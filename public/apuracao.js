// Busca e normaliza os dados oficiais do TSE. Universal: roda no navegador (window.Apuracao) e no Node (testes).
(function () {
'use strict';

// Configuração: window.APURACAO_CFG = { ano, id, cargo } (navegador) ou ELEICAO_ANO/ELEICAO_ID/CARGO (Node).
const CFG = (typeof window !== 'undefined' && window.APURACAO_CFG) || {};
const ENV = (typeof process !== 'undefined' && process.env) || {};
const ANO = CFG.ano || ENV.ELEICAO_ANO || '2026';
const CARGO = CFG.cargo || ENV.CARGO || '0001'; // 0001 = Presidente
const TTL_MS = 20_000;
const BASE = 'https://resultados.tse.jus.br/oficial';

// Pode fixar o código da eleição (ex.: ELEICAO_ID=544 em 2022 1º turno). Se vazio, descobre sozinho.
const ID_FIXO = CFG.id || ENV.ELEICAO_ID || null;
const DESCOBERTA_TTL_MS = 5 * 60_000;
let descoberto = null; // { id, t }

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
  const res = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) });
  if (!res.ok) throw Object.assign(new Error(`HTTP ${res.status} em ${url}`), { status: 502 });
  return res.json();
}

const idStr = (id) => String(id).padStart(6, '0');
const urlUF = (id, uf) => {
  const u = uf.toLowerCase();
  return `${BASE}/ele${ANO}/${id}/dados/${u}/${u}-c${CARGO}-e${idStr(id)}-u.json`;
};

// Descobre o código da eleição lendo a configuração oficial (pleitos -> eleições -> abrangência "br" -> cargo Presidente).
// Usa o 2º turno (cdt2) só se o arquivo existir e já tiver seções totalizadas; senão, o 1º.
// O id descoberto vale por 5 minutos, para instâncias quentes migrarem sozinhas pro 2º turno.
// Retorna { id, br } com o JSON do Brasil, para reaproveitar.
async function descobrirEleicao() {
  if (ID_FIXO) return { id: ID_FIXO, br: await getJson(urlUF(ID_FIXO, 'BR')) };
  if (descoberto && Date.now() - descoberto.t < DESCOBERTA_TTL_MS) {
    return { id: descoberto.id, br: await getJson(urlUF(descoberto.id, 'BR')) };
  }
  const cfg = await getJson(`${BASE}/comum/config/ele-c.json`);
  const cargoNum = String(CARGO).replace(/^0+/, '');
  const achados = [];
  for (const pl of cfg.pl || []) {
    if (pl.c !== `ele${ANO}`) continue;
    for (const e of pl.e || []) {
      const ehPresidente = (e.abr || []).some((a) => a.cd === 'br' && (a.cp || []).some((c) => String(c.cd).replace(/^0+/, '') === cargoNum));
      if (ehPresidente) achados.push(e);
    }
  }
  if (!achados.length) throw new Error(`Eleição ${ANO} com o cargo ${CARGO} não está na configuração do TSE (defina ELEICAO_ID).`);
  for (const e of achados) {
    if (e.cdt2) {
      try {
        const j = await getJson(urlUF(e.cdt2, 'BR'), 8000);
        if (num(j.s?.st) > 0) { descoberto = { id: e.cdt2, t: Date.now() }; return { id: e.cdt2, br: j }; }
      } catch { /* 2º turno ainda sem dados */ }
    }
    if (e.cd) {
      try {
        const j = await getJson(urlUF(e.cd, 'BR'), 8000);
        descoberto = { id: e.cd, t: Date.now() };
        return { id: e.cd, br: j };
      } catch { /* ainda sem dados desse turno */ }
    }
  }
  const err = new Error('A apuração ainda não foi publicada pelo TSE. Tente de novo em alguns minutos — esta página recarrega sozinha.');
  err.status = 503;
  throw err;
}

