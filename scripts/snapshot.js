// Acrescenta o retrato atual do TSE ao histórico (historico.json). Uso: node scripts/snapshot.js caminho/historico.json
const fs = require('fs');
const { snapshotBrasil } = require('../public/apuracao.js');

const MAX_PONTOS = 2000;

// Só acrescenta se o horário do TSE mudou (o TSE publica de tempos em tempos; não duplicar).
function acrescenta(historico, ponto) {
  const ultimo = historico[historico.length - 1];
  if (ultimo && ultimo.t >= ponto.t) return historico;
  return [...historico, ponto].slice(-MAX_PONTOS);
}

async function main() {
  const arq = process.argv[2];
  if (!arq) throw new Error('Informe o caminho do historico.json');
  let atual = [];
  try { atual = JSON.parse(fs.readFileSync(arq, 'utf8')); } catch { /* primeira execução */ }
  const novo = acrescenta(atual, await snapshotBrasil());
  if (novo !== atual) fs.writeFileSync(arq, JSON.stringify(novo));
  console.log(novo === atual ? 'sem novidade' : `ponto ${novo.length} gravado`);
}

if (require.main === module) main().catch((e) => { console.error(e.message); process.exit(1); });
module.exports = { acrescenta };
