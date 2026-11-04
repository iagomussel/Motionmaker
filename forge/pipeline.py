import json
from pathlib import Path

from .audio import mix_and_mux
from .page import build_page, fonts_link
from .plan import make_plan, normalize_plan
from .render import Stage
from .scenes import fallback_scene, fix_scene, write_scene
from .tts import synth_scene

LEAD = 0.35      # a voz entra 0,35 s depois do corte
TAIL = 0.45      # respiro depois da última palavra
MIN_DUR = 2.5
END_HOLD = 1.5   # cartão final segura mais um pouco


def log(*a):
    print("·", *a, flush=True)


def build_timeline(plan, voice_meta, width, height, fps):
    scenes, t = [], 0.0
    for i, s in enumerate(plan["scenes"]):
        meta = voice_meta.get(s["id"])
        if meta:
            speech = meta["duration"]
            beats = [{"w": w["w"], "t": round(LEAD + w["t"], 3), "d": round(w["d"], 3)} for w in meta["words"]]
        else:
            speech = max(1.0, len(s["narration"].split()) / 2.6)
            beats = []
        dur = max(MIN_DUR, LEAD + speech + TAIL)
        if i == len(plan["scenes"]) - 1:
            dur = max(3.5, dur + END_HOLD)
        dur = round(dur * fps) / fps  # cortes caem exatamente num quadro
        scenes.append({"id": s["id"], "start": round(t, 4), "dur": dur, "narration": s["narration"], "beats": beats})
        t += dur
    return {"width": width, "height": height, "fps": fps, "duration": round(t, 4), "scenes": scenes}


def run(args, llm):
    work = Path(args.workdir)
    (work / "scenes").mkdir(parents=True, exist_ok=True)
    plan_path = work / "plan.json"

    # 1. roteiro
    if args.plan:
        raw = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        plan = normalize_plan(raw, args.style if args.style_set else raw.get("style"))
    elif plan_path.exists() and not args.replan:
        plan = normalize_plan(json.loads(plan_path.read_text(encoding="utf-8")))
    else:
        log(f"Escrevendo o roteiro (estrutura: {args.structure}, estilo: {args.style})…")
        plan = make_plan(llm, args.plan_model or args.model, args.brief, args.brand, args.url, args.colors,
                         args.language, args.style, args.structure, args.seconds)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"Roteiro: {len(plan['scenes'])} cenas → {plan_path}")

    # 2. voz (a voz define o tempo)
    voice_meta, voice_files = {}, {}
    if not args.no_tts:
        for s in plan["scenes"]:
            log(f"Voz: {s['id']}")
            wav, meta = synth_scene(s["narration"], args.voice, args.length_scale, args.voices_dir, work / "voice", s["id"])
            voice_meta[s["id"]], voice_files[s["id"]] = meta, wav

    # 3. linha do tempo
    W, H = (1080, 1920) if args.format == "9:16" else (1920, 1080)
    timeline = build_timeline(plan, voice_meta, W, H, args.fps)
    log(f"Duração total: {timeline['duration']:.1f} s")

    # 4. cenas
    codes = {}
    html = work / "film.html"
    fonts_html = fonts_link(plan["fonts"])
    tl = build_page(plan, timeline, {}, not args.no_captions, html, fonts_html)  # para preencher safe/band
    for i, s in enumerate(plan["scenes"]):
        f = work / "scenes" / f"{s['id']}.js"
        if f.exists() and not args.regen:
            codes[s["id"]] = f.read_text(encoding="utf-8")
            continue
        log(f"Animando cena {i + 1}/{len(plan['scenes'])}: {s['id']}")
        codes[s["id"]] = write_scene(llm, args.model, plan, tl, i)
        f.write_text(codes[s["id"]], encoding="utf-8")

    # 5. roda, audita e corrige
    ids = [s["id"] for s in plan["scenes"]]
    with Stage(W, H) as stage:
        for rnd in range(args.max_fix + 1):
            tl = build_page(plan, timeline, codes, not args.no_captions, html, fonts_html)
            stage.load(html)
            problems = stage.audit(ids)
            if not problems:
                log("Todas as cenas passaram na auditoria.")
                break
            for sid, issues in problems.items():
                log(f"Cena {sid}: {len(issues)} problema(s)")
                for x in issues[:4]:
                    print("    -", x[:200])
            if rnd == args.max_fix:
                for sid in problems:
                    i = ids.index(sid)
                    log(f"Usando cena reserva para {sid}")
                    codes[sid] = fallback_scene(plan["scenes"][i], first=(i == 0))
                    (work / "scenes" / f"{sid}.js").write_text(codes[sid], encoding="utf-8")
                tl = build_page(plan, timeline, codes, not args.no_captions, html, fonts_html)
                stage.load(html)
                break
            for sid, issues in problems.items():
                i = ids.index(sid)
                log(f"Corrigindo {sid} (rodada {rnd + 1})")
                codes[sid] = fix_scene(llm, args.model, plan, tl, i, codes[sid], issues)
                (work / "scenes" / f"{sid}.js").write_text(codes[sid], encoding="utf-8")

        if args.stills:
            for sc in timeline["scenes"]:
                stage.still(sc["start"] + sc["dur"] * 0.6, work / f"still_{sc['id']}.png")
            log(f"Prévias salvas em {work}")

        # 6. quadros → vídeo
        log("Renderizando quadros…")
        silent = work / "video_silent.mp4"
        stage.frames_to_video(timeline["duration"], args.fps, silent,
                              on_progress=lambda i, n: print(f"\r  {i * 100 // n}%", end="", flush=True))
        print("\r  100%")

    # 7. áudio
    out = Path(args.out)
    if voice_files:
        voices = [(voice_files[sc["id"]], sc["start"] + LEAD) for sc in timeline["scenes"]]
        mix_and_mux(silent, voices, timeline["duration"], out, music=args.music, music_volume=args.music_volume)
    else:
        out.write_bytes(silent.read_bytes())
    log(f"Pronto: {out}")
    return out
