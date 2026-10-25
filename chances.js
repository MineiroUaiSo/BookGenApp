// Chance de Lula vencer o 2º turno — modelo v2 (proposta). Universal: navegador (window.Chances) e Node (testes).
// É uma ESTIMATIVA do modelo, não um número do TSE. Mesma API do chances.js: calcula(D) e formataChance(c).
//
// Ideia: o que já foi contado é certo; a incerteza está só no que falta. Para cada UF (e o exterior):
//  1. "swing" observado = % de Lula (no duelo) na parte apurada MENOS a % de Lula no 1º turno NAS MESMAS urnas.
//     Com a composição por município (arquivos *-ab.json do TSE + tabela do 1º turno por município), "as mesmas urnas"
//     são os mesmos municípios, na proporção apurada de cada um. Sem ela, compara com o 1º turno da UF inteira e
//     trata a diferença de composição como ruído grande no começo (as primeiras urnas não representam a UF).
//  2. Modelo hierárquico (nacional -> região -> UF), bayesiano e conjugado: o swing de cada UF é o nacional + o da
//     região + o da UF; o prior é NEUTRO (swing 0 = mesmo duelo do 1º turno, com incerteza larga e simétrica).
//     Observações discrepantes perdem peso (verossimilhança t, por IRLS).
//  3. Comparecimento/votos válidos do 2º turno relativos ao 1º (razão por UF), também hierárquico.
//  4. % final = (votos já contados + votos que faltam × % prevista no que falta) / total previsto. A incerteza
//     (swing, composição, comparecimento) é propagada analiticamente e a cauda é t de Student (choques grandes).
//     Resultado determinístico: mesmo dado => mesma chance, sem ruído de simulação.
(function () {
'use strict';

const LULA = '13';
const FLAVIO = '22';
const P = {
  // prior do swing (pontos da fração de Lula no duelo, 1 = 100 pp). Centro 0 = neutro.
  TAU_N: 0.04,      // nacional (entre turnos o duelo já variou 2-7 pp no Brasil)
  TAU_R: 0.015,     // região
  TAU_U: 0.015,     // UF
  // ruído da observação SEM composição municipal: as urnas apuradas podem ser bem diferentes da UF
  // variância ~ (1-f)*(A_ST/seções_apuradas + C_ST): poucas seções => amostra muito "em bloco" (ajuste ao vivo, 25/10)
  A_ST: 0.2,        // ~14 pp com 10 seções, ~6 pp com 100, ~4 pp com 1.000+ (no começo)
  C_ST: 0.0015,
  A_COMP: 0.02,     // sem nº de seções: dp ~ A*sqrt((1-f)/(f+F0))
  F0: 0.1,
  A_COMUM: 0.02,    // parte desse viés comum a todas as UFs (ex.: capitais primeiro em todo lugar)
  S_XI_UF: 0.01,    // o que falta da UF difere do já apurado mesmo após o swing (sem composição)
  // ruído COM composição municipal
  S_MUN: 0.025,     // heterogeneidade do swing entre municípios
  S_DENTRO: 0.08,   // viés das primeiras seções de cada município ainda incompleto (medido ao vivo: dp ~9 pp com <20% apurado)
  A_COMUM_MUN: 0.04,// parte comum desse viés (ao vivo, 25/10: ~+2,5 a +3,5 pp nas primeiras seções)
  S_PISO: 0.003,
  NU_OBS: 2,        // robustez (Huber): acima de 2 desvios a observação perde peso; influência limitada e monotônica
  N_MIN: 300,       // abaixo disso (votos contados na UF) a parcial não informa o swing
  LAMBDA_K: 0,      // 0 = exposição ao viés comum igual em todas as UFs (monotônico); 1 = exposição própria de cada UF
  ROB_T: 0,         // 0 = Huber (monotônico); 1 = t
  NU: 5,            // cauda da distribuição final (t de Student)
  // comparecimento: razão (votos válidos do duelo no 2º turno) / (votos válidos no 1º turno), em log
  RHO0: Math.log(0.99), TAU_RHO_N: 0.03, TAU_RHO_R: 0.02, TAU_RHO_U: 0.015, A_RHO: 0.02,
};

const votosDe = (cands, n) => (cands || []).find((c) => String(c.numero) === n)?.votos || 0;
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const fin = (x, d = 0) => (Number.isFinite(x) ? x : d);

// ---------- álgebra linear pequena (n ~ 36) ----------
function cholesky(A, n) { // A simétrica positiva (Float64Array n*n) -> L triangular inferior
  const L = new Float64Array(n * n);
  for (let i = 0; i < n; i++) {
    for (let j = 0; j <= i; j++) {
      let s = A[i * n + j];
      for (let k = 0; k < j; k++) s -= L[i * n + k] * L[j * n + k];
      L[i * n + j] = i === j ? Math.sqrt(Math.max(s, 1e-300)) : s / L[j * n + j];
    }
  }
  return L;
}
function resolve(L, b, n) { // L L' x = b
  const y = new Float64Array(n);
  for (let i = 0; i < n; i++) { let s = b[i]; for (let k = 0; k < i; k++) s -= L[i * n + k] * y[k]; y[i] = s / L[i * n + i]; }
  const x = new Float64Array(n);
  for (let i = n - 1; i >= 0; i--) { let s = y[i]; for (let k = i + 1; k < n; k++) s -= L[k * n + i] * x[k]; x[i] = s / L[i * n + i]; }
  return x;
}

// Posterior gaussiano de um modelo linear: y_o = sum_j coef_oj * theta_j + e_o, e_o ~ N(0, v_o); theta ~ N(m0, diag(p0)).
// Robusto: reponderação t (IRLS) — uma UF com dado esquisito não arrasta o resto.
function posterior(n, m0, p0, obs, nuObs) {
  let v = obs.map((o) => o.v);
  let mu = Float64Array.from(m0), L = null;
  for (let it = 0; it < (nuObs ? 6 : 1); it++) {
    const A = new Float64Array(n * n), b = new Float64Array(n);
    for (let j = 0; j < n; j++) { A[j * n + j] = 1 / p0[j]; b[j] = m0[j] / p0[j]; }
    obs.forEach((o, k) => {
      const w = 1 / v[k];
      for (let a = 0; a < o.idx.length; a++) {
        const ia = o.idx[a], ca = o.coef[a];
        b[ia] += w * ca * o.y;
        for (let c = 0; c < o.idx.length; c++) A[ia * n + o.idx[c]] += w * ca * o.coef[c];
      }
    });
    L = cholesky(A, n);
    mu = resolve(L, b, n);
    if (!nuObs) break;
    v = obs.map((o) => {
      let pred = 0;
      for (let a = 0; a < o.idx.length; a++) if (o.coef[a] === 1 && a < 4) pred += mu[o.idx[a]]; // nacional+região+UF
      const vm = o.vMarg ?? o.v;
      const z = Math.abs(o.y - pred) / Math.sqrt(vm);
      if (P.ROB_T) return o.v + vm * Math.max(0, (nuObs + z * z) / (nuObs + 1) - 1); // t (influência redescendente)
      return o.v + vm * Math.max(0, z / nuObs - 1); // Huber: quem destoa mais que nuObs desvios perde peso (influência limitada)
    });
  }
  // covariância posterior = A^-1 (colunas por resolução)
  const cov = new Float64Array(n * n);
  for (let j = 0; j < n; j++) {
    const e = new Float64Array(n); e[j] = 1;
    const c = resolve(L, e, n);
    for (let i = 0; i < n; i++) cov[i * n + j] = c[i];
  }
  return { mu, cov };
}
const quad = (cov, a, n) => { let s = 0; for (let i = 0; i < n; i++) { if (!a[i]) continue; for (let j = 0; j < n; j++) s += a[i] * cov[i * n + j] * a[j]; } return s; };

// ---------- t de Student: CDF (beta incompleta regularizada) e quantil ----------
function lgamma(x) {
  const c = [76.18009172947146, -86.50532032941677, 24.01409824083091, -1.231739572450155, 0.1208650973866179e-2, -0.5395239384953e-5];
  let y = x, t = x + 5.5; t -= (x + 0.5) * Math.log(t);
  let s = 1.000000000190015; for (const k of c) s += k / ++y;
  return -t + Math.log(2.5066282746310005 * s / x);
}
function betacf(a, b, x) {
  let qab = a + b, qap = a + 1, qam = a - 1, c = 1, d = 1 - qab * x / qap;
  if (Math.abs(d) < 1e-30) d = 1e-30; d = 1 / d; let h = d;
  for (let m = 1; m <= 200; m++) {
    const m2 = 2 * m;
    let aa = m * (b - m) * x / ((qam + m2) * (a + m2));
    d = 1 + aa * d; if (Math.abs(d) < 1e-30) d = 1e-30; c = 1 + aa / c; if (Math.abs(c) < 1e-30) c = 1e-30; d = 1 / d; h *= d * c;
    aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2));
    d = 1 + aa * d; if (Math.abs(d) < 1e-30) d = 1e-30; c = 1 + aa / c; if (Math.abs(c) < 1e-30) c = 1e-30; d = 1 / d;
    const del = d * c; h *= del; if (Math.abs(del - 1) < 3e-16) break;
  }
  return h;
}
function ibeta(a, b, x) {
  if (x <= 0) return 0; if (x >= 1) return 1;
  const bt = Math.exp(lgamma(a + b) - lgamma(a) - lgamma(b) + a * Math.log(x) + b * Math.log(1 - x));
  return x < (a + 1) / (a + b + 2) ? bt * betacf(a, b, x) / a : 1 - bt * betacf(b, a, 1 - x) / b;
}
function tCdf(t, nu) {
  if (!Number.isFinite(t)) return t > 0 ? 1 : 0;
  const x = nu / (nu + t * t), p = 0.5 * ibeta(nu / 2, 0.5, x);
  return t > 0 ? 1 - p : p;
}
function tQuant(p, nu) { let lo = -60, hi = 60; for (let i = 0; i < 100; i++) { const m = (lo + hi) / 2; if (tCdf(m, nu) < p) lo = m; else hi = m; } return (lo + hi) / 2; }
const T95 = {}; const t95 = (nu) => (T95[nu] ??= tQuant(0.95, nu));

