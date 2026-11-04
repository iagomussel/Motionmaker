import json
import subprocess
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

import pytest
from gui import App, build_command, handler_for


def test_command_validates_and_keeps_brief_as_argument(tmp_path):
    command = build_command({'brief': 'Minha ideia; $(touch /tmp/never)', 'no_tts': True}, tmp_path)
    assert command[3] == 'Minha ideia; $(touch /tmp/never)'
    assert '--no-tts' in command
    for data in ({'brief': ''}, {'brief': 'teste', 'style': '../x'}, {'brief': 'teste', 'seconds': 0}, {'brief': 'teste', 'fps': 10}):
        with pytest.raises(ValueError):
            build_command(data, tmp_path)


def test_job_completion_failure_and_recovery(tmp_path):
    app = App(tmp_path)
    def complete(cmd, **kwargs):
        from pathlib import Path
        Path(cmd[cmd.index('--out') + 1]).write_bytes(b'video')
        return subprocess.CompletedProcess(cmd, 0)
    with patch('gui.subprocess.run', side_effect=complete):
        job = app.create({'brief': 'Video de teste'})
        for thread in threading.enumerate():
            if thread is not threading.current_thread() and thread.daemon:
                thread.join(timeout=2)
    assert app.jobs[job['id']]['status'] == 'done'
    assert App(tmp_path).jobs[job['id']]['status'] == 'done'
    folder = tmp_path / job['id']
    app.jobs[job['id']]['status'] = 'running'
    app.save(app.jobs[job['id']])
    assert App(tmp_path).jobs[job['id']]['status'] == 'failed'
    with pytest.raises(ValueError, match='andamento'):
        app.create({'brief': 'Segunda geração'})
    app.jobs[job['id']]['status'] = 'done'
    with patch('gui.subprocess.run', side_effect=OSError('falha do processo')):
        failed = app.create({'brief': 'Teste de falha'})
        for thread in threading.enumerate():
            if thread is not threading.current_thread() and thread.daemon:
                thread.join(timeout=2)
    assert app.jobs[failed['id']]['status'] == 'failed'


def test_http_validation_and_assets(tmp_path):
    app = App(tmp_path)
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(app))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        assert 'MotionForge' in urlopen(base).read().decode()
        assert json.load(urlopen(base + '/api/jobs')) == []
        for path, body, headers, code in [('/api/jobs', b'{', {'Content-Type':'application/json'}, 400), ('/api/jobs', b'{}', {'Content-Type':'application/json','Origin':'http://evil.example'},403), ('/api/jobs', b'[]', {'Content-Type':'application/json'},400), ('/missing', b'{}', {'Content-Type':'application/json'},404)]:
            with pytest.raises(HTTPError) as exc:
                urlopen(Request(base + path, body, headers))
            assert exc.value.code == code
        with pytest.raises(HTTPError):
            urlopen(base + '/../gui.py')
    finally:
        server.shutdown()
        server.server_close()
