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
- **`api/`**: API REST com 54 operações, login por token, documentação automática em
  `/api/docs` e os mesmos serviços por baixo.
- **Organizações**: cada escritório assinante é uma organização. Usuários, projetos, logos
  e auditoria ficam dentro dela, e nada atravessa essa fronteira (seção 4).
- **`migracoes/`**: o Alembic controla o esquema do banco, no SQLite e no PostgreSQL
  (seção 6).
- **`tests/`**: 84 testes automáticos (ver seção 9).

## 2. Diagnóstico do código atual

O que foi encontrado na leitura do código e como cada ponto foi tratado:

| # | Achado | Risco | Situação |
|---|---|---|---|
| 1 | Regras de negócio misturadas com o acesso ao banco em `database.py` (1.400 linhas), e parte da lógica nas telas (relatório, PDF da ata, IA, envio de anexos) | Não dá para reaproveitar num frontend novo; difícil testar | **Resolvido**: regras em `nucleo/servicos/` |
| 2 | **Leituras sem checagem de permissão** (`listar_decisoes_projeto`, `listar_caracteristicas`, `buscar_reuniao`...). Só a tela impedia o acesso. O filtro "Leitor não vê rascunho de ata" também estava só na tela (`views/atas.py`) | Numa API, qualquer usuário logado leria qualquer projeto trocando o número na URL | **Resolvido na API**: todo serviço checa o acesso, inclusive na leitura. Objeto de projeto alheio responde 404, sem confirmar que existe |
| 3 | Numeração "maior + 1" (D-001, P-001, Ata 01) sem trava | Com dois usuários gravando ao mesmo tempo, número repetido | **Resolvido**: trava da linha do projeto (`SELECT … FOR UPDATE`) no PostgreSQL |
| 4 | Banco SQLite num único arquivo | Um escritor por vez; não escala horizontalmente | **Preparado**: `DECIDIU_DATABASE_URL` liga o PostgreSQL, que nasce pelas migrações do Alembic. SQLite passou a usar WAL (leitores não travam quem grava). Falta copiar os dados (seção 10) |
| 5 | Estado guardado em memória ou arquivo de um processo: limite de login, contagem de uso da IA (`uso_ia.json`), anexos, logos e PDFs no disco local | Com 2+ instâncias, cada uma tem o seu: limites furam e arquivos "somem" | **Preparado**: `nucleo/armazenamento.py` isola os arquivos atrás de uma interface (trocar por S3/R2 sem mexer nos serviços). Limite e uso de IA vão para o Redis/banco (seção 9) |
| 6 | Sem trilha de auditoria (exclusão de projeto só aparecia num `print`) | Sem como responder "quem mudou isso?" a um cliente | **Resolvido**: tabela `RegistroAuditoria`, gravada na mesma transação de cada alteração. `GET /projetos/{id}/auditoria` para o Responsável |
| 7 | **Sem separação entre clientes do SaaS**: o administrador vê todos os projetos de todos os usuários | Para um produto comercial, um escritório não pode ter acesso ao projeto de outro, nem você como dono da plataforma deve ter por padrão | **Resolvido**: organizações (seção 4) |
| 8 | `autor` gravado como texto (nome), anexos como texto separado por vírgula, checklist como JSON em texto | Nome muda e o histórico perde o vínculo; anexos sem metadados | Mantido para não quebrar o banco. A API já expõe anexos e checklist estruturados. Migração na seção 9 |
| 9 | Migrações feitas à mão (`ALTER TABLE` com `PRAGMA`) | Só funciona no SQLite; frágil | **Resolvido**: Alembic (seção 6). O que era feito à mão virou parte da migração base |
| 10 | Título de decisão podia ficar vazio | Registro sem título na linha do tempo | **Resolvido**: o serviço valida título, categoria e impacto, e a tela mostra a mensagem |
| 11 | `ficha.py` e `questionario_sistemas.py` na raiz são cópias idênticas dos arquivos em `views/` | Confusão ao editar | Não alterado. Pode apagar as cópias da raiz |

## 3. Camada de serviços (`nucleo/`)

| Arquivo | Responsabilidade |
|---|---|
| `tabelas.py` | Todas as tabelas (movidas de `database.py` e `models.py`) + `Organizacao` e `RegistroAuditoria` (novas) |
| `migracoes.py` | Roda o Alembic a partir do app (`atualizar_banco()`) |
| `db.py` | Engine e sessões. SQLite por padrão; PostgreSQL com `DECIDIU_DATABASE_URL` |
| `ator.py` | `Ator`: quem está agindo (id, nome, admin). Substitui o `usuario_id` solto |
| `permissoes.py` | `nivel()` e `exigir()`: Leitor 1, Editor 2, Responsável 3, Admin 4 |
| `erros.py` | `NaoEncontrado` (404), `Conflito` (409), `SemPermissao` (403), `ErroDominio` (422). Herdam de `ValueError`/`PermissionError`, então as telas Flet tratam igual |
| `numeracao.py` | Sequenciais por projeto com trava |
| `auditoria.py` | `registrar()` dentro da transação |
| `armazenamento.py` | Interface de arquivos + implementação em disco local |
| `marcacoes.py`, `senhas.py` | Linhas `[D]`/`[P]`, hash PBKDF2 |
| `servicos/usuarios.py` | Login, cadastro (admin, na organização dele), troca de senha |
| `servicos/organizacoes.py` | Minha organização; plataforma: criar, listar (só contagens), suspender |
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

