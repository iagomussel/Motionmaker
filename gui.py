"""Interface local do MotionForge. Inicie com python gui.py."""
import argparse
import json
import re
import shutil
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
STYLES = ('paper', 'flat', 'kinetic', 'blueprint', 'ui', 'editorial')
STRUCTURES = ('auto', 'aida', 'pas', 'explainer', 'story', 'list')


def build_command(data, folder):
    brief = str(data.get('brief', '')).strip()
    if not 3 <= len(brief) <= 12000:
        raise ValueError('Escreva um briefing entre 3 e 12.000 caracteres.')
    style, structure = data.get('style', 'paper'), data.get('structure', 'auto')
    fmt = data.get('format', '9:16')
    if style not in STYLES or structure not in STRUCTURES or fmt not in ('9:16', '16:9'):
        raise ValueError('Estilo, estrutura ou formato inválido.')
    seconds, fps = int(data.get('seconds', 30)), int(data.get('fps', 30))
    if not 5 <= seconds <= 180 or fps not in (24, 30, 60):
        raise ValueError('Duração deve ser de 5 a 180 segundos; FPS: 24, 30 ou 60.')
    cmd = [sys.executable, '-u', str(ROOT / 'main.py'), brief, '--workdir', str(folder / 'work'),
           '--out', str(folder / 'video.mp4'), '--style', style, '--structure', structure,
           '--format', fmt, '--seconds', str(seconds), '--fps', str(fps), '--stills']
    for key in ('brand', 'url', 'colors', 'model', 'voice'):
        value = str(data.get(key, '')).strip()
        if len(value) > 500:
            raise ValueError(f'Campo {key} muito longo.')
        if value:
            cmd.extend(['--' + key, value])
    if data.get('no_tts'):
        cmd.append('--no-tts')
    if data.get('no_captions'):
        cmd.append('--no-captions')
    return cmd


class App:
    def __init__(self, storage):
        self.storage = Path(storage).resolve()
        self.storage.mkdir(parents=True, exist_ok=True)
        self.jobs = {}
        self.lock = threading.Lock()
        # Recupera resultados e identifica execuções interrompidas.
        for path in self.storage.glob('*/job.json'):
            try:
                job = json.loads(path.read_text())
                if job['status'] == 'running':
                    job.update(status='failed', error='Execução interrompida. Gere o vídeo novamente.')
                self.jobs[job['id']] = job
            except (ValueError, KeyError, OSError):
                pass

    def save(self, job):
        (self.storage / job['id'] / 'job.json').write_text(json.dumps(job, ensure_ascii=False))

    def create(self, data):
        jid = uuid.uuid4().hex
        folder = self.storage / jid
        cmd = build_command(data, folder)
        with self.lock:
            if any(j['status'] == 'running' for j in self.jobs.values()):
                raise ValueError('Já existe uma geração em andamento. Aguarde a conclusão.')
            folder.mkdir()
            job = dict(id=jid, title=str(data.get('brand') or data['brief'])[:70], status='running', error='')
            self.jobs[jid] = job
            self.save(job)
        threading.Thread(target=self.run, args=(job, cmd, folder), daemon=True).start()
        return job.copy()

    def run(self, job, cmd, folder):
        try:
            with (folder / 'log.txt').open('w') as log:
                result = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            success = result.returncode == 0 and (folder / 'video.mp4').exists()
            with self.lock:
                job.update(status='done' if success else 'failed', error='' if success else 'A geração falhou. Consulte o registro abaixo.')
                self.save(job)
        except Exception as exc:
            with self.lock:
                job.update(status='failed', error=str(exc))
                self.save(job)


def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        def send(self, status, body, content_type='application/json; charset=utf-8'):
            raw = json.dumps(body, ensure_ascii=False).encode() if isinstance(body, (dict, list)) else body
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/api/jobs':
                with app.lock:
                    return self.send(200, list(reversed(list(app.jobs.values()))))
            if path == '/api/health':
                import urllib.request
                try:
                    with urllib.request.urlopen('http://localhost:11434/api/tags', timeout=2) as response:
                        models = [m['name'] for m in json.load(response).get('models', [])]
                    ollama = True
                except Exception:
                    models, ollama = [], False
                return self.send(200, dict(ollama=ollama, models=models, ffmpeg=bool(shutil.which('ffmpeg')), ffprobe=bool(shutil.which('ffprobe'))))
            match = re.fullmatch(r'/api/jobs/([a-f0-9]{32})/(log|video)', path)
            if match and match[1] in app.jobs:
                file = app.storage / match[1] / ('log.txt' if match[2] == 'log' else 'video.mp4')
                if file.exists():
                    return self.send(200, file.read_bytes()[-100000:] if match[2] == 'log' else file.read_bytes(),
                                     'text/plain; charset=utf-8' if match[2] == 'log' else 'video/mp4')
                return self.send(404, {'error': 'Arquivo ainda não disponível.'})
            assets = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}
            if path in assets:
                name, mime = assets[path]
                return self.send(200, (ROOT / 'web' / name).read_bytes(), mime)
            self.send(404, {'error': 'Não encontrado.'})

        def do_POST(self):
            # JSON + same-origin impedem submissões de páginas externas.
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host', ''):
                return self.send(403, {'error': 'Origem não permitida.'})
            if self.path != '/api/jobs':
                return self.send(404, {'error': 'Não encontrado.'})
            try:
                size = int(self.headers.get('Content-Length', 0))
                if not 0 < size <= 32000 or self.headers.get_content_type() != 'application/json':
                    raise ValueError('Envie JSON de até 32 KB.')
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError('Envie um objeto JSON.')
                self.send(202, app.create(data))
            except (ValueError, TypeError) as exc:
                self.send(400, {'error': str(exc)})
    return Handler


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=7860)
    parser.add_argument('--data-dir', default=str(ROOT / 'projects'))
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(App(args.data_dir)))
    print(f'MotionForge Studio → http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
