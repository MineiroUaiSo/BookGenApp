// Servidor local sem dependências: serve public/ (site estático). Uso: node dev.js
const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = process.env.PORT || 3000;
const TIPOS = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8' };
const PUB = path.join(__dirname, 'public');

http.createServer((req, res) => {
  const url = new URL(req.url, 'http://x');
  const arq = path.join(PUB, url.pathname === '/' ? 'index.html' : path.normalize(url.pathname));
  if (!arq.startsWith(PUB)) { res.writeHead(403); return res.end(); }
  fs.readFile(arq, (err, buf) => {
    if (err) { res.writeHead(404); return res.end('Não encontrado'); }
    res.writeHead(200, { 'content-type': TIPOS[path.extname(arq)] || 'application/octet-stream' });
    res.end(buf);
  });
}).listen(PORT, () => console.log(`Apuração por região: http://localhost:${PORT}  (demo: /?demo=1)`));
