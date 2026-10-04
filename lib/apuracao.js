// Busca e normaliza os dados oficiais do TSE (usado pelo servidor local e pela função da Vercel).

const ANO = process.env.ELEICAO_ANO || '2026';
const CARGO = process.env.CARGO || '0001'; // 0001 = Presidente
const TTL_MS = 20_000;
const BASE = 'https://resultados.tse.jus.br/oficial';

// Pode fixar o código da eleição (ex.: ELEICAO_ID=544 em 2022 1º turno). Se vazio, descobre sozinho.
let eleicaoId = process.env.ELEICAO_ID || null;

const REGIOES = {
  Norte: ['AC', 'AM', 'AP', 'PA', 'RO', 'RR', 'TO'],
  Nordeste: ['AL', 'BA', 'CE', 'MA', 'PB', 'PE', 'PI', 'RN', 'SE'],
  'Centro-Oeste': ['DF', 'GO', 'MS', 'MT'],
  Sudeste: ['ES', 'MG', 'RJ', 'SP'],
  Sul: ['PR', 'RS', 'SC'],
};
const NOMES = {
  AC: 'Acre', AL: 'Alagoas', AP: 'Amapá', AM: 'Amazonas', BA: 'Bahia', CE: 'Ceará', DF: 'Distrito Federal',
  ES: 'Espírito Santo', GO: 'Goiás', MA: 'Maranhão', MT: 'Mato Grosso', MS: 'Mato Grosso do Sul',
  MG: 'Minas Gerais', PA: 'Pará', PB: 'Paraíba', PR: 'Paraná', PE: 'Pernambuco', PI: 'Piauí',
  RJ: 'Rio de Janeiro', RN: 'Rio Grande do Norte', RS: 'Rio Grande do Sul', RO: 'Rondônia', RR: 'Roraima',
  SC: 'Santa Catarina', SP: 'São Paulo', SE: 'Sergipe', TO: 'Tocantins',
};
// Eleitorado aproximado (milhares) — só usado como peso se o TSE não informar o total de seções.
const ELEITORADO = {
  AC: 590, AL: 2370, AP: 570, AM: 2650, BA: 11000, CE: 6700, DF: 2200, ES: 2900, GO: 5000, MA: 4900,
  MT: 2500, MS: 2000, MG: 16400, PA: 5900, PB: 3000, PR: 8400, PE: 7200, PI: 2500, RJ: 12700, RN: 2500,
  RS: 8500, RO: 1200, RR: 370, SC: 5400, SP: 34600, SE: 1700, TO: 1100,
};
const regiaoDe = {};
for (const [r, ufs] of Object.entries(REGIOES)) ufs.forEach((u) => (regiaoDe[u] = r));
const UFS = Object.keys(NOMES);

// "48,43" / "1.234.567" / 12 -> número
const num = (v) => {
  if (v == null || v === '') return null;
  if (typeof v === 'number') return v;
  const n = parseFloat(String(v).replace(/\./g, '').replace(',', '.'));
  return Number.isFinite(n) ? n : null;
};

async function getJson(url, timeoutMs = 15_000) {
  const res = await fetch(url, { signal: AbortSignal.timeout(timeoutMs), headers: { 'user-agent': 'apuracao-por-regiao/1.0' } });
  if (!res.ok) throw new Error(`HTTP ${res.status} em ${url}`);
  return res.json();
}

const idStr = (id) => String(id).padStart(6, '0');
const urlUF = (id, uf) => {
  const u = uf.toLowerCase();
  return `${BASE}/ele${ANO}/${id}/dados-simplificados/${u}/${u}-c${CARGO}-e${idStr(id)}-r.json`;
};

// Descobre o código da eleição: testa números de 3 dígitos presentes na configuração oficial.
async function descobrirEleicao() {
  if (eleicaoId) return eleicaoId;
  const cfg = JSON.stringify(await getJson(`${BASE}/comum/config/ele-c.json`));
  const candidatos = [...new Set([...cfg.matchAll(/"(\d{3,4})"/g)].map((m) => m[1]))];
  for (const id of candidatos) {
    try {
      const d = await getJson(urlUF(id, 'BR'), 8000);
      if (d && (d.carg !== undefined || d.cand !== undefined)) { eleicaoId = id; return id; }
    } catch { /* tenta o próximo */ }
  }
  throw new Error(`Não achei a eleição ${ANO} no TSE (defina ELEICAO_ID).`);
}

function normalizaUF(uf, d) {
  const carg = Array.isArray(d.carg) ? d.carg.find((c) => String(c.cd).replace(/^0+/, '') === String(CARGO).replace(/^0+/, '')) || d.carg[0] : d;
  const cands = ((carg && carg.cand) || d.cand || []).map((c) => ({
    numero: c.n, nome: c.nm || c.nv, partido: c.cc || c.sg || '', votos: num(c.vap) || 0,
  }));
  const sec = d.s && typeof d.s === 'object' ? d.s : d;
  let secoes = num(sec.ts ?? d.ts ?? (typeof d.s !== 'object' ? d.s : null));
  let secoesTot = num(sec.st ?? d.st);
  let pst = num(d.pst ?? sec.pst);
  if (pst == null && secoes && secoesTot != null) pst = (secoesTot / secoes) * 100;
  if (secoes && secoesTot == null && pst != null) secoesTot = Math.round((secoes * pst) / 100);
  return { uf, nome: NOMES[uf], regiao: regiaoDe[uf], pst: pst ?? 0, secoes, secoesTot, peso: secoes || ELEITORADO[uf], candidatos: cands };
}

