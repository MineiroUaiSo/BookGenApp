// Diagnóstico temporário: mostra o que o TSE responde a partir da Vercel.
module.exports = async (req, res) => {
  const B = 'https://resultados.tse.jus.br/oficial';
  const urls = [
    `${B}/ele2026/6257/dados-simplificados/br/br-c0001-e006257-r.json`,
    `${B}/ele2026/6258/dados-simplificados/br/br-c0001-e006258-r.json`,
    `${B}/ele2026/6257/dados/br/br-c0001-e006257-v.json`,
    `${B}/ele2026/6257/config/mun-e006257-cm.json`,
    `${B}/ele2026/6257/dados-simplificados/sp/sp-c0001-e006257-r.json`,
    `${B}/ele2026/6257/dados/br/br-c0001-e006257-u.json`,
  ];
  const out = [];
  for (const u of urls) {
    const t = Date.now();
    try {
      const r = await fetch(u, { signal: AbortSignal.timeout(6000) });
      const txt = await r.text();
      out.push({ u: u.replace(B, ''), status: r.status, ms: Date.now() - t, head: txt.slice(0, 500).replace(/\s+/g, ' ') });
    } catch (e) { out.push({ u, erro: String(e), ms: Date.now() - t }); }
  }
  res.setHeader('content-type', 'application/json');
  res.end(JSON.stringify(out));
};
