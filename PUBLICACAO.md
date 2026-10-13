# Publicar o Memória de Projetos como site

## Sobre o "uv"
O **uv** (Astral) é o gerenciador de pacotes e de ambiente do Python. Ele instala as
dependências e roda o app, mas **não guarda dados**. As informações ficam em um
**volume persistente do servidor**: o banco `memoria_projetos.db` (SQLite) e os anexos.
Tudo fica na pasta definida por `MEMORIA_DATA_DIR` (no Docker: `/dados`).

## Usar o PostgreSQL do Railway (banco novo)
1. O PostgreSQL e o serviço do app precisam estar no **mesmo projeto e no mesmo ambiente** do
   Railway (o endereço `postgres.railway.internal` só funciona lá dentro).
2. No serviço do PostgreSQL: confira que está **Active** e deixe o *App Sleeping* desligado.
3. No serviço do app, crie as variáveis **antes** de publicar (o primeiro usuário só é criado
   num banco vazio, na primeira partida):
   - `DECIDIU_DATABASE_URL` = `${{Postgres.DATABASE_URL}}` (referência, não cole o endereço;
     troque `Postgres` pelo nome do serviço do banco);
   - `MEMORIA_ADMIN_USUARIO` = `lucas` e `MEMORIA_ADMIN_SENHA` = a senha que você quer (6+ caracteres).
     Sem a senha, uma senha aleatória aparece **uma vez** no log;
   - `DECIDIU_ORG_INICIAL` = nome do escritório (ex.: `Ru.A Estúdio`).
4. No log da partida deve aparecer:
   `[memoria] Banco: postgresql+psycopg://...:***@postgres.railway.internal:5432/...` e depois
   `[memoria] Banco atualizado: versão sem versão -> 0002`.
5. Se o banco não responder, o app tenta por ~90 s e então escreve no log as causas prováveis.
   Para voltar ao SQLite, apague `DECIDIU_DATABASE_URL`.

O volume `/dados` continua necessário: anexos, logos e PDFs ainda ficam nele.

## Atualização com organizações e Alembic (fazer uma vez)
Esta versão muda a estrutura do banco na primeira partida (migrações do Alembic):
cria a tabela de organizações e coloca todos os usuários e projetos atuais numa organização só.
Ninguém perde acesso, mas faça assim:

1. **Backup antes**: copie o `memoria_projetos.db` (e a pasta `/dados` inteira) do volume.
2. No Railway, defina `DECIDIU_ORG_INICIAL` com o nome do escritório (ex.: `Ru.A Estúdio`).
   Sem ela, o nome fica "Organização principal" (dá para trocar depois pela API).
3. Rode `uv lock` no PC e publique (entraram `alembic`, `pyjwt` e `psycopg`).
4. No log da partida deve aparecer `[memoria] Banco atualizado: versão sem versão -> 0002`.
   Nas partidas seguintes essa linha não aparece (não há nada a aplicar). Para conferir:
   `alembic current` no terminal do serviço (deve mostrar `0002 (head)`).

O administrador mais antigo (o usuário inicial) vira também **superadmin**.

## Tela principal (linha do tempo)
Pensada para o celular: a linha do tempo ocupa quase toda a tela.
- Barra superior: ☰ (menu), nome do projeto e o seu nível de acesso.
- Logo abaixo: **Buscar decisões**, **+ Nova Decisão** e **Atas de Reunião**.
- Menu lateral (☰): troca de projeto, Pendências (com a contagem), Ficha, Relatório PDF,
  gestão do projeto (novo, editar, membros, excluir), administração (usuários, logo,
  plataforma) e conta (modo claro/escuro, senha, sair). Cada item só aparece para quem tem
  permissão, como antes.

## Aparência: modo claro e escuro
No menu lateral (☰), item "Modo claro" / "Modo escuro". A escolha fica guardada **no usuário**
(vale em qualquer aparelho) e o padrão continua sendo o modo escuro. A migração 0003 cria essa
preferência sozinha na partida (log: `Banco atualizado: versão 0002 -> 0003`).