// ---------- composição municipal ----------
// mun: lista [te, est, vv1, L1, B1] por município (est = eleitores nas seções já totalizadas no 2º turno).
// estUF: eleitores apurados segundo o arquivo da UF (pode estar alguns segundos à frente/atrás do *-ab.json).
// Devolve o 1º turno da parte apurada (c) e da que falta (r), e as exposições ao viés "dentro do município":
//  xc = soma dos quadrados (parte independente), xl = média ponderada (parte comum); municípios grandes pesam mais.
function composicao(mun, estUF) {
  let te = 0, est = 0;
  for (const m of mun) { te += fin(m[0]); est += clamp(fin(m[1]), 0, fin(m[0])); }
  if (!(te > 0)) return null;
  const alvo = clamp(fin(estUF, est), 0, te);
  // arquivos de horários diferentes: ajusta a proporção apurada de cada município para fechar com o total da UF;
  // se a diferença for grande demais, a composição não é confiável e o modelo usa só a UF
  if (Math.abs(alvo - est) > 0.1 * te && Math.abs(alvo - est) > 0.5 * Math.max(est, alvo)) return null;
  const k = est > 0 ? alvo / est : 0;
  // qc/qr: fração de Lula no duelo do 1º turno, ponderada pelos votos válidos de cada município (o 2º turno tem
  // ~os mesmos válidos do 1º, então é assim que cada município pesa no que já foi e no que falta apurar)
  const r = { qc: 0, qr: 0, V1c: 0, V1r: 0, hc: 0, hr: 0, xc: 0, xl: 0 };
  for (const m of mun) {
    const tm = fin(m[0]); if (!(tm > 0)) continue;
    const w = clamp((clamp(fin(m[1]), 0, tm) * k) / tm, 0, 1);
    const V = fin(m[2]), c = w * V, rr = (1 - w) * V;
    const l = fin(m[3]), b = fin(m[4]), qm = l + b > 0 ? l / (l + b) : 0.5;
    r.qc += c * qm; r.V1c += c;
    r.qr += rr * qm; r.V1r += rr;
    r.hc += c * c; r.hr += rr * rr;
    const d = (1 - w) ** 3; // o viés das primeiras seções some rápido (medido ao vivo: ~0 a partir de 20-50% do município)
    r.xc += (c * d) ** 2; r.xl += c * d;
  }
  r.qc = r.V1c ? r.qc / r.V1c : null; r.qr = r.V1r ? r.qr / r.V1r : null;
  r.hc = r.V1c ? r.hc / r.V1c ** 2 : 0; r.hr = r.V1r ? r.hr / r.V1r ** 2 : 0;
  r.xc = r.V1c ? r.xc / r.V1c ** 2 : 0; r.xl = r.V1c ? r.xl / r.V1c : 0;
  return r;
}

