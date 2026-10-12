# Decidiu: camada de serviços e API REST

Este documento descreve a nova arquitetura do backend: o que mudou neste branch, como as
peças se encaixam e o que falta para o Decidiu atender muitos clientes ao mesmo tempo.

## 1. Resumo

O app Flet continua funcionando como antes. Por baixo dele foram criadas duas camadas:

```
          app Flet atual                         novo frontend (web/PWA)
     views/*.py  ─►  database.py                 React/Next.js, apps futuros
                         │  (compatibilidade)              │  HTTPS + JSON
                         │                                 ▼
                         │                          api/  (FastAPI)
                         │                       rotas, esquemas, login JWT
                         ▼                                 │
              ┌────────────────────────────────────────────┴───┐
              │  nucleo/servicos/   REGRAS DE NEGÓCIO (uma só)  │
              │  permissões · numeração · auditoria · ficha     │
              ├─────────────────────────────────────────────────┤
              │  nucleo/tabelas.py · nucleo/db.py · armazenamento│
              └──────────────┬──────────────────────┬───────────┘
                     SQLite / PostgreSQL     disco local / S3·R2
```

- **`nucleo/`**: regras de negócio, sem Flet e sem FastAPI. É a única fonte das regras.
- **`database.py`**: mantém as mesmas funções que as telas chamam, mas agora só abre a
  sessão e delega para `nucleo/servicos/`. As telas não mudaram.
- **`api/`**: API REST com 48 operações, login por token, documentação automática em
  `/api/docs` e os mesmos serviços por baixo.
- **`tests/`**: 44 testes automáticos (ver seção 8).

## 2. Diagnóstico do código atual

O que foi encontrado na leitura do código e como cada ponto foi tratado:

| # | Achado | Risco | Situação |
|---|---|---|---|
| 1 | Regras de negócio misturadas com o acesso ao banco em `database.py` (1.400 linhas), e parte da lógica nas telas (relatório, PDF da ata, IA, envio de anexos) | Não dá para reaproveitar num frontend novo; difícil testar | **Resolvido**: regras em `nucleo/servicos/` |
| 2 | **Leituras sem checagem de permissão** (`listar_decisoes_projeto`, `listar_caracteristicas`, `buscar_reuniao`...). Só a tela impedia o acesso. O filtro "Leitor não vê rascunho de ata" também estava só na tela (`views/atas.py`) | Numa API, qualquer usuário logado leria qualquer projeto trocando o número na URL | **Resolvido na API**: todo serviço checa o acesso, inclusive na leitura. Objeto de projeto alheio responde 404, sem confirmar que existe |
| 3 | Numeração "maior + 1" (D-001, P-001, Ata 01) sem trava | Com dois usuários gravando ao mesmo tempo, número repetido | **Resolvido**: trava da linha do projeto (`SELECT … FOR UPDATE`) no PostgreSQL |
| 4 | Banco SQLite num único arquivo | Um escritor por vez; não escala horizontalmente | **Preparado**: `DECIDIU_DATABASE_URL` liga o PostgreSQL. SQLite passou a usar WAL (leitores não travam quem grava). Falta migrar os dados (seção 9) |
| 5 | Estado guardado em memória ou arquivo de um processo: limite de login, contagem de uso da IA (`uso_ia.json`), anexos, logos e PDFs no disco local | Com 2+ instâncias, cada uma tem o seu: limites furam e arquivos "somem" | **Preparado**: `nucleo/armazenamento.py` isola os arquivos atrás de uma interface (trocar por S3/R2 sem mexer nos serviços). Limite e uso de IA vão para o Redis/banco (seção 9) |
| 6 | Sem trilha de auditoria (exclusão de projeto só aparecia num `print`) | Sem como responder "quem mudou isso?" a um cliente | **Resolvido**: tabela `RegistroAuditoria`, gravada na mesma transação de cada alteração. `GET /projetos/{id}/auditoria` para o Responsável |
| 7 | **Sem separação entre clientes do SaaS**: o administrador vê todos os projetos de todos os usuários | Para um produto comercial, um escritório não pode ter acesso ao projeto de outro, nem você como dono da plataforma deve ter por padrão | **Pendente**: é a primeira mudança de modelo da seção 9 |
| 8 | `autor` gravado como texto (nome), anexos como texto separado por vírgula, checklist como JSON em texto | Nome muda e o histórico perde o vínculo; anexos sem metadados | Mantido para não quebrar o banco. A API já expõe anexos e checklist estruturados. Migração na seção 9 |
| 9 | Migrações feitas à mão (`ALTER TABLE` com `PRAGMA`) | Só funciona no SQLite; frágil | Mantido para o SQLite. Para o PostgreSQL: Alembic (seção 9) |
| 10 | Título de decisão podia ficar vazio | Registro sem título na linha do tempo | **Resolvido**: o serviço valida título, categoria e impacto, e a tela mostra a mensagem |
| 11 | `ficha.py` e `questionario_sistemas.py` na raiz são cópias idênticas dos arquivos em `views/` | Confusão ao editar | Não alterado. Pode apagar as cópias da raiz |