- Cores das telas: definidas em `tema.py`. Nas telas, use as cores "por papel" do tema
  (`ft.Colors.ON_SURFACE_VARIANT`, `PRIMARY`, `ERROR`...), nunca cores fixas como `GREY_400`:
  elas somem num dos modos. O teste `tests/test_tema.py` acusa se alguma cor fixa voltar.
- Selos (disciplina, impacto, situação): texto escuro sobre fundo em tom médio, contraste ≥ 7.

## Plataforma: organizações (só o superadmin)
Botão **Plataforma** no cabeçalho da linha do tempo (só aparece para o superadmin).
- **+ Nova Organização**: nome do escritório e o primeiro administrador (nome, usuário e senha
  inicial). Envie ao administrador o endereço, o usuário e, por outro canal, a senha; ele troca a
  senha em "Minha conta" e cadastra a equipe em "Usuários".
- A lista mostra a situação, quantos usuários e projetos cada organização tem e desde quando.
  Só contagens: os projetos dos escritórios continuam invisíveis para a plataforma.
- **Suspender**: ninguém da organização entra (quem estiver com o app aberto perde o acesso na
  hora). Os dados ficam guardados. **Reativar** devolve o acesso. A sua organização não pode ser
  suspensa.

## Como funciona
- O Python roda no servidor e o navegador é só a tela (Flet em modo web). Todos
  os usuários compartilham o mesmo banco.
- Usuários e senhas (PBKDF2) continuam na tela de login do app.
- O banco, o segredo dos links e os anexos ficam no volume `dados` e sobrevivem a atualizações.
  Inclua `/dados` inteiro no backup.

## Usar no celular (iPhone e Android)
O app abre no navegador do celular, sem instalar nada. As telas se ajustam ao tamanho da tela:
cabeçalho com botões que quebram de linha (rótulos curtos), campos empilhados e janelas que
ocupam a largura do aparelho.

Para ter um atalho na tela inicial:
- **iPhone (Safari)**: toque em Compartilhar → **Adicionar à Tela de Início**.
- **Android (Chrome)**: menu ⋮ → **Adicionar à tela inicial** (ou **Instalar app**).

Observações:
- O nome e o ícone do atalho podem aparecer no padrão do Flet; personalizar fica para depois.
- Teste em aparelho real, em pé e deitado. O layout é ajustado quando a tela é aberta: se girar o
  aparelho com uma janela aberta, feche e abra de novo.
- Para clientes, entregue o endereço do site e um usuário com acesso **Leitor**.
- Anexos baixam como arquivo (links temporários de 5 minutos). Abra pelo app de novo se expirar.

## Relatório de decisões em PDF
Botão **Relatório PDF** (no celular, **PDF**) no cabeçalho da linha do tempo. Qualquer pessoa com
acesso ao projeto, inclusive o **Leitor** (cliente), pode gerar.

Opções: período (datas em branco = tudo), categoria, incluir a ficha do empreendimento e incluir
justificativa, alternativas e checklist. O relatório traz capa com cliente e filtros, resumo por
categoria e impacto, a ficha com os indicadores calculados e as decisões em ordem cronológica
(origem na ata, alterações da ficha, anexos e quem registrou), com "Página X de Y" no rodapé.

No site, depois de gerar toque em **Baixar PDF** (o link vale 15 minutos). Os arquivos ficam em
`/dados/relatorios` e são apagados automaticamente depois de 24 horas.

**Logotipos no cabeçalho**: o relatório e o PDF das atas trazem, no alto de todas as páginas, o
logo da empresa (à esquerda) e o logo do cliente do projeto (à direita), quando cadastrados.
- Logo da empresa: botão com ícone de prédio no topo da tela (só administradores). Vale para
  todos os projetos.
- Logo do cliente: **Editar Projeto** → "Logo do cliente" (Responsável pelo projeto).

Aceita PNG, JPG, WEBP, GIF ou BMP de até 5 MB; a imagem é reduzida e guardada como PNG em
`/dados/logos`. PNG com fundo transparente fica melhor. Sem logos, o PDF sai como antes.

