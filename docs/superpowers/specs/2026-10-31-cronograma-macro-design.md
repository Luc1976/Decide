# Cronograma macro do projeto — desenho

Data: 31/10/2026 · Branch: `homologacao` · Situação: aguardando revisão do Lucas

## 1. Objetivo

Uma tela "Cronograma" em que o usuário define o kick-off, as etapas do projeto e os
marcos, e o app desenha um gráfico de Gantt. Quando uma decisão impacta prazos, o
cronograma é revisado: nasce uma versão nova, ligada à decisão, e as anteriores ficam
guardadas como referência. As etapas dependem umas das outras: atrasar uma entrega
recalcula as seguintes.

**Definido pelo Lucas nesta conversa:**

- Cada etapa tem data de início e data de entrega próprias (pode haver sobreposição e
  intervalo entre etapas).
- A revisão é feita na tela do cronograma e sempre ligada a uma decisão (existente ou
  criada ali mesmo). A decisão ganha o selo "Impacta cronograma".
- Além das etapas padrão, o usuário pode criar etapas e marcos próprios.
- Versões completas (opção A) e Gantt desenhado com componentes do Flet (opção A).
- Cada etapa depende da anterior; um atraso já aponta os novos prazos das seguintes.
- O atraso entra pela revisão (não por data realizada nem pela data de hoje).

**Suposições (corrigir se estiverem erradas):**

- Kick-off e Liberado para obra são marcos (uma data, losango no Gantt).
- O recálculo vale nos dois sentidos: antecipar uma entrega também puxa as seguintes.
- O cliente (Leitor) vê tudo, sem criar nem revisar.

**Fora do escopo:** datas realizadas ("entregue em"), atraso automático pela data de
hoje, gráfico de Gantt desenhado no PDF (o PDF traz tabela), ligação automática com
"Prazo previsto (meses)" da ficha, dependências entre etapas que não sejam vizinhas na
sequência.

## 2. Tela "Cronograma" (`views/cronograma.py`, rota `/cronograma`)

Acesso pelo menu lateral (seção PROJETO), junto de Ficha e Pendências.

**Sem cronograma:** aviso + botão "Criar cronograma" (Editor ou acima). O formulário traz:

| Item | Tipo | Padrão |
| --- | --- | --- |
| Kick-off | marco | marcado |
| Projeto conceitual | etapa | desmarcado |
| Estudo preliminar | etapa | marcado |
| Anteprojeto | etapa | marcado |
| Projeto básico | etapa | marcado |
| Projeto executivo | etapa | marcado |
| Liberado para obra | marco | marcado |

Cada linha: caixa para marcar, início e entrega (marco: uma data), e "Depende da etapa
anterior" (marcado por padrão; o Kick-off não tem). Botões "+ Adicionar etapa" e
"+ Adicionar marco" (nome livre), e remover para os itens próprios. Datas em dd/mm/aaaa.
Salvar cria a **versão 1**, a linha de base, sem decisão.

**Com cronograma:**

- Resumo: "Versão 3 · 25/08/2026 · Decisão D-032 · Liberado para obra: 29/11/2026
  (+45 dias em relação à versão 1)".
- Gantt: uma linha por item na ordem do cronograma; escala de meses no topo; linha
  vertical em hoje; etapas como barras, marcos como losangos; sob cada item, barra cinza
  fina com as datas da **referência**. Seletor "Comparar com": Versão 1 (padrão),
  versão anterior, nenhuma. Tocar num item mostra início, entrega e desvio
  ("Entrega 12/05/2026 · +21 dias em relação à versão 1"). No celular o gráfico rola na
  horizontal, com a coluna de nomes junto.
- "Revisar cronograma" (Editor ou acima): o mesmo formulário, com as datas atuais.
  Mudar uma entrega recalcula as seguintes na hora (seção 3), com o selo
  "recalculada"; qualquer data pode ser ajustada à mão. Para salvar é obrigatório
  escolher a decisão: uma do projeto (lista) ou "Nova decisão" (título, disciplina,
  impacto, justificativa). Salvar cria a versão seguinte.
- "Versões": lista com número, data, autor e decisão; tocar mostra o Gantt daquela
  versão (somente leitura).
- Leitor: vê resumo, Gantt e versões; sem "Criar" e "Revisar".

**Validação (recusa com mensagem):** ao menos um item; nomes únicos; datas obrigatórias
nos itens marcados; entrega não pode ser antes do início; revisão sem decisão; revisão
igual à versão atual ("nada mudou").

## 3. Regras de cálculo (`cronograma_calculos.py`, sem Flet e sem banco)

- **Cadeia principal:** o primeiro item e todos os itens com "Depende da etapa anterior".
  Cada item da cadeia depende do item da cadeia imediatamente anterior. Itens sem
  dependência ficam fora da cadeia (correm em paralelo) e só mudam quando editados.
- **Recálculo:** percorrendo a cadeia em ordem, carrega-se um deslocamento (dias). Um
  item editado pelo usuário fica com as datas dele, e o deslocamento passa a ser
  (entrega nova − entrega anterior) desse item. Um item não editado anda o deslocamento
  atual no início e na entrega (duração, intervalos e sobreposições preservados).
  Mudar só o início de um item não move os seguintes.