## 4. Organizações e permissões

**Organização** é o escritório assinante. Todo usuário e todo projeto pertencem a uma.
A regra fica em um lugar só (`nucleo/permissoes.nivel`): usuário e projeto precisam ser da
**mesma** organização, e ela precisa estar **ativa**. Não há exceção, nem para o administrador
nem para o superadmin.

| Papel | Quem é | O que alcança |
|---|---|---|
| Leitor, Editor, Responsável | Membros de um projeto | Só os projetos de que são membros, na sua organização |
| **Admin** | Administrador do escritório (`usuario.admin`) | Todos os projetos e usuários **da sua organização** |
| **Superadmin** | Dono da plataforma (`usuario.superadmin`) | Cria, lista e suspende organizações. Vê só contagens, nunca projetos de outra organização |

Outras regras:
- O login (`username`) é único na plataforma toda, porque a pessoa entra só com ele.
- Usuário de outra organização é tratado como inexistente: ao adicionar membro, a resposta é
  "não encontrado", sem revelar quem existe.
- Organização suspensa: ninguém dela entra, e os tokens já emitidos param de valer na hora.
  Os dados ficam guardados.
- O logo da empresa nos PDFs passa a ser um por organização. O logo único antigo vai para a
  primeira organização na primeira partida.

| Ação | Leitor (cliente) | Editor | Responsável | Admin |
|---|:-:|:-:|:-:|:-:|
| Ver projeto, decisões, ficha, pendências, histórico | ✔ | ✔ | ✔ | ✔ |
| Ver atas **fechadas** / gerar PDFs | ✔ | ✔ | ✔ | ✔ |
| Ver atas em **rascunho** | – | ✔ | ✔ | ✔ |
| Registrar decisão, ata, pendência; alterar ficha; enviar anexo; usar IA | – | ✔ | ✔ | ✔ |
| Alterar dados do projeto, membros, logo do cliente; ver auditoria; excluir projeto | – | – | ✔ | ✔ |
| Cadastrar usuários, logo da empresa, renomear a organização, auditoria da organização | – | – | – | ✔ |
| Criar projeto | se o usuário tiver `pode_criar_projetos` |||  ✔ |

Sem acesso ao projeto, a resposta é **404**, não 403: a API não confirma que o projeto existe.
Tudo nesta tabela vale só dentro da organização do usuário.

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
| GET | `/organizacao` | A minha organização |
| PUT | `/organizacao` | Renomear (admin) |
| GET / POST | `/admin/usuarios` | Usuários da organização (admin) |
| GET | `/admin/auditoria` | Auditoria da organização inteira (admin) |
| PUT | `/admin/logo-empresa` | Logo do escritório nos PDFs (admin) |
| GET / POST | `/plataforma/organizacoes` | Listar com contagens / criar com o primeiro admin (superadmin) |
| PUT | `/plataforma/organizacoes/{id}/situacao` | Ativar ou suspender (superadmin) |
| GET | `/arquivos/{token}` | Download por link assinado (sem login) |
| GET | `/opcoes` | Listas fixas para os formulários (categorias, impactos, tipologias, campos da ficha) |
| GET | `/api/saude` | Verificação de funcionamento (fora do `/v1`) |

## 6. Migrações do banco (Alembic)

O esquema do banco agora é controlado pelo Alembic. Cada mudança no modelo vira um arquivo em
`migracoes/versions/`.

| Revisão | O que faz |
|---|---|
| `0001` esquema base | Banco novo: cria todas as tabelas. Banco que já existe (o SQLite do Railway): só cria o que falta e acrescenta as colunas antigas que antes eram postas à mão. Não apaga nada |
| `0002` organizações | Cria `organizacao`, liga usuários, projetos e auditoria a ela. Num banco com dados, coloca todos numa organização só (`DECIDIU_ORG_INICIAL`), e o administrador mais antigo vira superadmin. Ninguém perde acesso |
| `0003` tema do usuário | Coluna opcional `usuario.tema` ("claro"/"escuro"); vazia = escuro. `PUT /auth/tema` |

**Na partida**, o app Flet (`init_db`) e a API rodam `upgrade head`, que só aplica o que falta.
No PostgreSQL há uma trava (`pg_advisory_xact_lock`), então os dois podem iniciar juntos.

**No terminal:**
```bash
alembic current                              # versão do banco
alembic upgrade head                         # aplicar o que falta
alembic upgrade head --sql                   # só ver o SQL (sem conectar)
alembic check                                # o modelo tem mudança sem migração?
alembic revision --autogenerate -m "o que mudou"   # nova migração a partir do modelo
```

**Para mudar o modelo:**
1. Altere `nucleo/tabelas.py`.
2. Rode `alembic revision --autogenerate -m "..."` e **revise** o arquivo gerado.
3. Rode os testes. `tests/test_migracoes.py` compara o banco migrado com o modelo e falha se
   divergirem.

