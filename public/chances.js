// Chance de Lula vencer o 2º turno: simulação de Monte Carlo sobre os votos que ainda faltam apurar.
// Universal: navegador (window.Chances) e Node (testes). É uma ESTIMATIVA do modelo, não um número do TSE.
//
// Para cada UF (e o exterior):
//  - votos válidos já contados (Lula + Flávio) e total previsto (mistura do que foi contado/fração apurada com o 1º turno);
//  - participação esperada do Lula nos votos que faltam = mistura entre a % observada até agora e um "prior"
//    (parcela do Lula no duelo Lula x Flávio do 1º turno naquela UF + deslocamento nacional estimado);
//    quanto mais apurado, mais peso na % observada;
//  - incertezas: choque nacional comum, ruído por UF e variação do comparecimento — todos encolhem com a apuração.
(function () {
'use strict';

const N_SIM = 20_000;
const LULA = '13';
const FLAVIO = '22';
const N0_SWING = 400_000;   // votos "virtuais" que ancoram o deslocamento nacional em 0
const K_PESO = 0.3;         // fração apurada em que observado e prior pesam igual
const TAU_PRIOR = 0.02;     // choque nacional com 0% apurado (2 pp); cai com a raiz da fração que falta
const SIGMA_UF = 0.015;     // ruído de cada UF (1,5 pp)
const SIGMA_COMP = 0.02;    // variação nacional do comparecimento (2%)

// gerador pseudoaleatório determinístico (mulberry32) + normal por Box-Muller: mesmo dado => mesma chance
function rng(seed) {
  let a = seed >>> 0;
  const u = () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  return () => { const r = Math.sqrt(-2 * Math.log(u() || 1e-12)); return r * Math.cos(2 * Math.PI * u()); };
}

const votosDe = (cands, n) => (cands || []).find((c) => String(c.numero) === n)?.votos || 0;
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));

// monta o resumo de cada UF a partir dos dados do 2º turno e do prior do 1º
function resumoUF(e, p) {
  const L = votosDe(e.candidatos, LULA), B = votosDe(e.candidatos, FLAVIO), n = L + B;
  const l1 = votosDe(p.candidatos, LULA), b1 = votosDe(p.candidatos, FLAVIO);
  const vv1 = p.candidatos.reduce((a, c) => a + c.votos, 0);
  const te = e.contagem?.te || p.contagem?.te || 0;
  const est = e.contagem?.est || 0;
  const f = te ? clamp(est / te, 0, 1) : 0; // fração do eleitorado já apurada
  return { uf: e.uf, L, n, q: l1 + b1 ? l1 / (l1 + b1) : 0.5, vv1, f, te };
}

/**
 * @param {object} D resultado de Apuracao.buscar() com D.insumos preenchido (2º turno)
 * @returns {object|null} null se o modelo não se aplica (1º turno, sem prior)
 */
function calcula(D, { sims = N_SIM, seed = 2026 } = {}) {
  if (!D || !D.insumos || D.eleicao?.turno !== 2) return null;
  const { prior, exterior } = D.insumos;
  const ufs = [];
  for (const e of D.estados) if (prior[e.uf]) ufs.push(resumoUF(e, prior[e.uf]));
  if (exterior && prior.ZZ) ufs.push(resumoUF(exterior, prior.ZZ));
  if (ufs.length < 20) return null;

  const nTot = ufs.reduce((a, u) => a + u.n, 0);
  const lTot = ufs.reduce((a, u) => a + u.L, 0);
  if (nTot <= 0) return { semDados: true };

  // deslocamento nacional observado (Lula 2º turno - prior), encolhido para 0 quando há poucos votos
  const desvio = ufs.reduce((a, u) => a + (u.n ? u.n * (u.L / u.n - u.q) : 0), 0);
  const fNac = ufs.reduce((a, u) => a + u.f * u.te, 0) / (ufs.reduce((a, u) => a + u.te, 0) || 1);
  // as primeiras urnas não representam o país: o deslocamento também só ganha peso conforme a fração apurada cresce
  const delta = (desvio / (nTot + N0_SWING)) * (fNac / (fNac + K_PESO));

  // total previsto de votos válidos por UF: mistura "contado / fração apurada" (cresce com f) e 1º turno
  const modelo = ufs.map((u) => {
    const proj = u.f > 0.02 && u.n ? u.n / u.f : u.vv1;
    const vTot = Math.max(u.n, u.f * proj + (1 - u.f) * u.vv1);
    const w = u.f / (u.f + K_PESO);
    const obs = u.n ? u.L / u.n : u.q;
    const m = w * obs + (1 - w) * clamp(u.q + delta, 0.02, 0.98);
    return { ...u, vTot, m, sd: SIGMA_UF * Math.sqrt(1 - u.f) };
  });

  const tau = TAU_PRIOR * Math.sqrt(1 - fNac);
  const z = rng(seed);
  const shares = new Float64Array(sims);
  let vitorias = 0;
  for (let i = 0; i < sims; i++) {
    const choque = z() * tau, comp = 1 + z() * SIGMA_COMP;
    let L = 0, V = 0;
    for (const u of modelo) {
      const falta = Math.max(0, u.vTot * (u.f > 0.999 ? 1 : (1 + (comp - 1) * (1 - u.f))) - u.n);
      const s = clamp(u.m + choque + z() * u.sd, 0, 1);
      L += u.L + falta * s;
      V += u.n + falta;
    }
    const share = V ? L / V : 0.5;
    shares[i] = share;
    if (share > 0.5) vitorias++;
  }
  shares.sort();
  const q = (p) => shares[Math.min(sims - 1, Math.floor(p * sims))];

  // número do "caminho": que fatia dos votos que faltam o Lula precisa para chegar a 50%
  const vTotal = modelo.reduce((a, u) => a + u.vTot, 0);
  const falta = Math.max(0, vTotal - nTot);
  const precisa = falta > 0 ? (0.5 * vTotal - lTot) / falta : null;

  const lulaAtual = lTot / nTot;
  return {
    chance: vitorias / sims,                 // 0..1
    final: { medio: q(0.5), p5: q(0.05), p95: q(0.95) }, // % final de Lula nos votos válidos (0..1)
    atual: lulaAtual,
    votosContados: nTot,
    votosFaltam: Math.round(falta),
    precisa,                                 // fração dos votos restantes que o Lula precisa (pode ser <0 ou >1)
    fracaoApurada: fNac,
    deslocamento: delta,
  };
}

// texto da chance: nunca mostra 0% ou 100% exatos (é estimativa)
function formataChance(c) {
  if (c == null) return '—';
  if (c >= 0.999) return '>99,9%';
  if (c <= 0.001) return '<0,1%';
  const pc = c * 100;
  return (pc >= 99 || pc <= 1 ? pc.toFixed(1) : pc.toFixed(0)).replace('.', ',') + '%';
}

const api = { calcula, formataChance };
if (typeof module !== 'undefined' && module.exports) module.exports = api;
else window.Chances = api;
})();
