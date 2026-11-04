// MotionForge player — monta as cenas, desenha qualquer instante t, legendas e auditoria.
(async () => {
  const TL = window.TIMELINE;
  const stage = document.getElementById('stage');
  const errors = window.__errors;
  const live = [];

  for (const sc of TL.scenes) {
    const root = document.createElement('div');
    root.className = 'scene';
    root.dataset.id = sc.id;
    stage.append(root);
    const ctx = {
      id: sc.id, root, W: TL.width, H: TL.height, dur: sc.dur, vertical: TL.height > TL.width,
      beats: sc.beats || [], narration: sc.narration || '', safe: TL.safe, captionBand: TL.captions ? TL.captionBand : null,
      css(txt) { const s = document.createElement('style'); s.textContent = txt; root.append(s); },
    };
    const def = kit.__registry[sc.id];
    const entry = { sc, ctx, def, ok: !!def, renderErr: false };
    if (!def) errors.push({ id: sc.id, phase: 'load', msg: `kit.scene('${sc.id}', ...) was never called` });
    else {
      try { await (def.init ? def.init.call(def, ctx) : null); }
      catch (e) { entry.ok = false; errors.push({ id: sc.id, phase: 'init', msg: String((e && e.stack) || e) }); }
    }
    live.push(entry);
  }

  // ---- legendas (karaokê) ----
  const cap = document.getElementById('cap');
  const chunks = [];
  if (TL.captions) {
    for (const sc of TL.scenes) {
      let cur = [];
      const flush = () => { if (cur.length) chunks.push({ words: cur, a: cur[0].t, b: cur[cur.length - 1].t + cur[cur.length - 1].d }); cur = []; };
      for (const w of sc.beats || []) {
        cur.push({ w: w.w, t: sc.start + w.t, d: w.d || 0.3 });
        if (cur.length >= 4 || /[.,!?;:…]$/.test(w.w)) flush();
      }
      flush();
    }
  }
  function renderCaptions(t) {
    if (!cap) return;
    let c = null;
    for (let i = 0; i < chunks.length; i++) {
      const next = chunks[i + 1];
      const end = next ? Math.min(chunks[i].b + 0.35, next.a) : chunks[i].b + 0.35;
      if (t >= chunks[i].a - 0.05 && t < end) { c = chunks[i]; break; }
    }
    if (!c) { cap.style.opacity = 0; return; }
    cap.style.opacity = 1;
    const html = '<span class="pill">' + c.words.map(w => `<span class="${t >= w.t ? 'on' : ''}">${kit.esc(w.w)}</span>`).join(' ') + '</span>';
    if (cap.__html !== html) { cap.innerHTML = html; cap.__html = html; }
  }

  // ---- render ----
  let lastIdx = -1;
  window.renderAt = t => {
    Math.random = kit.rand(Math.floor(t * 1000) + 1);
    let idx = 0;
    for (let i = 0; i < live.length; i++) if (t >= live[i].sc.start) idx = i;
    if (idx !== lastIdx) {
      live.forEach((e, i) => { e.ctx.root.style.visibility = i === idx ? 'visible' : 'hidden'; });
      lastIdx = idx;
    }
    const e = live[idx];
    if (e && e.ok) {
      try { e.def.render.call(e.def, t - e.sc.start, e.ctx); }
      catch (err) {
        if (!e.renderErr) errors.push({ id: e.sc.id, phase: 'render', msg: `at t=${(t - e.sc.start).toFixed(2)}s: ` + String((err && err.stack) || err) });
        e.renderErr = true;
      }
    }
    renderCaptions(t);
  };

  // ---- auditoria: o que o LLM precisa corrigir ----
  const effOpacity = (n, root) => {
    let o = 1;
    for (let x = n; x && x !== root.parentElement; x = x.parentElement) {
      const cs = getComputedStyle(x);
      if (cs.visibility === 'hidden' && x !== root) return 0;
      if (cs.display === 'none') return 0;
      o *= parseFloat(cs.opacity);
    }
    return o;
  };
  const ownText = n => [...n.childNodes].some(c => c.nodeType === 3 && c.textContent.trim()) || (n.__w && n.__w.length);
  window.__audit = id => {
    const e = live.find(x => x.sc.id === id);
    const issues = [];
    if (!e || !e.ok) return issues;
    const S = TL.safe, W = TL.width, H = TL.height;
    const dur = e.sc.dur;
    for (const lt of [0.05, dur * 0.5, Math.max(0.05, dur - 0.05)]) {
      window.renderAt(e.sc.start + lt);
      const vis = [...e.ctx.root.querySelectorAll('*')].filter(n => {
        if (n.tagName === 'STYLE' || n.classList.contains('ground')) return false;
        const r = n.getBoundingClientRect();
        return r.width > 4 && r.height > 4 && r.right > 0 && r.left < W && r.bottom > 0 && r.top < H && effOpacity(n, e.ctx.root) > 0.05;
      });
      if (vis.length < 2) issues.push(`At t=${lt.toFixed(2)}s almost nothing is visible on screen (only ${vis.length} visible element).`);
    }
    const tt = Math.min(dur - 0.05, Math.max(dur * 0.75, 1.2));
    window.renderAt(e.sc.start + tt);
    const seen = new Set();
    for (const n of e.ctx.root.querySelectorAll('*')) {
      if (n.tagName === 'STYLE' || !ownText(n)) continue;
      if (effOpacity(n, e.ctx.root) < 0.2) continue;
      const r = n.getBoundingClientRect();
      if (r.width < 2) continue;
      const label = (n.textContent || '').trim().slice(0, 40);
      if (seen.has(label)) continue;
      const out = [];
      if (r.left < S.left - 4) out.push(`left edge ${Math.round(r.left)}px < ${S.left}`);
      if (r.right > W - S.right + 4) out.push(`right edge ${Math.round(r.right)}px > ${W - S.right}`);
      if (r.top < S.top - 4) out.push(`top ${Math.round(r.top)}px < ${S.top}`);
      if (r.bottom > H - S.bottom + 4) out.push(`bottom ${Math.round(r.bottom)}px > ${H - S.bottom}`);
      if (TL.captions && r.bottom > TL.captionBand[0] && r.top < TL.captionBand[1]) out.push(`overlaps the caption band y ${TL.captionBand[0]}..${TL.captionBand[1]}`);
      if (out.length) { seen.add(label); issues.push(`Text "${label}" at t=${tt.toFixed(2)}s is outside the safe area: ${out.join(', ')}.`); }
    }
    return issues;
  };

  try { await document.fonts.ready; } catch (_) {}
  window.renderAt(0);
  window.__ready = true;
})();
