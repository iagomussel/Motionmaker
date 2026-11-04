import json
import re

from .llm import extract_js
from .prompts import FIX_USER, SCENE_USER, scene_system
from .styles import get_style


def scene_context(plan, timeline, i):
    s = plan["scenes"][i]
    ts = timeline["scenes"][i]
    W, H = timeline["width"], timeline["height"]
    safe, band = timeline["safe"], timeline["captionBand"]
    beats = ", ".join(f"{b['w']}@{b['t']:.2f}" for b in ts["beats"]) or "(no voice)"
    prev = plan["scenes"][i - 1]["visual"][:160] if i > 0 else "(none: this is the first scene)"
    nxt = plan["scenes"][i + 1]["visual"][:160] if i + 1 < len(plan["scenes"]) else "(none: last scene)"
    first = ("\nThis is the FIRST scene: its frame 0 is the thumbnail. The headline must already read at t=0 "
             "(text.in with t0 = -0.5) and the main object must be visible at t=0.\n") if i == 0 else ""
    return SCENE_USER.format(
        W=W, H=H, orientation="vertical 9:16" if H > W else "horizontal 16:9",
        sl=safe["left"], sr=W - safe["right"], st=safe["top"], sb=H - safe["bottom"],
        band=f"y {band[0]}..{band[1]}" if timeline.get("captions") else "none",
        **plan["palette"], structure=plan.get("structure") or "-",
        index=i + 1, count=len(plan["scenes"]), id=s["id"], beat=s.get("beat") or "-", dur=ts["dur"],
        narration=s["narration"], beats=beats, headline=s["headline"], sub=s["sub"],
        visual=s["visual"], prev=prev, next=nxt, first_note=first,
    )


def _force_id(code, sid):
    # garante que o módulo registra a cena com o id certo
    return re.sub(r"kit\.scene\(\s*(['\"`])[^'\"`]*\1", f"kit.scene('{sid}'", code, count=1)


def write_scene(llm, model, plan, timeline, i, temperature=0.4):
    ctx = scene_context(plan, timeline, i)
    system = scene_system(get_style(plan["style"]))
    code = extract_js(llm.chat(model, system, ctx, temperature=temperature))
    return _force_id(code, plan["scenes"][i]["id"])


def fix_scene(llm, model, plan, timeline, i, code, issues):
    ctx = scene_context(plan, timeline, i)
    user = FIX_USER.format(context=ctx, code=code, issues="\n".join(f"- {x}" for x in issues))
    system = scene_system(get_style(plan["style"]))
    fixed = extract_js(llm.chat(model, system, user, temperature=0.2))
    return _force_id(fixed, plan["scenes"][i]["id"])


def fallback_scene(scene, first=False):
    """Cena simples e segura: usada só se o modelo não acertar depois das tentativas."""
    head, sub = json.dumps(scene["headline"]), json.dumps(scene["sub"])
    t0 = "-0.5" if first else "0.1"
    return f"""const {{ seg, lerp, eob, step, jit, text, pulse }} = kit;
kit.scene('{scene['id']}', {{
  init(ctx) {{
    ctx.root.append(kit.h('<div class="ground"></div>'));
    const top = ctx.safe.top + 40;
    this.words = kit.h('<div class="words" style="left:' + ctx.safe.left + 'px;top:' + top + 'px;width:' + (ctx.W - ctx.safe.left - ctx.safe.right) + 'px"><h2 class="line"></h2><p class="sub"></p></div>');
    this.words.querySelector('.line').textContent = {head};
    this.words.querySelector('.sub').textContent = {sub};
    ctx.root.append(this.words);
    this.line = this.words.querySelector('.line'); this.sub = this.words.querySelector('.sub');
    const size = Math.min(ctx.W, ctx.H) * 0.42;
    this.blob = kit.h('<div class="card" style="border-radius:50%;background:var(--main);width:' + size + 'px;height:' + size + 'px;left:' + (ctx.W - size) / 2 + 'px;top:' + (ctx.H * 0.55 - size / 2) + 'px"></div>');
    ctx.root.append(this.blob);
  }},
  render(t, ctx) {{
    const q = step(t);
    text.in(this.line, t, {t0});
    text.in(this.sub, t, 0.8);
    this.words.style.transform = 'translateY(' + (-2 * t) + 'px)';
    const p = eob(seg(q, 0.2, 0.7), 1.7), s = 0.06 * pulse(q, 0.7, 0.95);
    this.blob.style.transform = 'scale(' + (p * (1 + s)) + ',' + (p * (1 - s)) + ') rotate(' + jit(t, 1, 1.2) + 'deg)';
  }},
}});
"""