// ---------- resumo por UF ----------
function resumoUF(e, p, mun) {
  const L = votosDe(e?.candidatos, LULA), B = votosDe(e?.candidatos, FLAVIO), n = L + B;
  const l1 = votosDe(p.candidatos, LULA), b1 = votosDe(p.candidatos, FLAVIO);
  const vv1 = (p.candidatos || []).reduce((a, c) => a + (c.votos || 0), 0);
  const te = fin(e?.contagem?.te) || fin(p.contagem?.te) || 0;
  const est = fin(e?.contagem?.est);
  const q = l1 + b1 ? l1 / (l1 + b1) : 0.5;
  // fração do eleitorado já apurada; sem `est` mas com votos, usa os votos contados como piso
  let f = clamp(est && te ? est / te : (n && vv1 ? n / vv1 : 0), 0, 1);
  if (n > 0 && f === 0) f = clamp(vv1 ? n / vv1 : 1, 0, 1);
  const st = Math.max(0, fin(e?.secoesTot));
  const base = { uf: p.uf, regiao: p.regiao || 'Exterior', L, B, n, q, vv1, f, te, st, soPrior: !e };
  const comp = mun && mun.length && e ? composicao(mun, est) : null;
  if (comp && comp.V1c + comp.V1r > 0) {
    const qc = comp.qc ?? q, qr = comp.qr ?? q;
    const escala = comp.V1c + comp.V1r > 0 ? vv1 / (comp.V1c + comp.V1r) : 1; // tabela municipal x total da UF
    return { ...base, modo: 'mun', qc, qr, V1c: comp.V1c * escala, V1r: comp.V1r * escala, hc: comp.hc, hr: comp.hr, xc: comp.xc, xl: comp.xl };
  }
  return { ...base, modo: 'uf', qc: q, qr: q, V1c: f * vv1, V1r: (1 - f) * vv1, hc: 0, hr: 0, xc: 0, xl: 0 };
}