function normalizaUF(uf, d) {
  const cargoNum = String(CARGO).replace(/^0+/, '');
  const carg = Array.isArray(d.carg) ? d.carg.find((c) => String(c.cd).replace(/^0+/, '') === cargoNum) || d.carg[0] : d;
  let cands = [];
  for (const agr of (carg && carg.agr) || []) {
    for (const par of agr.par || []) {
      for (const c of par.cand || []) cands.push({ numero: c.n, nome: c.nmu || c.nm, partido: par.sg || '', votos: num(c.vap) || 0 });
    }
  }
  if (!cands.length) {
    cands = ((carg && carg.cand) || d.cand || []).map((c) => ({ numero: c.n, nome: c.nmu || c.nm || c.nv, partido: c.cc || c.sg || '', votos: num(c.vap) || 0 }));
  }
  const secoes = num(d.s?.ts);
  let secoesTot = num(d.s?.st);
  let pst = num(d.s?.pst);
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

// "04/10/2026" + "18:00:33" -> ISO com fuso de Brasília
function isoDoTSE(dg, hg) {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(dg || '');
  if (!m || !/^\d{2}:\d{2}:\d{2}$/.test(hg || '')) return new Date().toISOString();
  return `${m[3]}-${m[2]}-${m[1]}T${hg}-03:00`;
}

const comPct = (cands) => {
  const total = cands.reduce((a, c) => a + c.votos, 0);
  return [...cands].sort((a, b) => b.votos - a.votos).map((c) => ({ ...c, pct: total ? (c.votos / total) * 100 : 0 }));
};

async function buscaTSE() {
  const { id, br } = await descobrirEleicao();
  const resultados = await Promise.allSettled(UFS.map(async (uf) => normalizaUF(uf, await getJson(urlUF(id, uf)))));
  const estados = [];
  const falhas = [];
  resultados.forEach((r, i) => (r.status === 'fulfilled' ? estados.push(r.value) : falhas.push(`${UFS[i]}: ${r.reason.message}`)));
  if (!estados.length) throw new Error(falhas[0]);
  const agregado = agrega(estados);
  const b = normalizaUF('BR', br);
  const candidatos = comPct(b.candidatos);
  const brasil = candidatos.length
    ? { pst: b.pst, secoes: b.secoes, secoesTot: b.secoesTot, votosValidos: candidatos.reduce((a, c) => a + c.votos, 0), candidatos }
    : agregado.brasil;
  return {
    fonte: 'TSE',
    eleicao: { ano: ANO, id, turno: Number(br.t) },
    atualizadoEm: isoDoTSE(br.dg, br.hg),
    falhas,
    brasil,
    regioes: agregado.regioes,
    estados: agregado.estados,
  };
}

// Dados fictícios só para testar a interface (?demo=1). Mesmo formato dos dados reais.
function demo() {
  const seed = Math.floor(Date.now() / 20000);
  const rnd = (i) => { const x = Math.sin(seed * 31 + i * 12.9898) * 43758.5453; return x - Math.floor(x); };
  const nomes = [['22', 'FLAVIO BOLSONARO', 'PL'], ['13', 'LULA', 'PT'], ['55', 'RONALDO CAIADO', 'PSD'], ['70', 'AUGUSTO CURY', 'AVANTE']];
  const SEM_DADOS = 'RR';
  const estados = UFS.map((uf, i) => {
    if (uf === SEM_DADOS) return { uf, nome: NOMES[uf], regiao: regiaoDe[uf], pst: 0, secoes: 0, secoesTot: 0, peso: 0, candidatos: [] };
    const pst = Math.min(100, 20 + ((seed % 40) * 2) + rnd(i) * 45);
    const base = ELEITORADO[uf] * 1000 * 0.78 * (pst / 100);
    const secoes = Math.round(ELEITORADO[uf] * 2.9);
    const w = nomes.map((_, k) => 0.2 + rnd(i * 7 + k));
    const ws = w.reduce((a, b) => a + b, 0);
    return { uf, nome: NOMES[uf], regiao: regiaoDe[uf], pst, secoes, secoesTot: Math.round((secoes * pst) / 100), peso: secoes,
      candidatos: nomes.map(([n, nm, sg], k) => ({ numero: n, nome: nm, partido: sg, votos: Math.round((base * w[k]) / ws) })) };
  });
  const ag = agrega(estados);
  const brasil = {
    pst: ag.brasil.pst,
    secoes: estados.reduce((a, e) => a + e.secoes, 0),
    secoesTot: estados.reduce((a, e) => a + e.secoesTot, 0),
    votosValidos: ag.brasil.votosValidos,
    candidatos: ag.brasil.candidatos,
  };
  return {
    fonte: 'DEMO',
    eleicao: { ano: ANO, id: 'demo', turno: 1 },
    atualizadoEm: new Date().toISOString(),
    falhas: [`${SEM_DADOS}: sem dados (demo)`],
    brasil,
    regioes: ag.regioes,
    estados: ag.estados,
  };
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

function buscar({ demo: usaDemo } = {}) {
  return usaDemo ? Promise.resolve(demo()) : dados();
}

function _reset() {
  descoberto = null;
  cache = { t: 0, data: null, promise: null };
}

if (typeof module !== 'undefined' && module.exports) module.exports = { normalizaUF, agrega, descobrirEleicao, num, _reset, buscar };
else window.Apuracao = { buscar };
})();