Limites: o PDF usa a fonte padrão (Helvetica). Letras acentuadas e m² funcionam; emojis e símbolos
fora do alfabeto latino viram "?". Esta função exige o pacote `reportlab` (já está no
`pyproject.toml`; rode `uv lock` de novo antes de publicar).

## Pendências de decisão
Botão **Pendências** na linha do tempo (o número entre parênteses é quantas estão em aberto).
Lista os assuntos que ainda aguardam decisão, com responsável, prazo (vencidos aparecem em
vermelho) e origem.

Como uma pendência entra:
- **Manualmente**: **+ Nova Pendência** (Editor ou Responsável).
- **Pelas atas**: no texto da ata, comece a linha com `[P]` (ex.: `[P] Definir fornecedor das
  esquadrias`). Ao **fechar** a ata, cada linha `[P]` vira uma pendência ligada a ela. O rascunho
  gerado por IA a partir da transcrição já traz os assuntos sem decisão como linhas `[P]`: revise,
  apague ou ajuste antes de fechar. A IA também recebe a lista de pendências em aberto, para não
  repeti-las e para apontar (com o código P-xxx no título da decisão) quando uma delas foi decidida.

Como uma pendência sai:
- **Resolver**: registra a decisão na hora (vira um D-xxx na linha do tempo) ou liga a uma decisão
  já registrada.
- **Cancelar**: quando o assunto deixou de precisar de decisão (pede o motivo).
Resolvidas e canceladas continuam no histórico (filtro **Situação**) e podem ser reabertas.
Leitores (clientes) veem a lista, mas não alteram.

## Acesso e permissões (usuários externos)
Cada projeto tem seus próprios membros. Ninguém vê projetos dos quais não faz parte.

| Acesso | Quem é | O que pode |
|---|---|---|
| **Leitor** | cliente que acompanha | ver decisões, atas **fechadas** (rascunhos ficam ocultos) e a ficha; abrir anexos |
| **Editor** | equipe / terceiro | tudo do Leitor + registrar decisões, atas e pendências, alterar a ficha |
| **Responsável** | dono do projeto | tudo do Editor + editar o projeto, gerenciar os membros e **excluir o projeto** |
| **Administrador** | você | acessa todos os projetos e cadastra usuários |

**Excluir um projeto** (Responsável ou administrador): botão **Excluir** no cabeçalho. A tela mostra
quantas decisões, atas e anexos serão apagados e pede que você digite o nome do projeto. A exclusão
é **definitiva** (apaga também a ficha, o histórico e os arquivos anexados): faça backup antes se
houver qualquer dúvida. O log do servidor registra quem excluiu.

Como usar:
1. O administrador cadastra o usuário (botão **Usuários**). Para um **cliente**, desmarque
   "Pode criar projetos próprios". Pelo terminal: `gerenciar.py criar-usuario maria "Maria" --cliente`.
2. Quem for **Responsável** do projeto abre **Membros**, informa o login e escolhe o acesso.
3. Quem tem "pode criar projetos" cria os próprios e vira Responsável deles.
4. Cada pessoa troca a própria senha em **Minha conta** (ícone de engrenagem).

As permissões são conferidas também na gravação dos dados, não só nos botões da tela.
Os anexos só abrem por link assinado que vale 5 minutos e é gerado depois de checar o acesso.
5 senhas erradas bloqueiam o usuário por 15 minutos.

**Bancos criados antes desta versão:** na primeira execução, todo usuário comum recebe acesso
de **Editor** aos projetos já existentes (para ninguém perder acesso). Depois disso, ajuste em
**Membros**: ponha os clientes como **Leitor** ou remova o acesso.

## 1) Testar no seu computador
```bash
uv sync                      # instala as dependências do pyproject.toml
uv lock                      # gera o uv.lock (versões fixas); versione este arquivo
MEMORIA_MODO_WEB=1 MEMORIA_DATA_DIR=./dados uv run python main.py
# abra http://localhost:8000
```
Sem `MEMORIA_ADMIN_SENHA`, o primeiro usuário recebe uma senha aleatória, mostrada
**uma vez** no terminal. No Windows (PowerShell), defina as variáveis com `$env:NOME="valor"`.

