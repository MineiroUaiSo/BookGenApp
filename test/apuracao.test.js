// Testes sem rede: usam arquivos reais do TSE em test/fixtures e stub de fetch.
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { num, normalizaUF, agrega, descobrirEleicao, _reset } = require('../lib/apuracao.js');

const fx = (n) => require(path.join(__dirname, 'fixtures', n));
const sp = fx('sp-u.json');
const ac = fx('ac-u.json');
const br = fx('br-u.json');
const eleC = fx('ele-c.json');
const UFS = ['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'];

test('num converte formatos do TSE', () => {
  assert.equal(num('3,07'), 3.07);
  assert.equal(num('103656'), 103656);
  assert.equal(num('1.234.567'), 1234567);
  assert.equal(num(''), null);
  assert.equal(num(null), null);
  assert.equal(num(12), 12);
});

test('normalizaUF(SP) lê candidatos e seções da fixture', () => {
  const r = normalizaUF('SP', sp);
  assert.equal(r.candidatos.length, 12);
  const c = r.candidatos.find((x) => String(x.numero) === '22');
  assert.equal(c.nome, 'FLAVIO BOLSONARO');
  assert.equal(c.partido, 'PL');
  assert.equal(c.votos, 426265);
  assert.equal(r.pst, num(sp.s.pst));
  assert.equal(r.secoes, num(sp.s.ts));
  assert.equal(r.secoesTot, num(sp.s.st));
  assert.equal(r.nome, 'São Paulo');
  assert.equal(r.regiao, 'Sudeste');
});

test('normalizaUF tolera dados parciais', () => {
  const { carg } = sp;
  assert.equal(normalizaUF('SP', { carg }).pst, 0);
  assert.deepEqual(normalizaUF('SP', { s: sp.s }).candidatos, []);
  assert.equal(normalizaUF('SP', { carg, s: { ts: '100', st: '0' } }).pst, 0);
});

const todos = (mapa) => UFS.map((uf) => normalizaUF(uf, mapa[uf] || {}));

test('agrega com SP e AC reais e demais UFs vazias', () => {
  const { regioes, estados, brasil } = agrega(todos({ SP: sp, AC: ac }));
  assert.equal(regioes.length, 5);
  assert.equal(estados.length, 27);
  const sudeste = regioes.find((r) => r.nome === 'Sudeste');
  const votosSP = normalizaUF('SP', sp).candidatos.reduce((a, c) => a + c.votos, 0);
  assert.equal(sudeste.votosValidos, votosSP);
  for (const r of [...regioes, brasil]) {
    const soma = r.candidatos.reduce((a, c) => a + c.pct, 0);
    if (r.votosValidos) assert.ok(Math.abs(soma - 100) <= 0.01, `${r.nome} soma ${soma}`);
    else assert.equal(soma, 0);
  }
  const rr = estados.find((e) => e.uf === 'RR');
  assert.deepEqual(rr.candidatos, []);
});

test('pst da região = Σst/Σts quando todas as UFs têm seções', () => {
  const mapa = {};
  UFS.forEach((uf, i) => (mapa[uf] = i % 2 ? sp : ac));
  const { regioes } = agrega(todos(mapa));
  for (const r of regioes) {
    const es = r.ufs.map((uf) => mapa[uf]);
    const esperado = (es.reduce((a, d) => a + num(d.s.st), 0) / es.reduce((a, d) => a + num(d.s.ts), 0)) * 100;
    assert.ok(Math.abs(r.pst - esperado) < 1e-9, r.nome);
  }
});

// fetch stubado por URL
function stubFetch(rotas) {
  const original = globalThis.fetch;
  globalThis.fetch = async (url) => {
    const k = Object.keys(rotas).find((p) => String(url).includes(p));
    if (!k || rotas[k] == null) return { ok: false, status: 404, json: async () => ({}) };
    return { ok: true, status: 200, json: async () => rotas[k] };
  };
  return () => { globalThis.fetch = original; };
}
const comSt = (st) => ({ ...br, s: { ...br.s, st } });
const CFG = 'comum/config/ele-c.json';

test('descobrirEleicao: 2º turno 404 => 1º turno (6257)', async () => {
  _reset();
  const un = stubFetch({ [CFG]: eleC, '/6257/': br, '/6258/': null });
  try { assert.equal((await descobrirEleicao()).id, '6257'); } finally { un(); }
});

test('descobrirEleicao: 2º turno sem seções totalizadas => 6257', async () => {
  _reset();
  const un = stubFetch({ [CFG]: eleC, '/6257/': br, '/6258/': comSt('0') });
  try { assert.equal((await descobrirEleicao()).id, '6257'); } finally { un(); }
});

test('descobrirEleicao: 2º turno com seções totalizadas => 6258', async () => {
  _reset();
  const un = stubFetch({ [CFG]: eleC, '/6257/': br, '/6258/': comSt('5') });
  try { assert.equal((await descobrirEleicao()).id, '6258'); } finally { un(); }
});

test('descobrirEleicao: config sem ele2026 => erro', async () => {
  _reset();
  const un = stubFetch({ [CFG]: { pl: eleC.pl.filter((p) => p.c !== 'ele2026') } });
  try { await assert.rejects(descobrirEleicao(), /não está na configuração/); } finally { un(); }
});

test('descobrirEleicao: tudo 404 => erro 503', async () => {
  _reset();
  const un = stubFetch({ [CFG]: eleC, '/6257/': null, '/6258/': null });
  try { await assert.rejects(descobrirEleicao(), (e) => e.status === 503); } finally { un(); }
});