## 3. Camada de serviços (`nucleo/`)

| Arquivo | Responsabilidade |
|---|---|
| `tabelas.py` | Todas as tabelas (movidas de `database.py` e `models.py`, colunas idênticas) + `RegistroAuditoria` (nova) |
| `db.py` | Engine e sessões. SQLite por padrão; PostgreSQL com `DECIDIU_DATABASE_URL` |
| `ator.py` | `Ator`: quem está agindo (id, nome, admin). Substitui o `usuario_id` solto |
| `permissoes.py` | `nivel()` e `exigir()`: Leitor 1, Editor 2, Responsável 3, Admin 4 |
| `erros.py` | `NaoEncontrado` (404), `Conflito` (409), `SemPermissao` (403), `ErroDominio` (422). Herdam de `ValueError`/`PermissionError`, então as telas Flet tratam igual |
| `numeracao.py` | Sequenciais por projeto com trava |
| `auditoria.py` | `registrar()` dentro da transação |
| `armazenamento.py` | Interface de arquivos + implementação em disco local |
| `marcacoes.py`, `senhas.py` | Linhas `[D]`/`[P]`, hash PBKDF2 |
| `servicos/usuarios.py` | Login, cadastro (admin), troca de senha |
| `servicos/projetos.py` | Projetos, membros, exclusão completa |
| `servicos/decisoes.py` | Registrar, listar/filtrar, anexos. Decisão não é editada nem apagada |
| `servicos/atas.py` | Rascunho → fechamento (`[D]`, `[F]`, `[P]` numa transação), adendos, pré-visualização |
| `servicos/pendencias.py` | Criar, editar, resolver (com decisão existente ou nova), cancelar, reabrir |
| `servicos/ficha.py` | Ficha, indicadores, histórico com origem, padrão construtivo |
| `servicos/relatorios.py` | PDF do relatório e da ata (reaproveita `relatorio_pdf.py` e `ata_pdf.py`) |
| `servicos/ia.py` | Rascunho de ata pela IA (reaproveita `ia_transcricao.py`) |
| `servicos/anexos.py` | Envio para a pasta do projeto e links assinados de download |

**Convenções**: o serviço recebe a sessão e o `Ator`; checa a permissão primeiro; cada
gravação é uma transação completa (valida, grava, audita, faz commit). Funções
`consultar_*` não checam permissão e servem só para uso interno e para o `database.py`.

### Função antiga → serviço → rota

