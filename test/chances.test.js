// Testes do chances_v2.js: os mesmos de test/chances.test.js (adaptados às 2 casas decimais) + neutralidade,
// composição municipal, robustez e rótulos. Rodar: node --test test2/chances_v2.test.js
const test = require('node:test');
const assert = require('node:assert');
const { calcula, formataChance, rotulo, composicao } = require('../public/chances.js');

const UFS = ['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'];
const cands = (l, b) => [{ numero: '13', votos: l }, { numero: '22', votos: b }];
// cenário: cada UF com 1.000.000 de eleitores, 1º turno com Lula em share1 do duelo, apuração fração f com Lula em shareObs
function cenario({ f, shareObs, share1 = 0.5 }) {
  const te = 1_000_000;
  const estados = UFS.map((uf) => {
    const n = Math.round(te * 0.8 * f);
    return { uf, candidatos: cands(Math.round(n * shareObs), n - Math.round(n * shareObs)), contagem: { te, est: Math.round(te * f), esnt: te - Math.round(te * f), c: n } };
  });
  const prior = Object.fromEntries(UFS.map((uf) => [uf, { uf, candidatos: cands(Math.round(800_000 * share1), 800_000 - Math.round(800_000 * share1)), contagem: { te } }]));
  return { eleicao: { turno: 2 }, estados, insumos: { prior, exterior: null } };
}
const troca = (D) => {
  const sw = (cs) => (cs || []).map((c) => ({ ...c, numero: c.numero === '13' ? '22' : c.numero === '22' ? '13' : c.numero }));
  const prior = Object.fromEntries(Object.entries(D.insumos.prior).map(([k, v]) => [k, { ...v, candidatos: sw(v.candidatos) }]));
  const municipios = D.insumos.municipios && Object.fromEntries(Object.entries(D.insumos.municipios).map(([k, a]) => [k, a.map(([te, est, vv, L, B]) => [te, est, vv, B, L])]));
  return { ...D, estados: D.estados.map((e) => ({ ...e, candidatos: sw(e.candidatos) })), insumos: { ...D.insumos, prior, exterior: D.insumos.exterior && { ...D.insumos.exterior, candidatos: sw(D.insumos.exterior.candidatos) }, ...(municipios ? { municipios } : {}) } };
};

// ---- os testes originais ----
test('1º turno ou sem prior: modelo não se aplica', () => {
  assert.equal(calcula({ eleicao: { turno: 1 }, estados: [] }), null);
  assert.equal(calcula({ eleicao: { turno: 2 }, estados: [], insumos: null }), null);
});
test('é determinístico (mesmo dado, mesma chance)', () => {
  const d = cenario({ f: 0.3, shareObs: 0.52 });
  assert.equal(calcula(d).chance, calcula(d).chance);
});
test('começo da apuração não dispara: 60% de Lula com 1% apurado ainda fica longe de 100%', () => {
  const r = calcula(cenario({ f: 0.01, shareObs: 0.6 }));
  assert.ok(r.chance > 0.4 && r.chance < 0.9, `chance ${r.chance}`);
});
test('mais Lula na apuração => mais chance (monotônico)', () => {
  const c = [0.47, 0.5, 0.53, 0.56].map((s) => calcula(cenario({ f: 0.6, shareObs: s })).chance);
  for (let i = 1; i < c.length; i++) assert.ok(c[i] >= c[i - 1], c.join());
});
test('apuração avançada com folga decide: Lula 54% com 90% apurado => ~100%; 46% => ~0%', () => {
  assert.ok(calcula(cenario({ f: 0.9, shareObs: 0.54 })).chance > 0.99);
  assert.ok(calcula(cenario({ f: 0.9, shareObs: 0.46 })).chance < 0.01);
});
test('apuração completa não tem incerteza', () => {
  assert.equal(calcula(cenario({ f: 1, shareObs: 0.51 })).chance, 1);
  assert.equal(calcula(cenario({ f: 1, shareObs: 0.49 })).chance, 0);
});
test('"precisa" bate com a conta: share atual igual a 50% => precisa ≈ 50% do que falta', () => {
  const r = calcula(cenario({ f: 0.5, shareObs: 0.5 }));
  assert.ok(Math.abs(r.precisa - 0.5) < 0.03, r.precisa);
});
test('apuração completa converge com exterior presente no 1º e no 2º turno', () => {
  const d = cenario({ f: 1, shareObs: 0.51 });
  const ext = (te, est) => ({ uf: 'ZZ', candidatos: cands(150_000, 150_000), contagem: { te, est } });
  d.insumos.prior.ZZ = ext(900_000);
  d.insumos.exterior = ext(900_000, 900_000);
  assert.equal(calcula(d).chance, 1);
});
test('formataChance(NaN) não mostra NaN', () => {
  assert.equal(formataChance(NaN), '—');
});
test('formataChance: 2 casas decimais e nunca 0% ou 100% exatos', () => {
  assert.equal(formataChance(1), '>99,99%');
  assert.equal(formataChance(0), '<0,01%');
  assert.equal(formataChance(0.473), '47,30%');
  assert.equal(formataChance(0.5002), '50,02%');
  assert.equal(formataChance(0.995), '99,50%');
  assert.equal(formataChance(0.99996), '>99,99%');
});

