// Diagnóstico temporário: mostra o que o TSE responde a partir da Vercel.
module.exports = async (req, res) => {
  const urls = [
    'https://resultados.tse.jus.br/oficial/comum/config/ele-c.json',
    'https://resultados.tse.jus.br/oficial/ele2022/544/dados-simplificados/br/br-c0001-e000544-r.json',
  ];
  const out = [];
  for (const u of urls) {
    const t = Date.now();
    try {
      const r = await fetch(u, { signal: AbortSignal.timeout(7000), headers: { 'user-agent': 'Mozilla/5.0 (compatible; apuracao-por-regiao/1.0)' } });
      const txt = await r.text();
      out.push({ u, status: r.status, ms: Date.now() - t, len: txt.length, head: u.includes('ele-c') ? txt.slice(txt.indexOf('"pl"')).replace(/\s+/g,' ') : txt.slice(0, 700) });
    } catch (e) { out.push({ u, erro: String(e), ms: Date.now() - t }); }
  }
  res.setHeader('content-type', 'application/json');
  res.end(JSON.stringify(out));
};