| `database.py` (Flet) | Serviço | API |
|---|---|---|
| `autenticar_usuario` | `usuarios.autenticar` | `POST /auth/login` |
| `criar_usuario`, `listar_usuarios` | `usuarios.criar/listar` | `POST/GET /admin/usuarios` |
| `alterar_propria_senha` | `usuarios.alterar_propria_senha` | `POST /auth/senha` |
| `listar_projetos_do_usuario` | `projetos.listar_do_usuario` | `GET /projetos` |
| `criar_projeto`, `atualizar_projeto` | `projetos.criar/atualizar` | `POST /projetos`, `PUT /projetos/{id}` |
| `resumo_projeto`, `excluir_projeto` | `projetos.resumo/excluir` | `GET …/resumo`, `DELETE /projetos/{id}` |
| `listar_membros`, `definir_membro`, `remover_membro` | `projetos.*_membro(s)` | `GET/PUT …/membros`, `DELETE …/membros/{usuario}` |
| `adicionar_decisao` | `decisoes.criar` | `POST …/decisoes` |
| `buscar_decisoes_projeto` | `decisoes.listar` (+ categoria e período) | `GET …/decisoes?q=&categoria=&de=&ate=` |
| `criar_reuniao`, `atualizar_reuniao_rascunho` | `atas.criar/atualizar_rascunho` | `POST …/atas`, `PUT …/atas/{id}` |
| `fechar_reuniao` | `atas.fechar` | `POST …/atas/{id}/fechar` |
| `adicionar_adendo` | `atas.adicionar_adendo` | `POST …/atas/{id}/adendos` |
| `criar/atualizar/resolver/cancelar/reabrir_pendencia` | `pendencias.*` | `…/pendencias` e ações |
| `salvar_caracteristicas`, `listar_historico_ficha` | `ficha.salvar/historico` | `PUT …/ficha`, `GET …/ficha/historico` |
| `salvar/obter_padrao_construtivo` | `ficha.salvar_padrao/obter_padrao` | `PUT/GET …/padrao-construtivo` |
| lógica em `views/timeline.py` e `views/atas.py` | `relatorios.*`, `ia.*`, `anexos.*` | PDFs, `…/atas/rascunho-ia`, `…/anexos` |

## 4. Matriz de permissões

| Ação | Leitor (cliente) | Editor | Responsável | Admin |
|---|:-:|:-:|:-:|:-:|
| Ver projeto, decisões, ficha, pendências, histórico | ✔ | ✔ | ✔ | ✔ |
| Ver atas **fechadas** / gerar PDFs | ✔ | ✔ | ✔ | ✔ |
| Ver atas em **rascunho** | – | ✔ | ✔ | ✔ |
| Registrar decisão, ata, pendência; alterar ficha; enviar anexo; usar IA | – | ✔ | ✔ | ✔ |
| Alterar dados do projeto, membros, logo do cliente; ver auditoria; excluir projeto | – | – | ✔ | ✔ |
| Cadastrar usuários, logo da empresa | – | – | – | ✔ |
| Criar projeto | se o usuário tiver `pode_criar_projetos` |||  ✔ |

Sem acesso ao projeto, a resposta é **404**, não 403: a API não confirma que o projeto existe.

## 5. API REST (`api/`)

Base: `/api/v1`. Documentação interativa: `/api/docs`. Contrato OpenAPI: `/api/openapi.json`.
A partir desse contrato dá para gerar o cliente TypeScript do frontend com `openapi-typescript`.

**Autenticação.** `POST /auth/login` com `{"username", "senha"}` devolve um token (JWT, 60 min).
O frontend envia `Authorization: Bearer <token>` em toda chamada. O usuário é relido do banco
a cada requisição: se for removido, perde o acesso na hora. Cinco senhas erradas bloqueiam o
usuário por 15 minutos (429).

**Erros.** O corpo é sempre `{"detail": "mensagem em português"}`.
`401` sem login ou token vencido · `403` papel insuficiente · `404` não existe ou não é
visível · `409` estado não permite (ex.: ata já fechada) · `422` dado inválido ou regra
violada · `429` muitas tentativas de login.

**Anexos.** São dois passos:
1. `POST /projetos/{id}/anexos` (multipart, campo `arquivo`, até 25 MB) devolve uma `chave`.
2. A chave vai em `anexos: [...]` no `POST /projetos/{id}/decisoes`.

A API recusa chave enviada para outro projeto. Para baixar,
`GET …/decisoes/{id}/anexos/{indice}/link` devolve um link assinado de 5 minutos, que
funciona direto no navegador.

**PDFs.** `GET …/relatorios/decisoes.pdf?de=&ate=&categoria=` e `GET …/atas/{id}/pdf`
devolvem o arquivo.

### Rotas