// ---- neutralidade ----
test('neutro: trocar os candidatos dá exatamente a chance complementar (UF e municipal)', () => {
  for (const [f, s, s1] of [[0.02, 0.55, 0.48], [0.3, 0.49, 0.5], [0.7, 0.505, 0.47], [0.95, 0.499, 0.52]]) {
    const d = cenario({ f, shareObs: s, share1: s1 });
    const a = calcula(d), b = calcula(troca(d));
    assert.ok(Math.abs(a.chance + b.chance - 1) < 1e-9, `${a.chance} + ${b.chance}`);
    assert.ok(Math.abs(a.final.medio + b.final.medio - 1) < 1e-9);
  }
});
test('neutro: sem swing nenhum e 1º turno empatado, a chance é 50%', () => {
  const r = calcula(cenario({ f: 0.3, shareObs: 0.5, share1: 0.5 }));
  assert.ok(Math.abs(r.chance - 0.5) < 1e-9, r.chance);
});

// ---- composição municipal ----
// Cada UF tem 2 "municípios": capital (40% do eleitorado, Lula 65% no 1º turno) e interior (Lula 40%).
// No 2º turno NADA muda (swing 0), mas a capital apura primeiro: a parcial parece um swing enorme pró-Lula.
function cenarioMun({ fCap, fInt, swing = 0 }) {
  const teC = 400_000, teI = 600_000, vvC = 320_000, vvI = 480_000;
  const qC = 0.65, qI = 0.4;
  const mun = {}, estados = [], prior = {};
  for (const uf of UFS) {
    const L1 = Math.round(vvC * qC) + Math.round(vvI * qI);
    prior[uf] = { uf, candidatos: cands(L1, vvC + vvI - L1), contagem: { te: teC + teI } };
    const nC = Math.round(vvC * fCap), nI = Math.round(vvI * fInt);
    const L = Math.round(nC * (qC + swing)) + Math.round(nI * (qI + swing));
    estados.push({ uf, candidatos: cands(L, nC + nI - L), contagem: { te: teC + teI, est: Math.round(teC * fCap + teI * fInt) } });
    mun[uf] = [[teC, teC * fCap, vvC, Math.round(vvC * qC), vvC - Math.round(vvC * qC)], [teI, teI * fInt, vvI, Math.round(vvI * qI), vvI - Math.round(vvI * qI)]];
  }
  return { eleicao: { turno: 2 }, estados, insumos: { prior, exterior: null, municipios: mun } };
}
test('composição: capital apurando primeiro não vira "swing" quando há dado por município', () => {
  const d = cenarioMun({ fCap: 0.5, fInt: 0.05 });
  const semMun = calcula({ ...d, insumos: { ...d.insumos, municipios: undefined } });
  const comMun = calcula(d);
  assert.equal(comMun.modo, 'municipal');
  assert.equal(semMun.modo, 'uf');
  // a parcial está bem acima de 50%, mas o resultado final (sem swing) é 50%: o municipal sabe disso
  assert.ok(semMun.atual > 0.58, `atual ${semMun.atual}`);
  assert.ok(Math.abs(comMun.final.medio - 0.5) < 0.01, `medio municipal ${comMun.final.medio}`);
  assert.ok(Math.abs(comMun.deslocamento) < 0.01, `swing municipal ${comMun.deslocamento}`);
  assert.ok(semMun.final.medio > comMun.final.medio, 'sem composição o modelo é puxado pela capital');
});
test('composição: com swing real de +3 pp, o municipal o encontra', () => {
  const r = calcula(cenarioMun({ fCap: 0.6, fInt: 0.3, swing: 0.03 }));
  assert.ok(r.final.medio > 0.52 && r.final.medio < 0.54, `medio ${r.final.medio}`);
  assert.ok(r.chance > 0.9, `chance ${r.chance}`);
});
test('composição: municipal também é neutro (troca de candidatos)', () => {
  const d = cenarioMun({ fCap: 0.5, fInt: 0.1, swing: 0.01 });
  const a = calcula(d), b = calcula(troca(d));
  assert.ok(Math.abs(a.chance + b.chance - 1) < 1e-9, `${a.chance} + ${b.chance}`);
});
test('composição incoerente com o arquivo da UF (horários diferentes) => usa só a UF', () => {
  const d = cenarioMun({ fCap: 0.5, fInt: 0.05 });
  d.insumos.municipios.SP = d.insumos.municipios.SP.map((m) => [m[0], 0, m[2], m[3], m[4]]); // ab.json "atrasado": nada apurado
  const comp = composicao(d.insumos.municipios.SP, d.estados.find((e) => e.uf === 'SP').contagem.est);
  assert.equal(comp, null);
  assert.ok(Number.isFinite(calcula(d).chance));
});
test('apuração completa no modo municipal também não tem incerteza', () => {
  const d = cenarioMun({ fCap: 1, fInt: 1, swing: 0.001 });
  assert.equal(calcula(d).chance, 1);
});