- **Desvio:** cada item é comparado com o item de mesmo nome (sem diferenciar
  maiúsculas e acentos) na versão de referência: dias de diferença na entrega (e no
  início). Item que não existia: "novo". Item que saiu: listado como "removido" no resumo
  das diferenças.
- **Escala:** do menor início ao maior entrega das duas versões exibidas, com margem de
  meio mês, marcas mensais.
- Funções: `recalcular(base, editados)`, `desvios(atual, referencia)`, `validar(itens)`,
  `escala(itens…)`, `itens_padrao()`.

## 4. Dados — migração `0012` (só cria tabelas)

```
cronogramaversao: id, projeto_id (FK, índice), numero, criado_em, autor,
                  decisao_id (FK decisao, nulo na versão 1), observacao
                  único (projeto_id, numero)
cronogramaitem:   id, versao_id (FK, índice), ordem, nome, tipo ("etapa"|"marco"),
                  inicio (date), entrega (date; marco: igual ao início),
                  depende_da_anterior (bool), padrao (bool)
```

Versões nunca são alteradas depois de gravadas. A exclusão do projeto apaga também
o cronograma (`nucleo/servicos/projetos.excluir`).

## 5. Serviço (`nucleo/servicos/cronograma.py`)

- `obter(s, ator, projeto_id, numero=None)` (Leitor): versão (atual ou a pedida) com
  itens, lista de versões e desvios em relação à versão 1.
- `criar(s, ator, projeto_id, itens)` (Editor): versão 1; recusa se já existir.
- `revisar(s, ator, projeto_id, itens, decisao_id=None, nova_decisao=None)` (Editor):
  valida, cria a decisão nova se for o caso e a versão seguinte, numa transação só
  (ou nada é gravado). Numeração travada como nas decisões. Auditoria
  "cronograma.criar" e "cronograma.revisar".
- `versoes_por_decisao(s, projeto_id)` → {decisao_id: número da versão}, para o selo
  na linha do tempo.
- `decisoes.criar` passa a ter uma variante sem commit, para compor com a revisão.

## 6. Outras partes

| Parte | Mudança |
| --- | --- |
| `views/timeline.py` | Item "Cronograma" no menu; selo "Impacta cronograma · Versão N" na decisão |
| `app.py` | Rota `/cronograma` |
| `relatorio_pdf.py` + diálogo do relatório | Opção "Incluir o cronograma" (marcada): tabela da versão atual (item, início, entrega, desvio em relação à v1) e lista de versões com as decisões |
| `api` | `GET /projetos/{id}/cronograma` (atual; `?versao=N`), `POST /projetos/{id}/cronograma` (versão 1), `POST /projetos/{id}/cronograma/revisoes` |
| `scripts/dados_demo.py` | Cronograma da demonstração (abaixo) |
| `docs/ARQUITETURA_API.md` | Rotas e migração `0012` |

**Cronograma da demonstração (Residencial Alto das Quaresmeiras):**

| Item | Versão 1 (19/08/2025) | Versão 2 (17/03/2026, D-023) | Versão 3 (25/08/2026, D-032) |
| --- | --- | --- | --- |
| Kick-off | 19/08/2025 | = | = |
| Estudo preliminar | 20/08 – 30/10/2025 | = | = |
| Anteprojeto | 03/11/2025 – 30/01/2026 | = | = |
| Projeto básico | 02/02 – 30/04/2026 | 02/02 – 30/05/2026 | = |
| Aprovação na prefeitura (paralela) | 10/02 – 15/05/2026 | 10/02 – 16/06/2026 | = |
| Projeto executivo | 04/05 – 30/09/2026 | 03/06 – 30/10/2026 (recalculado) | 03/06 – 14/11/2026 |
| Liberado para obra | 15/10/2026 | 14/11/2026 (recalculado) | 29/11/2026 (recalculado) |

## 7. Testes

- Cálculo: atraso numa entrega empurra a cadeia preservando durações e sobreposição;
  antecipação puxa; item paralelo não se move; edição manual no meio da cadeia passa a
  valer como novo deslocamento; mudar só o início não move os seguintes; desvios por
  nome (novo e removido); validações; escala.
- Serviço: criar v1; recusar segunda v1; revisar com decisão existente e com decisão
  nova (numeração D-xxx); nada gravado se a validação falhar; Leitor não cria nem revisa;
  outra organização não vê; selo por decisão; excluir projeto apaga o cronograma.
- Migração `0012`: cria as tabelas; modelo e migrações batem (`test_migracoes`).
- Tela: cria v1 pelo formulário; revisão recalcula na tela antes de salvar; exige a
  decisão; Leitor sem botões; Gantt com uma linha por item e losango nos marcos.
- API e PDF: rotas e seção do relatório.
- Demonstração: três versões, v3 ligada à D-032, Liberado para obra em 29/11/2026.
- Critério de aceite: suíte inteira verde (hoje 168 passando, nenhuma falha).