| Método | Caminho (após `/api/v1`) | Para quê |
|---|---|---|
| POST | `/auth/login` | Entrar (devolve o token de acesso) |
| GET | `/auth/eu` | Usuário logado |
| POST | `/auth/senha` | Trocar a própria senha |
| GET | `/projetos` | Projetos que eu posso ver (com `meu_papel`) |
| POST | `/projetos` | Criar projeto |
| GET | `/projetos/{projeto_id}` | Dados do projeto |
| PUT | `/projetos/{projeto_id}` | Alterar dados (Responsável) |
| DELETE | `/projetos/{projeto_id}` | Excluir projeto e tudo dele (Responsável) |
| GET | `/projetos/{projeto_id}/resumo` | O que seria apagado junto (tela de confirmação) |
| GET | `/projetos/{projeto_id}/membros` | Membros e papéis (Responsável) |
| PUT | `/projetos/{projeto_id}/membros` | Adicionar membro ou mudar o papel (Responsável) |
| DELETE | `/projetos/{projeto_id}/membros/{usuario_id}` | Remover membro |
| PUT / DELETE | `/projetos/{projeto_id}/logo` | Logo do cliente nos PDFs (Responsável) |
| GET | `/projetos/{projeto_id}/auditoria` | Quem fez o quê neste projeto (Responsável) |
| GET | `/projetos/{projeto_id}/decisoes` | Linha do tempo (`q`, `categoria`, `de`, `ate`) |
| POST | `/projetos/{projeto_id}/decisoes` | Registrar decisão (Editor) |
| GET | `/projetos/{projeto_id}/decisoes/{decisao_id}` | Uma decisão |
| POST | `/projetos/{projeto_id}/anexos` | Enviar arquivo (antes de registrar a decisão) |
| GET | `/projetos/{projeto_id}/decisoes/{decisao_id}/anexos/{indice}/link` | Link temporário do anexo |
| GET | `/projetos/{projeto_id}/atas` | Atas (Leitor só vê as fechadas) |
| POST | `/projetos/{projeto_id}/atas` | Nova ata em rascunho (Editor) |
| POST | `/projetos/{projeto_id}/atas/pre-visualizar` | O que o fechamento vai gerar, sem gravar |
| POST | `/projetos/{projeto_id}/atas/rascunho-ia` | Rascunho de ata pela IA (não grava nada) |
| GET | `/projetos/{projeto_id}/atas/{ata_id}` | Ata com decisões, pendências, alterações da ficha e adendos |
| PUT | `/projetos/{projeto_id}/atas/{ata_id}` | Editar rascunho (Editor) |
| POST | `/projetos/{projeto_id}/atas/{ata_id}/fechar` | Fechar: cria decisões, pendências e altera a ficha |
| POST | `/projetos/{projeto_id}/atas/{ata_id}/adendos` | Correção em ata fechada |
| GET | `/projetos/{projeto_id}/atas/{ata_id}/pdf` | PDF da ata |
| GET / POST | `/projetos/{projeto_id}/pendencias` | Listar (`status`, `q`) / criar |
| GET / PUT | `/projetos/{projeto_id}/pendencias/{pendencia_id}` | Obter / editar (só em aberto) |
| POST | `…/pendencias/{pendencia_id}/resolver` · `/cancelar` · `/reabrir` | Mudar a situação |
| GET / PUT | `/projetos/{projeto_id}/ficha` | Ficha com indicadores / gravar campos |
| GET | `/projetos/{projeto_id}/ficha/historico` | Histórico com origem ("Decisão D-005 · Ata 04") |
| GET / PUT | `/projetos/{projeto_id}/padrao-construtivo` | Padrão construtivo por tipologia |
| GET | `/projetos/{projeto_id}/relatorios/decisoes.pdf` | Relatório de decisões (qualquer membro) |
| GET / POST | `/admin/usuarios` | Usuários (admin) |
| PUT | `/admin/logo-empresa` | Logo do escritório nos PDFs (admin) |
| GET | `/arquivos/{token}` | Download por link assinado (sem login) |
| GET | `/opcoes` | Listas fixas para os formulários (categorias, impactos, tipologias, campos da ficha) |
| GET | `/api/saude` | Verificação de funcionamento (fora do `/v1`) |

