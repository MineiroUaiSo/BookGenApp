// Gráfico de linhas: % de votos de Lula x Bolsonaro a cada atualização do TSE. window.Grafico.desenha(el, historico)
(function () {
'use strict';
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fmt = (v, d = 1) => v.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d });
const hora = (t) => t.slice(11, 16);
const W = 640, H = 280, M = { l: 44, r: 74, t: 14, b: 30 };
const PT = '13', PL = '22';

// Duas séries: Lula (13) e Bolsonaro (22); se não estiverem no histórico, os dois mais votados do último ponto.
function series(hist) {
  const ult = hist[hist.length - 1];
  const tem = (n) => ult.c.some((c) => c.n === n);
  const nums = tem(PT) && tem(PL) ? [PT, PL] : ult.c.slice(0, 2).map((c) => c.n);
  return nums.map((n) => {
    const cor = n === PT ? 'var(--pt)' : n === PL ? 'var(--pl)' : 'var(--outro)';
    const info = ult.c.find((c) => c.n === n);
    const pts = hist.map((p) => {
      const c = p.c.find((x) => x.n === n);
      return { t: Date.parse(p.t), pst: p.pst, y: c && p.vv ? (c.votos / p.vv) * 100 : null, tt: p.t };
    }).filter((p) => p.y != null);
    return { n, cor, nome: info.nome, partido: info.partido, pts };
  });
}

function escala(ss) {
  const ts = ss.flatMap((s) => s.pts.map((p) => p.t));
  const ys = ss.flatMap((s) => s.pts.map((p) => p.y));
  const t0 = Math.min(...ts); let t1 = Math.max(...ts); if (t1 === t0) t1 = t0 + 60000;
  let y0 = Math.min(...ys), y1 = Math.max(...ys);
  const passo = [1, 2, 5, 10].find((p) => (y1 - y0 + 4) / p <= 5) || 10;
  y0 = Math.max(0, Math.floor((y0 - 1) / passo) * passo); y1 = Math.min(100, Math.ceil((y1 + 1) / passo) * passo);
  const ticks = []; for (let v = y0; v <= y1 + 1e-9; v += passo) ticks.push(v);
  return { t0, t1, y0, y1, ticks, X: (t) => M.l + ((t - t0) / (t1 - t0)) * (W - M.l - M.r), Y: (y) => H - M.b - ((y - y0) / (y1 - y0)) * (H - M.t - M.b) };
}

function desenha(el, hist) {
  if (!hist || !hist.length) { el.innerHTML = '<p class="hint">O histórico começa a ser registrado a cada atualização do TSE. Volte em alguns minutos.</p>'; return; }
  const ss = series(hist);
  const e = escala(ss);
  const grade = e.ticks.map((v) => `<line x1="${M.l}" x2="${W - M.r}" y1="${e.Y(v)}" y2="${e.Y(v)}" stroke="var(--line)"/><text x="${M.l - 6}" y="${e.Y(v) + 4}" text-anchor="end" class="eixo">${fmt(v, 0)}%</text>`).join('');
  const nx = Math.min(5, hist.length);
  const eixoX = Array.from({ length: nx }, (_, i) => {
    const p = hist[Math.round((i * (hist.length - 1)) / Math.max(1, nx - 1))];
    return `<text x="${e.X(Date.parse(p.t))}" y="${H - 8}" text-anchor="middle" class="eixo">${hora(p.t)}</text>`;
  }).join('');
  const linhas = ss.map((s) => {
    const d = s.pts.map((p, i) => `${i ? 'L' : 'M'}${e.X(p.t).toFixed(1)},${e.Y(p.y).toFixed(1)}`).join('');
    const u = s.pts[s.pts.length - 1];
    return `<path d="${d}" fill="none" stroke="${s.cor}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/><circle cx="${e.X(u.t)}" cy="${e.Y(u.y)}" r="4" fill="${s.cor}"/>`;
  }).join('');
  // rótulos finais; se ficarem colados, afasta um do outro
  const fim = ss.map((s) => ({ s, u: s.pts[s.pts.length - 1] })).sort((a, b) => a.u.y - b.u.y);
  let yAnt = 1e9;
  const rotulos = fim.reverse().map(({ s, u }) => { const y = Math.min(e.Y(u.y) + 4, yAnt - 16); yAnt = y; return `<text x="${e.X(u.t) + 9}" y="${y}" class="rot" fill="${s.cor === 'var(--pl)' ? 'var(--ink)' : s.cor}">${fmt(u.y)}</text>`; }).join('');
  const resumo = ss.map((s) => `${s.nome} ${fmt(s.pts[s.pts.length - 1].y)}%`).join(' contra ');
  const legenda = ss.map((s) => `<span><i style="background:${s.cor}"></i>${esc(s.nome.toLowerCase().replace(/\S+/g, (w) => (w.length > 2 ? w[0].toUpperCase() + w.slice(1) : w)))} (${esc(s.partido)})</span>`).join('');
  el.innerHTML = `<div class="leg">${legenda}</div>
    <div class="gwrap"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Evolução da porcentagem de votos: ${esc(resumo)}, em ${hist.length} atualizações do TSE">${grade}${eixoX}${linhas}${rotulos}
    <g id="gcur" hidden><line y1="${M.t}" y2="${H - M.b}" stroke="var(--mut)" stroke-dasharray="3 3"/></g></svg><div class="gtip" hidden></div></div>
    <p class="hint">${hist.length} atualizações do TSE · de ${hora(hist[0].t)} a ${hora(hist[hist.length - 1].t)} · % sobre os votos nominais já apurados</p>`;
  ligaTooltip(el, ss, e);
}

function ligaTooltip(el, ss, e) {
  const svg = el.querySelector('svg'), cur = el.querySelector('#gcur'), tip = el.querySelector('.gtip'), box = el.querySelector('.gwrap');
  const base = ss[0].pts;
  const sai = () => { cur.hidden = true; tip.hidden = true; };
  svg.addEventListener('pointermove', (ev) => {
    const r = svg.getBoundingClientRect(), x = ((ev.clientX - r.left) / r.width) * W;
    let k = 0; base.forEach((p, i) => { if (Math.abs(e.X(p.t) - x) < Math.abs(e.X(base[k].t) - x)) k = i; });
    const p = base[k], px = e.X(p.t);
    cur.hidden = false; cur.firstElementChild.setAttribute('x1', px); cur.firstElementChild.setAttribute('x2', px);
    tip.hidden = false;
    tip.innerHTML = `<b>${hora(p.tt)}</b> · ${fmt(p.pst, 1)}% apurado` + ss.map((s) => { const q = s.pts.find((z) => z.t === p.t); return q ? `<div><i style="background:${s.cor}"></i>${fmt(q.y, 2)}%</div>` : ''; }).join('');
    const w = box.clientWidth, tx = (px / W) * w;
    tip.style.left = `${Math.min(Math.max(tx, 60), w - 60)}px`;
  });
  svg.addEventListener('pointerleave', sai);
}

window.Grafico = { desenha };
})();
