/*
 * Capturas de tela da página de ajuda (ajuda/img/*.png), tiradas do projeto de demonstração.
 *
 * Uso (com o app rodando e a demonstração carregada — ver scripts/seed_demo.py):
 *   cd scripts/ajuda && npm install && npx playwright install chromium
 *   DECIDIU_URL=http://localhost:8000 DECIDIU_DEMO_SENHA=... npm run capturar
 *
 * DECIDIU_CAPTURA_OFFLINE=1 serve o motor gráfico do Flet e as fontes a partir de cópias
 * locais (para ambientes sem acesso a gstatic.com). Num computador comum não é preciso.
 * As telas são abertas pelas rotas do app (/timeline, /ficha...) e alguns botões por
 * posição: se o layout mudar, confira as imagens e ajuste as coordenadas em PASSOS.
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const URL = process.env.DECIDIU_URL || 'http://localhost:8000';
const SENHA = process.env.DECIDIU_DEMO_SENHA || '';
const SAIDA = path.resolve(__dirname, '../../ajuda/img');
const ESPERA_FONTES = Number(process.env.DECIDIU_ESPERA || 12000);

function canvaskitLocal() {
  const raiz = path.resolve(__dirname, '../../.venv/lib');
  if (!fs.existsSync(raiz)) return null;
  for (const py of fs.readdirSync(raiz)) {
    const dir = path.join(raiz, py, 'site-packages/flet_web/web/canvaskit');
    if (fs.existsSync(dir)) return dir;
  }
  return null;
}

async function modoOffline(p) {
  const ck = canvaskitLocal();
  const fonte = (pacote, arquivo) => path.join(path.dirname(require.resolve(`${pacote}/package.json`)), 'files', arquivo);
  if (ck) {
    await p.route('**/flutter-canvaskit/**', async (r) => {
      const arq = path.join(ck, r.request().url().split('/').pop());
      if (!fs.existsSync(arq)) return r.abort();
      await r.fulfill({ body: fs.readFileSync(arq), contentType: arq.endsWith('.wasm') ? 'application/wasm' : 'application/javascript' });
    });
  }
  await p.route('https://fonts.gstatic.com/**', async (r) => {
    const u = r.request().url();
    let arq = null;
    if (u.includes('/roboto/')) arq = fonte('@fontsource/roboto', 'roboto-latin-400-normal.woff2');
    else if (u.includes('notosanssymbols2')) arq = fonte('@fontsource/noto-sans-symbols-2', 'noto-sans-symbols-2-symbols-400-normal.woff2');
    else if (u.includes('notosanssymbols')) arq = fonte('@fontsource/noto-sans-symbols', 'noto-sans-symbols-symbols-400-normal.woff2');
    if (!arq || !fs.existsSync(arq)) return r.abort();
    await r.fulfill({ body: fs.readFileSync(arq), contentType: 'font/woff2' });
  });
}

async function novaPagina(navegador, largura = 1366, altura = 900) {
  const p = await navegador.newPage({ viewport: { width: largura, height: altura }, deviceScaleFactor: 1 });
  if (process.env.DECIDIU_CAPTURA_OFFLINE === '1') await modoOffline(p);
  await p.goto(URL, { waitUntil: 'networkidle' });
  await p.waitForTimeout(ESPERA_FONTES);
  return p;
}

async function entrar(p, usuario) {
  const { width } = p.viewportSize();
  const x = width / 2;
  await p.mouse.click(x + 17, 387); await p.keyboard.type(usuario, { delay: 15 });
  await p.mouse.click(x - 3, 453); await p.keyboard.type(SENHA, { delay: 15 });
  await p.mouse.click(x, 568);
  await p.waitForTimeout(ESPERA_FONTES);
}

async function rota(p, caminho, espera = 5000) {
  await p.evaluate((c) => { history.pushState({}, '', c); dispatchEvent(new PopStateEvent('popstate', { state: {} })); }, caminho);
  await p.waitForTimeout(espera);
}

const foto = (p, nome) => p.screenshot({ path: path.join(SAIDA, `${nome}.png`) });
const clicar = async (p, x, y, espera = 2500) => { await p.mouse.click(x, y); await p.waitForTimeout(espera); };
const rolar = async (p, dy, espera = 1500) => { await p.mouse.move(683, 600); await p.mouse.wheel(0, dy); await p.waitForTimeout(espera); };
const fechar = async (p) => { await p.keyboard.press('Escape'); await p.waitForTimeout(1200); };

// Cada passo: [nome do arquivo, função]. Equipe: demo.rafael (Responsável).
const PASSOS = [
  ['02-linha-do-tempo', async (p) => { await rota(p, '/timeline'); }],
  ['03-menu', async (p) => { await clicar(p, 28, 32); }],
  ['04-nova-decisao', async (p) => { await fechar(p); await clicar(p, 795, 98, 3000); }],
  ['05-atas', async (p) => { await fechar(p); await rota(p, '/atas'); }],
  ['06-ata-aberta', async (p) => { await clicar(p, 297, 804, 4000); }],  // "Abrir ata" da Ata 06
  ['07-pendencias', async (p) => { await fechar(p); await rota(p, '/pendencias'); }],
  ['08-ficha', async (p) => { await rota(p, '/ficha'); await rolar(p, 640); }],
  ['09-ficha-alturas', async (p) => { await rolar(p, 420); }],
  ['10-cronograma', async (p) => { await rota(p, '/cronograma'); }],
  ['11-cronograma-revisar', async (p) => { await clicar(p, 513, 288, 3000); }],
  ['12-documentos', async (p) => { await rota(p, '/documentos'); }],
  ['13-relatorio', async (p) => { await rota(p, '/timeline'); await clicar(p, 28, 32); await clicar(p, 150, 410, 3000); }],
  ['14-membros', async (p) => { await fechar(p); await clicar(p, 28, 32); await clicar(p, 150, 604, 3000); }],
];

(async () => {
  if (!SENHA) { console.error('Defina DECIDIU_DEMO_SENHA.'); process.exit(2); }
  fs.mkdirSync(SAIDA, { recursive: true });
  const navegador = await chromium.launch();
  try {
    let p = await novaPagina(navegador);
    await foto(p, '01-login');
    await entrar(p, 'demo.rafael');
    for (const [nome, passo] of PASSOS) {
      await passo(p);
      await foto(p, nome);
      console.log('ok', nome);
    }
    await p.close();

    p = await novaPagina(navegador);  // cliente (Leitor)
    await entrar(p, 'demo.marcos');
    await clicar(p, 28, 32);
    await foto(p, '15-cliente-menu');
    await p.close();

    p = await novaPagina(navegador, 390, 844);  // celular
    await entrar(p, 'demo.rafael');
    await foto(p, '16-celular');
    await p.close();
  } finally {
    await navegador.close();
  }
})();
