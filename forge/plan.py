import json
import re
import unicodedata

from .prompts import PLAN_SYSTEM, PLAN_USER, STRUCTURES
from .styles import get_style

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def slug(s, fallback):
    s = unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if not s or not s[0].isalpha():
        s = fallback
    return s[:32]


def word_budget(seconds):
    # fala natural: ~2,3 a 2,7 palavras por segundo, descontando o cartão final
    speak = max(8, seconds - 3)
    return int(speak * 2.1), int(speak * 2.6)


def make_plan(llm, model, brief, brand="", url="", colors="", language="Brazilian Portuguese",
              style="paper", structure="auto", seconds=30):
    st = get_style(style)
    lo, hi = word_budget(seconds)
    n_lo, n_hi = (4, 6) if seconds <= 25 else (5, 8) if seconds <= 45 else (7, 12)
    system = PLAN_SYSTEM.format(
        structure=STRUCTURES.get(structure, STRUCTURES["auto"]), look=st["look"],
        min_scenes=n_lo, max_scenes=n_hi, min_words=lo, max_words=hi,
        default_palette=json.dumps(st["palette"]), default_fonts=json.dumps(st["fonts"]), language=language,
    )
    user = PLAN_USER.format(brief=brief, brand=brand or "-", url=url or "-", colors=colors or "-", seconds=seconds)
    plan = llm.chat_json(model, system, user, temperature=0.6)
    plan["style"] = style
    return normalize_plan(plan, style)


def normalize_plan(plan, style=None):
    style = style or plan.get("style") or "paper"
    st = get_style(style)
    out = {
        "title": str(plan.get("title") or "Video").strip(),
        "style": style,
        "structure": str(plan.get("structure") or "").strip(),
        "look": st["look"],
        "palette": dict(st["palette"]),
        "fonts": dict(st["fonts"]),
        "scenes": [],
    }
    for k, v in (plan.get("palette") or {}).items():
        if k in out["palette"] and isinstance(v, str) and HEX.match(v.strip()):
            out["palette"][k] = v.strip()
    for k, v in (plan.get("fonts") or {}).items():
        if k in out["fonts"] and isinstance(v, str) and re.match(r"^[A-Za-z0-9 ]{2,40}$", v.strip()):
            out["fonts"][k] = v.strip()

    scenes = plan.get("scenes") or []
    if not scenes:
        raise ValueError("O roteiro não tem cenas.")
    seen = set()
    for i, s in enumerate(scenes):
        sid = slug(s.get("id") or s.get("headline") or "", f"cena{i + 1}")
        while sid in seen:
            sid = f"{sid[:28]}-{i + 1}"
        seen.add(sid)
        out["scenes"].append({
            "id": sid,
            "beat": str(s.get("beat") or s.get("act") or "").strip(),
            "narration": str(s.get("narration", "")).strip(),
            "headline": str(s.get("headline", "")).strip(),
            "sub": str(s.get("sub", "") or "").strip(),
            "visual": str(s.get("visual", "")).strip(),
        })
    return out
