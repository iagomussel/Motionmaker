import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright


class Stage:
    """Abre a página do filme num Chromium headless do tamanho exato do vídeo."""

    def __init__(self, width, height):
        self.width, self.height = width, height

    def __enter__(self):
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch()
        self.page = self.browser.new_page(viewport={"width": self.width, "height": self.height}, device_scale_factor=1)
        self.page_errors = []
        self.page.on("pageerror", lambda e: self.page_errors.append(str(e)))
        return self

    def __exit__(self, *a):
        self.browser.close()
        self._pw.stop()

    def load(self, html_path):
        self.page_errors.clear()
        self.page.goto(Path(html_path).resolve().as_uri())
        self.page.wait_for_function("window.__ready === true", timeout=60_000)

    def audit(self, scene_ids):
        """Devolve {id: [problemas]} para cada cena com erro de código ou de layout."""
        problems = {sid: [] for sid in scene_ids}
        for err in self.page.evaluate("window.__errors"):
            problems.setdefault(err["id"], []).append(f"[{err['phase']} error] {err['msg'][:600]}")
        for sid in scene_ids:
            if problems[sid]:
                continue
            problems[sid] += self.page.evaluate("id => window.__audit(id)", sid)
            for err in self.page.evaluate("window.__errors"):
                if err["id"] == sid and err["phase"] == "render":
                    problems[sid].append(f"[render error] {err['msg'][:600]}")
        return {k: v for k, v in problems.items() if v}

    def frames_to_video(self, total, fps, out_mp4, on_progress=None):
        n = int(round(total * fps))
        ff = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps), "-i", "-",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium", str(out_mp4)],
            stdin=subprocess.PIPE,
        )
        clip = {"x": 0, "y": 0, "width": self.width, "height": self.height}
        for i in range(n):
            self.page.evaluate("t => window.renderAt(t)", i / fps)
            ff.stdin.write(self.page.screenshot(type="png", clip=clip))
            if on_progress and i % fps == 0:
                on_progress(i, n)
        ff.stdin.close()
        if ff.wait() != 0:
            raise RuntimeError("ffmpeg falhou ao gerar o vídeo")

    def still(self, t, path):
        self.page.evaluate("t => window.renderAt(t)", t)
        self.page.screenshot(path=str(path), clip={"x": 0, "y": 0, "width": self.width, "height": self.height})
