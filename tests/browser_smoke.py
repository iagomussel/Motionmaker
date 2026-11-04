"""Teste de UI com worker simulado, sem Ollama/Piper."""
import json
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gui import App, handler_for
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory() as storage:
        app = App(storage)
        def worker(job, cmd, folder):
            (folder / 'log.txt').write_text('Roteiro de teste concluído.\nPronto.')
            (folder / 'video.mp4').write_bytes(b'test-download')
            with app.lock:
                job['status'] = 'done'
                app.save(job)
        app.run = worker
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(app))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                page = browser.new_page(viewport={'width':1440,'height':1100})
                errors=[]
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}')
                page.get_by_role('button', name='Kinetic', exact=True).click()
                assert page.locator('#style').input_value() == 'kinetic'
                page.locator('#format').select_option('16:9')
                assert page.locator('#ratio').inner_text() == '16:9'
                page.locator('#brief').fill('Explique como organizar ideias em um vídeo animado.')
                page.locator('#brand').fill('Minha marca')
                page.locator('#generate').click()
                page.get_by_text('✓ Concluído', exact=True).wait_for(timeout=10000)
                page.get_by_text('Registro da geração', exact=True).click()
                page.get_by_text('Roteiro de teste concluído.', exact=False).wait_for()
                with page.expect_download() as event:
                    page.get_by_text('↓ Baixar MP4').click()
                assert event.value.suggested_filename == 'motionforge.mp4'
                assert Path(event.value.path()).read_bytes() == b'test-download'
                page.screenshot(path='/tmp/motionforge-desktop.png', full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.screenshot(path='/tmp/motionforge-mobile.png', full_page=True)
                page.reload()
                page.get_by_text('Minha marca',exact=True).wait_for()
                assert not errors, errors
                browser.close()
            print('PASS: seleção, envio, conclusão, logs, download, histórico e layout mobile.')
        finally:
            server.shutdown()
            server.server_close()

if __name__ == '__main__':
    main()