function agrega(estados) {
  const soma = (arr, f) => arr.reduce((a, e) => a + f(e), 0);
  const pctPonderado = (arr) => {
    if (arr.every((e) => e.secoes)) return (soma(arr, (e) => e.secoesTot ?? 0) / soma(arr, (e) => e.secoes)) * 100;
    const pesos = soma(arr, (e) => ELEITORADO[e.uf]);
    return soma(arr, (e) => e.pst * ELEITORADO[e.uf]) / pesos;
  };
  const candidatos = (arr) => {
    const m = new Map();
    for (const e of arr) for (const c of e.candidatos) {
      const k = c.numero;
      m.set(k, { ...(m.get(k) || { numero: c.numero, nome: c.nome, partido: c.partido, votos: 0 }), votos: (m.get(k)?.votos || 0) + c.votos });
    }
    const lista = [...m.values()].sort((a, b) => b.votos - a.votos);
    const total = soma(lista, (c) => c.votos);
    return lista.map((c) => ({ ...c, pct: total ? (c.votos / total) * 100 : 0 }));
  };
  const regioes = Object.keys(REGIOES).map((nome) => {
    const es = estados.filter((e) => e.regiao === nome);
    return { nome, pst: pctPonderado(es), votosValidos: soma(es, (e) => soma(e.candidatos, (c) => c.votos)), candidatos: candidatos(es), ufs: es.map((e) => e.uf) };
  });
  const brasil = { pst: pctPonderado(estados), votosValidos: soma(estados, (e) => soma(e.candidatos, (c) => c.votos)), candidatos: candidatos(estados) };
  for (const e of estados) {
    const tot = soma(e.candidatos, (c) => c.votos);
    e.candidatos = e.candidatos.sort((a, b) => b.votos - a.votos).map((c) => ({ ...c, pct: tot ? (c.votos / tot) * 100 : 0 }));
  }
  return { brasil, regioes, estados };
}

async function buscaTSE() {
  const id = await descobrirEleicao();
  const resultados = await Promise.allSettled(UFS.map(async (uf) => normalizaUF(uf, await getJson(urlUF(id, uf)))));
  const estados = [];
  const falhas = [];
  resultados.forEach((r, i) => (r.status === 'fulfilled' ? estados.push(r.value) : falhas.push(`${UFS[i]}: ${r.reason.message}`)));
  if (estados.length < UFS.length) {
    if (!estados.length) throw new Error(falhas[0]);
  }
  return { fonte: 'TSE', eleicao: { ano: ANO, id }, atualizadoEm: new Date().toISOString(), falhas, ...agrega(estados) };
}

// Dados fictícios só para testar a interface (/api/apuracao?demo=1).
function demo() {
  const seed = Math.floor(Date.now() / 20000);
  const rnd = (i) => { const x = Math.sin(seed * 31 + i * 12.9898) * 43758.5453; return x - Math.floor(x); };
  const nomes = [['13', 'Candidato A'], ['22', 'Candidato B'], ['12', 'Candidato C'], ['15', 'Candidato D']];
  const estados = UFS.map((uf, i) => {
    const pst = Math.min(100, 20 + ((seed % 40) * 2) + rnd(i) * 45);
    const base = ELEITORADO[uf] * 1000 * 0.78 * (pst / 100);
    const secoes = Math.round(ELEITORADO[uf] * 2.9);
    const w = nomes.map((_, k) => 0.2 + rnd(i * 7 + k));
    const ws = w.reduce((a, b) => a + b, 0);
    return { uf, nome: NOMES[uf], regiao: regiaoDe[uf], pst, secoes, secoesTot: Math.round((secoes * pst) / 100), peso: secoes,
      candidatos: nomes.map(([n, nm], k) => ({ numero: n, nome: nm, partido: '', votos: Math.round((base * w[k]) / ws) })) };
  });
  return { fonte: 'DEMO', eleicao: { ano: ANO, id: 'demo' }, atualizadoEm: new Date().toISOString(), falhas: [], ...agrega(estados) };
}

let cache = { t: 0, data: null, promise: null };
async function dados() {
  if (cache.data && Date.now() - cache.t < TTL_MS) return cache.data;
  if (!cache.promise) {
    cache.promise = buscaTSE()
      .then((d) => { cache.data = d; cache.t = Date.now(); return d; })
      .catch((e) => { if (cache.data) return { ...cache.data, aviso: `Usando dados em cache: ${e.message}` }; throw e; })
      .finally(() => { cache.promise = null; });
  }
  return cache.promise;
}

async function apiHandler(req, res) {
  const url = new URL(req.url, 'http://x');
  try {
    const d = url.searchParams.has('demo') ? demo() : await dados();
    res.writeHead(200, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 's-maxage=15, stale-while-revalidate=30' });
    res.end(JSON.stringify(d));
  } catch (e) {
    res.writeHead(502, { 'content-type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({ erro: e.message }));
  }
}

module.exports = { apiHandler };
