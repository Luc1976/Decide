# Capturas da página de ajuda

A ajuda fica em `ajuda/index.html` e é servida pelo app em `/ajuda` (`ajuda_web.py`).
As imagens em `ajuda/img/` são capturas reais do projeto de demonstração.

Para regerar as imagens depois de mudar alguma tela:

1. Suba o app com a demonstração carregada (`DECIDIU_CARREGAR_DEMO=1` e `DECIDIU_DEMO_SENHA`).
2. Nesta pasta:

```bash
npm install
npx playwright install chromium
DECIDIU_URL=http://localhost:8000 DECIDIU_DEMO_SENHA="<senha da demo>" npm run capturar
```

3. Confira as imagens em `ajuda/img/`. Telas e menus são abertos pelas rotas do app e por
   posição na tela: se um botão mudar de lugar, ajuste as coordenadas em `PASSOS`
   (`capturar.js`).

`DECIDIU_CAPTURA_OFFLINE=1` só é necessário em ambientes sem acesso aos servidores do
Google (motor gráfico do Flet e fontes); num computador comum, deixe sem.