// ---- robustez ----
test('uma UF com dado esquisito (6 votos, 100% Lula) quase não mexe na chance', () => {
  const d = cenario({ f: 0.2, shareObs: 0.5, share1: 0.5 });
  const base = calcula(d).chance;
  const e = d.estados.find((x) => x.uf === 'RR');
  e.candidatos = cands(6, 0); e.contagem.est = 10;
  const r = calcula(d).chance;
  assert.ok(Math.abs(r - base) < 0.05, `${base} -> ${r}`);
});
test('UF ausente entra pelo prior e é listada', () => {
  const d = cenario({ f: 0.4, shareObs: 0.52 });
  d.estados = d.estados.filter((e) => e.uf !== 'SP');
  const r = calcula(d);
  assert.deepEqual(r.soPrior, ['SP']);
  assert.ok(r.chance > 0 && r.chance < 1);
});
test('quantis em ordem e dentro de 0..1', () => {
  for (const f of [0.01, 0.2, 0.6, 0.99]) {
    const r = calcula(cenario({ f, shareObs: 0.51, share1: 0.49 }));
    assert.ok(r.final.p5 <= r.final.medio && r.final.medio <= r.final.p95);
    assert.ok(r.final.p5 >= 0 && r.final.p95 <= 1);
  }
});

// ---- rótulos ----
test('rótulo é simétrico e avisa o começo da apuração', () => {
  assert.equal(rotulo({ chance: 0.55, fracaoApurada: 0.3 }).texto, 'Indefinido');
  assert.equal(rotulo({ chance: 0.7, fracaoApurada: 0.3 }).texto, 'Leve vantagem de Lula');
  assert.equal(rotulo({ chance: 0.3, fracaoApurada: 0.3 }).texto, 'Leve vantagem de Flávio Bolsonaro');
  assert.equal(rotulo({ chance: 0.95, fracaoApurada: 0.5 }).texto, 'Vantagem clara de Lula');
  assert.match(rotulo({ chance: 0.8, fracaoApurada: 0.02 }).texto, /início da apuração/);
  assert.equal(rotulo({ chance: 0.0005, fracaoApurada: 0.97 }).texto, 'Vitória de Flávio Bolsonaro praticamente garantida');
});