## 6. Variáveis de ambiente novas

| Variável | Uso |
|---|---|
| `DECIDIU_DATABASE_URL` | PostgreSQL (`postgres://…`). Sem ela, continua o SQLite. O nome é próprio de propósito: o Railway cria `DATABASE_URL` sozinho, e o app não pode trocar de banco antes da migração dos dados |
| `DECIDIU_JWT_SEGREDO` | Segredo dos tokens (≥ 32 caracteres). Sem ela, é derivado do segredo do servidor |
| `DECIDIU_TOKEN_MINUTOS` | Validade do token (padrão 60) |
| `DECIDIU_CORS_ORIGENS` | Endereços do frontend, separados por vírgula |

## 7. Como rodar

```bash
uv lock                     # atualizar o uv.lock (pyjwt e psycopg entraram no pyproject)
uv sync
uv run python main.py                               # app Flet, como sempre
uv run uvicorn api.main:app --reload --port 8001    # API -> http://localhost:8001/api/docs
uv run --extra testes pytest                         # testes
```

**No Railway**, a API entra como um **segundo serviço** do mesmo repositório:
- mesmo Dockerfile e mesmo volume `/dados`;
- *Custom Start Command*: `uvicorn api.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'`;
- *Healthcheck Path*: `/api/saude`.

Enquanto o banco for SQLite, os dois serviços precisam compartilhar o volume, então a API fica
em uma única instância. Com o PostgreSQL e o armazenamento S3/R2, a API pode ter várias
réplicas.

## 8. Testes

| Arquivo | O que garante |
|---|---|
| `tests/test_caracterizacao_database.py` (19) | Escritos **antes** da refatoração: o comportamento que as telas Flet usam continua idêntico |
| `tests/test_servicos.py` (12) | Regras novas: leitura exige acesso, Leitor não vê rascunho, objeto de outro projeto dá 404, anexo só do próprio projeto, conflitos de estado, auditoria, IA com contexto do projeto |
| `tests/test_api.py` (13) | Pela HTTP, como o frontend usará: login e bloqueio, isolamento, fluxo ata → decisões → ficha → pendência, anexo com download, PDFs, exclusão |

## 9. Próximos passos (em ordem)

1. **Organizações (isolamento entre clientes do SaaS).** Criar a tabela `Organizacao`
   (o escritório assinante) e incluir `organizacao_id` em `Usuario` e `Projeto`. O "admin"
   passa a ser admin **da organização**, e o dono da plataforma ganha um papel separado, sem
   acesso aos dados dos clientes por padrão. Essa base também serve para cobrar por
   assinatura. A checagem entra em `permissoes.nivel()`, num lugar só.
2. **Alembic + PostgreSQL.** Configurar o Alembic com o esquema atual como ponto de partida.
   Escrever um script de cópia SQLite → PostgreSQL. Depois, definir `DECIDIU_DATABASE_URL`
   nos dois serviços. Na mesma migração:
   - índices únicos `(projeto_id, numero)`;
   - `autor_id` (FK) ao lado de `autor`;
   - tabela `Anexo` (nome, tamanho, tipo, quem enviou) no lugar do texto com vírgulas.
3. **Arquivos em S3/R2.** Escrever `ArmazenamentoS3` com a mesma interface e trocar em
   `armazenamento_padrao()`. Logos e relatórios vão junto.
4. **Redis.** Mover para o Redis o limite de login e a contagem de uso da IA (hoje em
   `uso_ia.json`), e criar uma fila para PDFs e IA. A rota passa a responder "em
   processamento" e o frontend consulta o andamento.
5. **Login gerenciado** (Clerk, Auth0 ou Keycloak), para ter MFA, recuperação de senha por
   e-mail e convite de cliente por link. Só `api/autenticacao.py` e `api/deps.py` mudam.
6. **Frontend.** Next.js/React como PWA, consumindo a API, uma tela por vez: linha do tempo,
   atas, pendências, ficha.
7. **Desligar o Flet** e apagar `database.py` e `views/`.