## 2) Publicar em um servidor (VPS Linux com Docker)
Precisa de um servidor com Docker e de um domínio apontando para o IP dele.
```bash
cp .env.example .env         # edite: DOMINIO e a senha do administrador
docker compose up -d --build
```
O Caddy emite o HTTPS automaticamente. Acesse `https://SEU_DOMINIO`.

Dia a dia:
```bash
docker compose logs -f app                                  # ver o que está acontecendo
docker compose exec app python gerenciar.py listar          # listar usuários
docker compose exec app python gerenciar.py criar-usuario maria "Maria Souza"
docker compose exec app python gerenciar.py trocar-senha lucas
git pull && docker compose up -d --build                    # atualizar (os dados ficam)
```

## 3) Backup (faça com frequência)
```bash
docker compose exec app python -c "import sqlite3; s=sqlite3.connect('/dados/memoria_projetos.db'); d=sqlite3.connect('/dados/backup.db'); s.backup(d); d.close()"
docker compose cp app:/dados ./backup-$(date +%F)
```

## 4) Levar os dados que você já tem
```bash
docker compose cp memoria_projetos.db app:/dados/memoria_projetos.db
docker compose exec -u root app chown app /dados/memoria_projetos.db
docker compose restart app
```
Se o banco antigo tiver usuários com a senha `123`, o app avisa no log: troque com
`gerenciar.py trocar-senha`. Os anexos antigos (pasta `anexos_projetos`) **não** abrem no
site: eles usam outro formato de caminho. Reenvie-os pela tela de decisão.

## Publicar no Railway
Não use o `docker-compose.yml` nem o Caddy: o Railway já fornece HTTPS e domínio.

1. **Pré-requisitos**: rode `uv lock` e envie o projeto para um repositório **privado** no
   GitHub (o `.gitignore` já deixa de fora `.env`, bancos e anexos).
2. No Railway: **New Project → Deploy from GitHub repo** e escolha o repositório. Ele detecta
   o `Dockerfile` sozinho. Se o primeiro deploy rodar antes dos passos 3 e 4, tudo bem, mas
   o banco criado nele será descartado: o importante é o volume existir antes de você usar.
3. **Volume**: no serviço, crie um Volume com **Mount Path `/dados`**.
4. **Variáveis** (aba Variables do serviço):
   - `RAILWAY_RUN_UID` = `0` (o volume é montado como root; sem isso o app não consegue gravar)
   - `MEMORIA_ADMIN_USUARIO`, `MEMORIA_ADMIN_NOME`, `MEMORIA_ADMIN_SENHA` (administrador inicial)
   - Não defina `PORT`: o Railway cuida disso.
5. Faça um novo deploy (Redeploy) e, em **Settings → Networking**, clique em **Generate Domain**.
   Para usar seu domínio, adicione-o ali e crie o registro CNAME no seu provedor de DNS.
6. Acesse o endereço, entre com o administrador e crie os usuários e projetos.

**Por CLI** (alternativa ao GitHub): `npm i -g @railway/cli`, depois `railway login`,
`railway init` e `railway up` na pasta do projeto. Volume, variáveis e domínio seguem os
mesmos passos acima.

**Atualizar**: um `git push` publica a nova versão (ou `railway up`). Com volume, o Railway
mantém uma só instância ativa e há alguns segundos de indisponibilidade a cada deploy.

**Cuidados**
- A senha do administrador só vale na **primeira** execução com banco vazio. Se você definir
  `MEMORIA_ADMIN_SENHA` depois, nada muda; se esqueceu de defini-la, a senha temporária
  aparece nos **Deploy Logs**. Troque pelo app (Minha conta).
- Um serviço aceita **um volume** e **não pode ter réplicas** (compatível com SQLite).
- Para levar o seu banco atual, é preciso copiar `memoria_projetos.db` para dentro do volume
  (a documentação do Railway cita `railway ssh` com scp/sftp). Para poucos dados, comece do zero.
- Faça cópias periódicas do `/dados` e confira se o seu plano oferece backup de volume.
- Confira o preço atual do plano e do volume no site do Railway antes de abrir a externos.

