// MotionForge kit — tudo aqui é função pura do tempo t (segundos).
(() => {
  const TL = window.TIMELINE;
  const W = TL.width, H = TL.height;
  const clamp01 = x => (x < 0 ? 0 : x > 1 ? 1 : x);
  const seg = (t, a, b) => clamp01((t - a) / (b - a));
  const lerp = (a, b, p) => a + (b - a) * p;
  const eo = x => 1 - Math.pow(1 - clamp01(x), 3);
  const ei = x => Math.pow(clamp01(x), 3);
  const eio = x => { x = clamp01(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
  const eob = (x, s = 1.7) => { x = clamp01(x); const c = s + 1; return 1 + c * Math.pow(x - 1, 3) + s * Math.pow(x - 1, 2); };
  const pulse = (t, a, b) => Math.sin(Math.PI * seg(t, a, b));
  const hash = n => { const x = Math.sin(n * 12.9898 + 78.233) * 43758.5453; return x - Math.floor(x); };
  const rand = seed => { let s = (seed >>> 0) || 1; return () => { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 4294967296; }; };
  const step = (t, fps = 12) => Math.floor(t * fps) / fps;
  const jit = (t, seed, amt = 1, fps = 12) => (hash(Math.floor(t * fps) * 7.13 + seed * 91.7) - 0.5) * 2 * amt;
  const breathe = (t, amt = 0.012, period = 3.2) => 1 + amt * Math.sin((2 * Math.PI * t) / period);
  const h = html => { const d = document.createElement('div'); d.innerHTML = String(html).trim(); return d.firstElementChild; };
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const norm = s => String(s).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]/g, '');
  const beat = (ctx, prefix, fallback = 1) => {
    const p = norm(prefix);
    const b = (ctx.beats || []).find(x => norm(x.w).startsWith(p));
    return b ? b.t : fallback;
  };

  const draw = (el, p) => {
    if (el.__len === undefined) el.__len = el.getTotalLength ? el.getTotalLength() : 1000;
    el.style.strokeDasharray = el.__len;
    el.style.strokeDashoffset = el.__len * (1 - clamp01(p));
  };

  function words(el) {
    if (!el.__w) {
      const txt = el.textContent;
      el.textContent = '';
      el.__w = txt.split(/(\s+)/).map(part => {
        if (!part) return null;
        if (/^\s+$/.test(part)) { el.append(part); return null; }
        const s = document.createElement('span');
        s.textContent = part;
        s.style.display = 'inline-block';
        el.append(s);
        return s;
      }).filter(Boolean);
    }
    return el.__w;
  }
  const text = {
    in(el, t, t0, o = {}) {
      const { stagger = 0.09, dur = 0.5, dy = 28, dx = 0 } = o;
      const ws = words(el);
      ws.forEach((s, i) => {
        const p = eo(seg(t, t0 + i * stagger, t0 + i * stagger + dur));
        s.style.opacity = p;
        s.style.transform = `translate(${(1 - p) * dx}px, ${(1 - p) * dy}px)`;
      });
      return t0 + (ws.length - 1) * stagger + dur;
    },
    pop(el, t, t0, o = {}) {
      const { stagger = 0.07, dur = 0.4 } = o;
      const ws = words(el);
      ws.forEach((s, i) => {
        const a = t0 + i * stagger, p = eob(seg(t, a, a + dur), 1.8);
        s.style.opacity = t < a ? 0 : 1;
        s.style.transform = `scale(${p})`;
      });
      return t0 + (ws.length - 1) * stagger + dur;
    },
    type(el, t, t0, cps = 22) {
      if (el.__full === undefined) el.__full = el.textContent;
      const n = Math.max(0, Math.min(el.__full.length, Math.floor((t - t0) * cps)));
      const s = el.__full.slice(0, n);
      if (el.textContent !== s) el.textContent = s;
      return t0 + el.__full.length / cps;
    },
  };

  const registry = {};
  const errors = (window.__errors = []);
  let expect = null;
  const kit = {
    W, H, clamp01, seg, lerp, eo, ei, eio, eob, pulse, rand, step, jit, breathe, h, esc, beat, text, draw,
    scene(id, def) {
      const key = expect || id;
      if (expect && id !== expect) errors.push({ id: key, phase: 'load', msg: `kit.scene('${id}') used, expected '${expect}' (registered anyway)` });
      registry[key] = def;
    },
    __load(id, code) {
      expect = id;
      try { new Function('kit', code)(kit); }
      catch (e) { errors.push({ id, phase: 'load', msg: String((e && e.stack) || e) }); }
      expect = null;
    },
    __registry: registry,
  };
  window.kit = kit;
})();