/**
 * @param {object} D resultado de Apuracao.buscar() com D.insumos (2º turno). Opcional: D.insumos.municipios[UF] =
 *   [[te, est, vv1, L1, B1], ...] (eleitores, eleitores apurados no 2º turno, válidos/Lula/Flávio no 1º turno por município)
 * @returns {object|null} null se o modelo não se aplica (1º turno, sem prior)
 */
function calcula(D, opcoes = {}) {
  if (!D || !D.insumos || D.eleicao?.turno !== 2) return null;
  const { prior, exterior } = D.insumos;
  if (!prior) return null;
  const munPorUF = D.insumos.municipios || {};
  const porUf = Object.fromEntries((D.estados || []).map((e) => [e.uf, e]));
  const ufs = Object.keys(prior).map((uf) => resumoUF(uf === 'ZZ' ? exterior : porUf[uf], prior[uf], munPorUF[uf]));
  if (ufs.length < 20) return null;
  const soPrior = ufs.filter((u) => u.soPrior).map((u) => u.uf);
  const nTot = ufs.reduce((a, u) => a + u.n, 0);
  const lTot = ufs.reduce((a, u) => a + u.L, 0);
  if (nTot <= 0) return { semDados: true };
  const teTot = ufs.reduce((a, u) => a + u.te, 0) || 1;
  const fNac = ufs.reduce((a, u) => a + u.f * u.te, 0) / teTot;

  // Parâmetros (todos na fração de Lula no duelo): 0 swing nacional; 1 viés comum da parte apurada;
  // regiões; swing de cada UF; viés da parte apurada de cada UF (b). O swing vale para a UF toda; o viés b é só da
  // ordem de apuração: se a parte apurada é +b, a que falta é -b*(V1c/V1r) (o total da UF não depende da ordem).
  const regioes = [...new Set(ufs.map((u) => u.regiao))];
  const nr = regioes.length, nu = ufs.length;
  const iR = Object.fromEntries(regioes.map((r, i) => [r, 2 + i]));
  const iU = (i) => 2 + nr + i, iB = (i) => 2 + nr + nu + i;
  const n = 2 + nr + 2 * nu;
  const comp = (u) => Math.sqrt((1 - u.f) / (u.f + P.F0));
  // viés comum: mesma exposição para todas as UFs (média nacional), para que voto a mais para um candidato numa UF
  // nunca reduza a chance dele (monotonia); a exposição cai conforme a apuração avança
  const cont = ufs.filter((u) => u.n >= P.N_MIN);
  const pesoC = (m) => cont.filter((u) => u.modo === m).reduce((a, u) => a + u.V1c, 0);
  const xlNac = pesoC('mun') > 0 ? cont.filter((u) => u.modo === 'mun').reduce((a, u) => a + u.V1c * u.xl, 0) / pesoC('mun') : 0;
  const fUF = pesoC('uf') > 0 ? cont.filter((u) => u.modo === 'uf').reduce((a, u) => a + u.V1c * u.f, 0) / pesoC('uf') : fNac;
  const kMun = P.A_COMUM_MUN * xlNac, kUF = P.A_COMUM * Math.sqrt((1 - fUF) / (fUF + P.F0));
  const vies = ufs.map((u) => (u.modo === 'mun'
    ? { sb2: P.S_DENTRO ** 2 * u.xc, k: kMun + P.LAMBDA_K * (P.A_COMUM_MUN * u.xl - kMun), ve: P.S_MUN ** 2 * u.hc * (1 - u.f) + P.S_PISO ** 2 }
    : { sb2: u.st > 0 ? (1 - u.f) * (P.A_ST / u.st + P.C_ST) : (P.A_COMP * comp(u)) ** 2, k: kUF + P.LAMBDA_K * (P.A_COMUM * comp(u) - kUF), ve: P.S_PISO ** 2 }));

  // ---- swing (fração de Lula no duelo: 2º turno - 1º turno nas mesmas urnas) ----
  const m0 = new Float64Array(n), p0 = new Float64Array(n);
  p0[0] = P.TAU_N ** 2; p0[1] = 1;
  regioes.forEach((r) => (p0[iR[r]] = P.TAU_R ** 2));
  ufs.forEach((u, i) => { p0[iU(i)] = P.TAU_U ** 2; p0[iB(i)] = Math.max(vies[i].sb2, 1e-10); });
  const obs = [];
  ufs.forEach((u, i) => {
    if (!(u.n >= P.N_MIN)) return;
    obs.push({ idx: [0, 1, iR[u.regiao], iU(i), iB(i)], coef: [1, vies[i].k, 1, 1, 1], y: u.L / u.n - u.qc, v: vies[i].ve, vMarg: vies[i].ve + vies[i].sb2 + vies[i].k ** 2 });
  });
  const S = posterior(n, m0, p0, obs, P.NU_OBS);

  // ---- comparecimento (log da razão de votos válidos do duelo 2º turno / válidos 1º turno) ----
  const r0 = new Float64Array(n), rp = new Float64Array(n).fill(1e-10);
  r0[0] = P.RHO0; rp[0] = P.TAU_RHO_N ** 2;
  regioes.forEach((r) => (rp[iR[r]] = P.TAU_RHO_R ** 2));
  ufs.forEach((_, i) => (rp[iU(i)] = P.TAU_RHO_U ** 2));
  const obsR = [];
  ufs.forEach((u, i) => {
    if (!(u.n >= P.N_MIN) || !(u.V1c > 0)) return;
    const y = Math.log(u.n / u.V1c);
    if (!Number.isFinite(y)) return;
    const v = u.modo === 'mun' ? vies[i].ve + vies[i].sb2 + vies[i].k ** 2 : (P.A_RHO * comp(u)) ** 2 + P.S_PISO ** 2;
    obsR.push({ idx: [0, iR[u.regiao], iU(i)], coef: [1, 1, 1], y, v, vMarg: v });
  });
  const R = posterior(n, r0, rp, obsR, P.NU_OBS);

  // ---- projeção do que falta ----
  const proj = ufs.map((u, i) => {
    const rho = u.V1r > 0 ? u.V1c / u.V1r : 0;         // fator de população finita
    const lr = R.mu[0] + R.mu[iR[u.regiao]] + R.mu[iU(i)];
    const falta = u.f >= 1 ? 0 : Math.max(0, u.V1r * Math.exp(lr));
    const sw = S.mu[0] + S.mu[iR[u.regiao]] + S.mu[iU(i)] - rho * (vies[i].k * S.mu[1] + S.mu[iB(i)]);
    const s = clamp(u.qr + sw, 0.005, 0.995);
    const xi2 = u.modo === 'mun' ? P.S_MUN ** 2 * u.hr : P.S_XI_UF ** 2;
    return { i, regiao: u.regiao, rho, k: vies[i].k, s, falta, xi2 };
  });
  const faltaTot = proj.reduce((a, u) => a + u.falta, 0);
  const V = nTot + faltaTot;
  const medio = (lTot + proj.reduce((a, u) => a + u.falta * u.s, 0)) / V;
  // variância (linearização): swing e vieses (covariância posterior completa), idiossincrasia do que falta, comparecimento
  const aS = new Float64Array(n), aR = new Float64Array(n);
  let vXi = 0;
  for (const u of proj) {
    if (!(u.falta > 0)) continue;
    const wS = u.falta / V, wR = (u.falta * (u.s - medio)) / V;
    aS[0] += wS; aS[iR[u.regiao]] += wS; aS[iU(u.i)] += wS;
    aS[1] -= wS * u.rho * u.k; aS[iB(u.i)] -= wS * u.rho;
    aR[0] += wR; aR[iR[u.regiao]] += wR; aR[iU(u.i)] += wR;
    vXi += wS * wS * u.xi2;
  }
  const sd = Math.sqrt(Math.max(0, quad(S.cov, aS, n) + vXi + quad(R.cov, aR, n)));
  const chance = sd > 1e-12 ? 1 - tCdf((0.5 - medio) / sd, P.NU) : medio > 0.5 ? 1 : medio < 0.5 ? 0 : 0.5;
  const t = t95(P.NU);
  const falta = Math.max(0, V - nTot);
  return {
    chance,                                   // 0..1 (a de Flávio é 1 - chance)
    final: { medio, p5: clamp(medio - t * sd, 0, 1), p95: clamp(medio + t * sd, 0, 1) },
    atual: lTot / nTot,
    votosContados: nTot,
    votosFaltam: Math.round(falta),
    precisa: falta > 0 ? (0.5 * V - lTot) / falta : null,
    fracaoApurada: fNac,
    deslocamento: S.mu[0],                    // swing nacional estimado (fração de Lula no duelo, 2º - 1º turno)
    soPrior,
    incerteza: sd,                            // desvio (escala da t) da % final
    modo: ufs.some((u) => u.modo === 'mun') ? 'municipal' : 'uf',
  };
}

