const test = require('node:test');
const assert = require('node:assert');
const { calcula, formataChance } = require('../public/chances.js');

const UFS = ['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'];
const cands = (l, b) => [{ numero: '13', votos: l }, { numero: '22', votos: b }];
// monta um cenário: cada UF com 1.000.000 de eleitores, 1º turno 50/50 e apuração fração f com Lula em shareObs
function cenario({ f, shareObs, share1 = 0.5 }) {
  const te = 1_000_000;
  const estados = UFS.map((uf) => {
    const n = Math.round(te * 0.8 * f);
    return { uf, candidatos: cands(Math.round(n * shareObs), n - Math.round(n * shareObs)), contagem: { te, est: Math.round(te * f), esnt: te - Math.round(te * f), c: n } };
  });
  const prior = Object.fromEntries(UFS.map((uf) => [uf, { uf, candidatos: cands(Math.round(800_000 * share1), 800_000 - Math.round(800_000 * share1)), contagem: { te } }]));
  return { eleicao: { turno: 2 }, estados, insumos: { prior, exterior: null } };
}

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

test('formataChance nunca mostra 0% ou 100% exatos', () => {
  assert.equal(formataChance(1), '>99,9%');
  assert.equal(formataChance(0), '<0,1%');
  assert.equal(formataChance(0.473), '47%');
  assert.equal(formataChance(0.995), '99,5%');
});
