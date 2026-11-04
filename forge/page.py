import json
from pathlib import Path
from string import Template
from urllib.parse import quote_plus

import requests

RUNTIME = Path(__file__).parent / "runtime"

BASE_CSS = Template("""
#stage { --ground:$ground; --main:$main; --second:$second; --accent:$accent;
  --paper: color-mix(in srgb, var(--ground) 70%, #ffffff);
  --soft: color-mix(in srgb, var(--main) 14%, var(--ground));
  position:relative; width:${W}px; height:${H}px; overflow:hidden; background:var(--ground);
  color:var(--second); font-family:$sans_stack; }
#stage * { transition:none !important; animation:none !important; box-sizing:border-box; }
.scene { position:absolute; inset:0; visibility:hidden; }
.ground { position:absolute; inset:0; background:var(--soft); }
.words { position:absolute; margin:0; display:flex; flex-direction:column; gap:20px; }
.words > * { margin:0; }
.line { font-family:$display_stack; font-size:${line}px; line-height:1.03; font-weight:400; letter-spacing:-.01em; }
.sub { font-size:${sub}px; line-height:1.2; font-weight:400; color:color-mix(in srgb, var(--second) 78%, var(--soft)); }
.card { position:absolute; background:var(--paper); border:5px solid var(--second); border-radius:14px;
  box-shadow:10px 12px 0 rgba(0,0,0,.18); }
.chip { display:inline-block; align-self:flex-start; padding:8px 18px; border-radius:999px; font-size:24px; font-weight:700;
  background:color-mix(in srgb, var(--main) 22%, var(--paper)); color:var(--second); }
.outline { border:5px solid var(--second); }
.phone { position:absolute; width:440px; height:860px; border-radius:64px; background:var(--second);
  box-shadow:12px 16px 0 rgba(0,0,0,.18); }
.screen { position:absolute; inset:22px; border-radius:46px; background:var(--paper); overflow:hidden; }
.art { position:absolute; inset:0; width:100%; height:100%; overflow:visible; }
.f-paper { fill:var(--paper); stroke:var(--second); stroke-width:5; stroke-linejoin:round; }
.f-main { fill:var(--main); stroke:var(--second); stroke-width:5; stroke-linejoin:round; }
.f-accent { fill:var(--accent); stroke:var(--second); stroke-width:5; stroke-linejoin:round; }
.f-soft { fill:var(--soft); stroke:var(--second); stroke-width:5; stroke-linejoin:round; }
.f-ink { fill:var(--second); }
.stroke { fill:none; stroke:var(--accent); stroke-width:12; stroke-linecap:round; stroke-linejoin:round; }
#cap { position:absolute; left:${capL}px; right:${capR}px; top:${capTop}px; height:${capH}px; z-index:50;
  display:flex; align-items:center; justify-content:center; text-align:center; pointer-events:none; }
#cap .pill { display:inline-block; padding:14px 26px; border-radius:22px; background:var(--second); color:var(--paper);
  font-family:$sans_stack; font-weight:700; font-size:${capFont}px; line-height:1.25; }
#cap .on { color:var(--main); }
""")

HTML = Template("""<!doctype html>
<html><head><meta charset="utf-8">
$fonts_link
<style>html,body{margin:0;padding:0;background:#000;overflow:hidden}</style>
<style>$base_css</style>
</head><body>
<div id="stage">$cap</div>
<script>window.TIMELINE = $timeline;</script>
<script>$kit</script>
$scenes
<script>$player</script>
</body></html>
""")


def layout(width, height):
    vertical = height > width
    if vertical:
        safe = {"top": 240, "right": 120, "bottom": 420, "left": 90}
        band = [height - safe["bottom"] - 170, height - safe["bottom"]]
        sizes = {"line": 92, "sub": 42, "capFont": 44}
    else:
        safe = {"top": 70, "right": 90, "bottom": 70, "left": 90}
        band = [height - 210, height - 70]
        sizes = {"line": 104, "sub": 42, "capFont": 42}
    return safe, band, sizes


def fonts_link(fonts):
    fams = [(fonts["display"], ""), (fonts["sans"], ":wght@400;700")]
    url = "https://fonts.googleapis.com/css2?" + "&".join(
        f"family={quote_plus(f)}{w}" for f, w in fams) + "&display=block"
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:  # família sem peso 700, por exemplo
            url = "https://fonts.googleapis.com/css2?" + "&".join(
                f"family={quote_plus(f)}" for f, _ in fams) + "&display=block"
            r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            return f'<link rel="stylesheet" href="{url}">'
    except requests.RequestException:
        pass
    return ""


def stacks(fonts):
    return (f"'{fonts['display']}', Georgia, serif", f"'{fonts['sans']}', system-ui, sans-serif")


def build_page(plan, timeline, scene_codes, captions, out_path, fonts_html=None):
    W, H = timeline["width"], timeline["height"]
    safe, band, sizes = layout(W, H)
    display_stack, sans_stack = stacks(plan["fonts"])
    css = BASE_CSS.substitute(
        **plan["palette"], W=W, H=H, display_stack=display_stack, sans_stack=sans_stack,
        line=sizes["line"], sub=sizes["sub"], capFont=sizes["capFont"],
        capL=safe["left"], capR=safe["right"], capTop=band[0], capH=band[1] - band[0],
    )
    tl = dict(timeline, safe=safe, captionBand=band, captions=bool(captions))
    def safe_js(s):
        return json.dumps(s, ensure_ascii=False).replace("</", "<\\/")

    scripts = "\n".join(
        "<script>kit.__load(" + safe_js(sid) + ", " + safe_js(code) + ");</script>"
        for sid, code in scene_codes.items()
    )
    html = HTML.substitute(
        fonts_link=fonts_link(plan["fonts"]) if fonts_html is None else fonts_html,
        base_css=css,
        cap='<div id="cap"></div>' if captions else "",
        timeline=json.dumps(tl, ensure_ascii=False).replace("</", "<\\/"),
        kit=(RUNTIME / "kit.js").read_text(),
        scenes=scripts,
        player=(RUNTIME / "player.js").read_text(),
    )
    Path(out_path).write_text(html, encoding="utf-8")
    return tl