## 7. Variáveis de ambiente novas

| Variável | Uso |
|---|---|
| `DECIDIU_DATABASE_URL` | PostgreSQL (`postgres://…`). Sem ela, continua o SQLite. O nome é próprio de propósito: o Railway cria `DATABASE_URL` sozinho, e o app não pode trocar de banco antes da migração dos dados |
| `DECIDIU_JWT_SEGREDO` | Segredo dos tokens (≥ 32 caracteres). Sem ela, é derivado do segredo do servidor |
| `DECIDIU_TOKEN_MINUTOS` | Validade do token (padrão 60) |
| `DECIDIU_CORS_ORIGENS` | Endereços do frontend, separados por vírgula |
| `DECIDIU_ORG_INICIAL` | Nome da primeira organização (padrão "Organização principal"). Pode ser renomeada depois em `PUT /organizacao` |
| `DECIDIU_MIGRAR_NA_PARTIDA` | `1` (padrão) a API aplica as migrações ao iniciar; `0` para deixar só para o app ou o pré-deploy |

## 8. Como rodar

```bash
uv lock                     # atualizar o uv.lock (pyjwt e psycopg entraram no pyproject)
uv sync
uv run python main.py                               # app Flet, como sempre
uv run uvicorn api.main:app --reload --port 8001    # API -> http://localhost:8001/api/docs
uv run --extra testes pytest                         # testes
uv run python gerenciar.py organizacoes              # organizações (slug e nome)
uv run python gerenciar.py criar-usuario ana "Ana" --org=<slug>
```

**No Railway**, a API entra como um **segundo serviço** do mesmo repositório:
- mesmo Dockerfile e mesmo volume `/dados`;
- *Custom Start Command*: `uvicorn api.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'`;
- *Healthcheck Path*: `/api/saude`.

Enquanto o banco for SQLite, os dois serviços precisam compartilhar o volume, então a API fica
em uma única instância. Com o PostgreSQL e o armazenamento S3/R2, a API pode ter várias
réplicas.

## 9. Testes

| Arquivo | O que garante |
|---|---|
| `tests/test_caracterizacao_database.py` (19) | Escritos **antes** da refatoração: o comportamento que as telas Flet usam continua idêntico |
| `tests/test_servicos.py` (12) | Regras novas: leitura exige acesso, Leitor não vê rascunho, objeto de outro projeto dá 404, anexo só do próprio projeto, conflitos de estado, auditoria, IA com contexto do projeto |
| `tests/test_api.py` (13) | Pela HTTP, como o frontend usará: login e bloqueio, isolamento, fluxo ata → decisões → ficha → pendência, anexo com download, PDFs, exclusão |
| `tests/test_organizacoes.py` (9) | Projetos, membros, usuários, auditoria e logos não atravessam organizações; plataforma só para superadmin; suspensão bloqueia login e tokens; telas Flet e linha de comando criam usuário na organização certa |
| `tests/test_tela_plataforma.py` (7) | Tela da plataforma dirigida como o usuário: criar organização, erros no formulário, suspender e reativar, busca, acesso restrito e rótulo de celular |
| `tests/test_conexao_banco.py` (4) | Espera pelo banco na partida e diagnóstico sem expor a senha |
| `tests/test_migracoes.py` (8) | Banco novo, **cópia do esquema de produção com dados** e banco muito antigo: todos migram, ficam idênticos ao modelo e ninguém perde acesso; volta e reaplicação da 0002; `init_db` não recria admin nem projeto exemplo |

## 10. Próximos passos (em ordem)

1. ~~Organizações~~ e ~~Alembic~~: feitos.
2. **Copiar os dados do SQLite para o PostgreSQL.** Script de cópia tabela a tabela,
   mantendo os ids. Depois, definir `DECIDIU_DATABASE_URL` nos dois serviços. Na mesma leva
   (nova migração 0003):
   - índices únicos `(projeto_id, numero)`;
   - `autor_id` (FK) ao lado de `autor`;
   - tabela `Anexo` no lugar do texto com vírgulas.
3. **Arquivos em S3/R2.** Escrever `ArmazenamentoS3` com a mesma interface e trocar em
   `armazenamento_padrao()`. Logos e relatórios vão junto, separados por organização.
4. **Redis.** Mover para o Redis o limite de login e a contagem de uso da IA, que deve ser
   **por organização**, pois é base da cobrança. Criar uma fila para PDFs e IA.
5. **Assinatura.** Plano e limites na organização (usuários, projetos, transcrições por mês),
   integração de pagamento e suspensão automática por inadimplência (a suspensão já existe).
6. **Login gerenciado** (Clerk, Auth0 ou Keycloak), para ter MFA, recuperação de senha por
   e-mail e convite de cliente por link.
7. **Frontend.** Next.js/React como PWA, consumindo a API, uma tela por vez. O painel da
   plataforma já existe no app Flet (`views/plataforma.py`) e serve de referência.
8. **Desligar o Flet** e apagar `database.py` e `views/`.