// texto da chance com 2 casas decimais; nunca mostra 0% ou 100% exatos (é estimativa)
function formataChance(c) {
  if (c == null || !Number.isFinite(c)) return '—';
  if (c >= 0.9999) return '>99,99%';
  if (c <= 0.0001) return '<0,01%';
  return (c * 100).toFixed(2).replace('.', ',') + '%';
}

// rótulo honesto da situação (simétrico: serve para os dois candidatos)
function rotulo(r) {
  if (!r || r.chance == null) return null;
  const c = Math.max(r.chance, 1 - r.chance), quem = r.chance >= 0.5 ? 'Lula' : 'Flávio Bolsonaro';
  const inicio = r.fracaoApurada < 0.05;
  let txt;
  if (c < 0.6) txt = 'Indefinido';
  else if (c < 0.75) txt = `Leve vantagem de ${quem}`;
  else if (c < 0.9) txt = `Vantagem de ${quem}`;
  else if (c < 0.99) txt = `Vantagem clara de ${quem}`;
  else if (c < 0.999) txt = `${quem} muito provável vencedor`;
  else txt = `Vitória de ${quem} praticamente garantida`;
  if (inicio && c >= 0.6) txt += ' (início da apuração: pode mudar muito)';
  return { texto: txt, nivel: c < 0.6 ? 0 : c < 0.75 ? 1 : c < 0.9 ? 2 : c < 0.99 ? 3 : 4, inicio };
}

const api = { calcula, formataChance, rotulo, composicao, _P: P, _tCdf: tCdf };
if (typeof module !== 'undefined' && module.exports) module.exports = api;
else window.Chances = api;
})();
