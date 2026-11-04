"""Estilos reutilizáveis. Cada um é um "vocabulário" de movimento e desenho que entra no prompt da cena.

Para criar um estilo novo, copie um bloco e mude os textos. Nada aqui depende do assunto do vídeo.
"""

STYLES = {
    "paper": {
        "name": "Stop-motion paper",
        "look": "Stop-motion paper cut-outs on a flat background; objects hop in frame by frame with a slight jitter and overshoot.",
        "palette": {"ground": "#FFF7ED", "main": "#F97316", "second": "#1C1917", "accent": "#9A3412"},
        "fonts": {"display": "DM Serif Display", "sans": "Inter"},
        "motion": """- Drive object motion with q = step(t) (12 fps). Text entrances use smooth t.
- Resting objects boil: translate jit(t, seed, 1.5) px and rotate jit(t, seed, .6) deg.
- Arrivals overshoot with eob (1.5-1.9); impacts squash with pulse; falls accelerate with ei.""",
        "drawing": """- Flat fills + 5px var(--second) outline + hard shadow 10px 12px 0 rgba(0,0,0,.18) (.card, .f-* classes).
- Slight rotations (-6..6 deg) so pieces look hand-placed. People: head circle, hair shape, body trapezoid, dot eyes.""",
        "snippet": """const q = step(t);
const p = eob(seg(q, 0.4, 0.85), 1.7);
this.box.style.transform = `translate(${jit(t, 1, 1.5)}px, ${lerp(700, 0, p) + jit(t, 2, 1.5)}px) rotate(${-4 + jit(t, 3, .6)}deg)`;""",
    },
    "flat": {
        "name": "Flat geometric",
        "look": "Clean flat vector shapes, generous whitespace, smooth confident easing, one accent color doing one job.",
        "palette": {"ground": "#F5F7FB", "main": "#3B5BDB", "second": "#111827", "accent": "#F59F00"},
        "fonts": {"display": "Bricolage Grotesque", "sans": "Inter"},
        "motion": """- Smooth time only (no step/jit). Arrivals: eob 1.3-1.5 for shapes; eio for anything moving across the frame.
- Shapes can morph: animate width/height/border-radius together; scale from 0 at their own center.
- Held frames drift: the main group scales 1 -> 1.03 over the scene.""",
        "drawing": """- Solid fills, no outlines, no hard shadows (override .card with border:0; box-shadow:none inline).
- Rounded rects, circles, pills, simple icons from 2-4 shapes. Grid-aligned composition.""",
        "snippet": """const p = eob(seg(t, 0.4, 0.9), 1.4);
this.circle.style.transform = `scale(${p}) scale(${lerp(1, 1.03, seg(t, 0.9, ctx.dur))})`;""",
    },
    "kinetic": {
        "name": "Kinetic typography",
        "look": "Words are the visuals: huge type that slides, scales and stacks in rhythm with the voice, on a bold flat ground.",
        "palette": {"ground": "#111111", "main": "#FFD43B", "second": "#F8F9FA", "accent": "#FF6B6B"},
        "fonts": {"display": "Archivo Black", "sans": "Manrope"},
        "motion": """- Each key word of the narration appears exactly on its beat (beat(ctx, 'word')).
- Words slam in from one direction (eob 1.6) or scale from 1.4 to 1; the previous phrase moves up and dims to 30% opacity.
- One emphasized word per scene in var(--main), maybe underlined by a bar that grows with eo.""",
        "drawing": """- Type 140-220px for key words (set font-size inline), 48px for small connectors. Max 2 simple shapes (bar, circle).
- Stack words left-aligned in the safe area. Still one string per element: one element per phrase or key word.""",
        "snippet": """const tw = beat(ctx, 'rapido', 1.2);
const p = eob(seg(t, tw - 0.15, tw + 0.25), 1.6);
this.word.style.opacity = t < tw - 0.15 ? 0 : 1;
this.word.style.transform = `translateX(${lerp(-200, 0, p)}px) scale(${lerp(1.4, 1, p)})`;""",
    },
    "blueprint": {
        "name": "Blueprint diagram",
        "look": "Technical diagram on a grid: lines draw themselves on, boxes and arrows explain how a system works, calm camera push.",
        "palette": {"ground": "#0B2545", "main": "#5BC0EB", "second": "#E8F1F2", "accent": "#FDE74C"},
        "fonts": {"display": "Space Grotesk", "sans": "IBM Plex Sans"},
        "motion": """- Lines and outlines draw on with kit.draw(pathEl, eo(seg(t, a, b))) over 0.4-0.8 s, in reading order.
- Boxes fade+rise 20px after their outline is drawn. Arrows draw from source to target, then a dot travels along.
- Whole diagram group slowly pushes in: scale 1 -> 1.05 over the scene.""",
        "drawing": """- SVG strokes 4-6px in var(--second) and var(--main), no fills except 10% tints. Labels 28-36px in sans.
- Optional background grid: thin lines every 60px at 12% opacity (draw once in init).""",
        "snippet": """// in init: this.link = svg.querySelector('.bp-link');
kit.draw(this.link, eo(seg(t, 0.8, 1.4)));""",
    },
    "ui": {
        "name": "Product UI walkthrough",
        "look": "Product screens on a phone or browser mockup; a tap dot or cursor uses the interface; precise, eased, no bounce.",
        "palette": {"ground": "#EEF2F6", "main": "#7048E8", "second": "#1A1B25", "accent": "#12B886"},
        "fonts": {"display": "Plus Jakarta Sans", "sans": "Inter"},
        "motion": """- UI only eases (eio, eo): never overshoot, squash or jitter inside the screen.
- Causality: the dot moves to a control (eio 0.5-0.8 s), presses (scale .85 with pulse), then the result appears.
- Zoom in on what matters: scale the phone/browser group 1 -> 1.25 toward the active area with eio.""",
        "drawing": """- Phone: .phone/.screen. Browser: a .card with a 56px top bar and three small dots.
- UI inside: rows, buttons, chips, toggles built from divs; realistic spacing (16-24px), 24-32px text.
- Names and data shown are generic or from the brief; never invent metrics.""",
        "snippet": """const tap = beat(ctx, 'toque', 2.0);
const m = eio(seg(t, tap - 0.7, tap - 0.1));
this.dot.style.transform = `translate(${lerp(x0, x1, m)}px, ${lerp(y0, y1, m)}px) scale(${1 - 0.15 * pulse(t, tap - 0.1, tap + 0.15)})`;""",
    },
    "editorial": {
        "name": "Editorial",
        "look": "Magazine layout: big serif headlines, color blocks that wipe in, thin rules, slow elegant pushes.",
        "palette": {"ground": "#F4EFE6", "main": "#C2410C", "second": "#1F2937", "accent": "#0F766E"},
        "fonts": {"display": "Fraunces", "sans": "Inter"},
        "motion": """- Color blocks wipe in from one edge (scaleX 0 -> 1 with eio, transform-origin at that edge).
- Text enters word by word, slow (stagger .12, dur .7). Rules (thin lines) grow with eo.
- Everything drifts slowly: 10-20 px over the scene. No bounce.""",
        "drawing": """- Large color blocks covering 30-60% of the frame, thin 3px rules, numbers or kickers in small caps sans 26px.
- Asymmetric layout; lots of whitespace.""",
        "snippet": """this.block.style.transformOrigin = '0 50%';
this.block.style.transform = `scaleX(${eio(seg(t, 0.2, 0.9))})`;""",
    },
}


def get_style(name):
    if name not in STYLES:
        raise ValueError(f"Estilo desconhecido: {name}. Opções: {', '.join(STYLES)}")
    return STYLES[name]