## Não consigo entrar / esqueci a senha
Não existe senha fixa. O usuário inicial (padrão `lucas`) só é criado quando o banco está vazio,
com a senha de `MEMORIA_ADMIN_SENHA` ou, se ela não foi definida, uma senha aleatória.

1. **Procure no log**: em **Deploy Logs**, busque `Usuário inicial criado`. A senha temporária está lá.
2. **Se errou 5 vezes**, o usuário fica bloqueado por 15 minutos. Reiniciar o serviço (Redeploy) libera.
3. **Redefinir pelo painel (sem terminal)**: em **Variables**, crie
   `MEMORIA_RESETAR_SENHA` = `lucas:NovaSenhaForte123` (usuário, dois-pontos, nova senha com
   6+ caracteres) e faça Redeploy. O log mostrará `Senha de 'lucas' redefinida`. Entre com a nova
   senha e **apague a variável** (enquanto ela existir, a senha volta a esse valor a cada reinício).
4. **Pelo terminal**: com o Railway CLI (`railway link` e `railway ssh`), rode
   `MEMORIA_DATA_DIR=/dados python gerenciar.py trocar-senha lucas`.

Se o log listar outros usuários em vez de `lucas`, use o nome que aparecer na mensagem.

## Se o Railway não subir (solução de problemas)
Veja a mensagem em **Build Logs** (construção) ou **Deploy Logs** (execução) do serviço.

| O que acontece | Causa provável | O que fazer |
|---|---|---|
| Build não acha o `Dockerfile` ou usa outro método | arquivos dentro de uma subpasta do repositório | o `Dockerfile` precisa estar na **raiz**, ao lado do `pyproject.toml`; ou defina *Root Directory* em Settings |
| Build falha em `uv sync` | `uv.lock` ausente ou desatualizado | rode `uv lock` no computador e faça commit do `uv.lock` |
| Deploy cai com "Não foi possível gravar em /dados" | volume ausente ou sem permissão | crie o Volume com Mount Path `/dados` e defina `RAILWAY_RUN_UID=0` |
| Deploy cai com "ERRO ao montar o servidor web" | versões de `flet`/`flet-web`/`fastapi` | envie a mensagem completa; confira o `uv.lock` |
| Logs mostram o app rodando, mas o site não abre | falta domínio público | Settings → Networking → **Generate Domain** |
| Página abre e fica em branco ou carregando | primeira carga do Flet é pesada, ou WebSocket bloqueado | aguarde alguns segundos; veja o console do navegador (F12) |
| Não sei a senha do administrador | `MEMORIA_ADMIN_SENHA` não estava definida na 1ª execução | a senha temporária está nos Deploy Logs (`[memoria] Usuário inicial criado`) |

**Banco de dados:** esta versão guarda tudo em um arquivo SQLite dentro do Volume `/dados`.
Um serviço de banco criado à parte no Railway (por exemplo, PostgreSQL) **não é usado** por ela.

## Outras plataformas
Qualquer hospedagem que rode Docker serve, desde que tenha **disco persistente** montado em
`/dados` (Fly.io volumes, Render com disk). Sem disco persistente, o banco
é apagado a cada novo deploy.

## Limites a conhecer
- **SQLite + um único processo**: adequado para uma equipe pequena. Não rode várias
  réplicas do app.
- **Anexos**: ficam em `/dados/uploads` (fora da pasta pública) e baixam por link temporário.
  Um Leitor que baixa um arquivo pode, claro, repassá-lo: a permissão controla o acesso, não a cópia.
- **Bloqueio de login**: vale por usuário e fica em memória (zera ao reiniciar). Alguém pode
  bloquear temporariamente a conta de outra pessoa errando a senha de propósito. Use senhas fortes.
- **Não há recuperação de senha por e-mail**: o administrador redefine com
  `gerenciar.py trocar-senha <usuario>`.
- **Cadastro de usuários**: só o administrador cria contas. O Responsável apenas dá acesso a
  contas que já existem.
- **Teste antes de abrir a externos**: crie um usuário Leitor e confira se ele vê só o que deve.
