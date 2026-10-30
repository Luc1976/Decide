# Ficha do empreendimento por tipologia — desenho

Data: 30/10/2026 · Branch: `homologacao` · Situação: aguardando revisão do Lucas

## 1. Objetivo

Unificar a ficha do empreendimento numa única tela. A tipologia escolhida em
"Uso / tipologia" define quais campos de sistemas construtivos aparecem, com listas
de opções e campos que se abrem em cascata. Os sistemas construtivos passam a ser
campos comuns da ficha: têm histórico e podem ser alterados por decisões e atas.

**Definido pelo Lucas nesta conversa:**

- Tipologias: Residencial, Comercial, Industrial, Condomínio de lotes, Corporativo,
  Shopping Center, Data Center. "Multifamiliar" passa a ser "Residencial".
- Os sistemas construtivos viram campos da ficha, com histórico.
- Cada lista termina em "Outro", que abre um campo de texto livre.
- O catálogo de campos e opções fica no código (opção A).
- Ao trocar a tipologia, os campos que deixam de valer são limpos, e a limpeza fica
  registrada no histórico.
- Depois ele quer acrescentar mais sistemas construtivos e outras características
  ligadas à tipologia (ex.: "Nº de lotes" para condomínio de lotes). O desenho tem de
  permitir isso editando só o catálogo.

**Suposições (corrigir se estiverem erradas):**

- Na troca de tipologia, um campo que existe nas duas tipologias com o mesmo card e
  o mesmo nome (ex.: "Sistema estrutural") mantém o valor.
- Campos dependentes seguem a mesma regra da tipologia: se o campo do qual dependem
  muda e eles deixam de aparecer, são limpos ao salvar.

**Fora do escopo:** catálogo editável pelo escritório (opções B e C), campos novos
de características além do que está na seção 6, mudanças nos indicadores calculados.

## 2. Comportamento na tela

- A ficha passa a ser uma única página, sem as abas "Dados gerais" e
  "Sistemas construtivos", e com um único botão "Salvar ficha".
- No card *Programa*, "Uso / tipologia" vira uma lista: as 7 tipologias + "Outro".
- Logo depois de *Programa* entra o card **Sistemas construtivos**, que mostra só os
  campos da tipologia escolhida. Sem tipologia, mostra o aviso
  "Escolha a tipologia no card Programa para ver os sistemas construtivos.".
- Campos com dependência aparecem só quando a condição é atendida (ex.: "Tipo de laje"
  só com Sistema estrutural = Concreto armado convencional). A tela se refaz na hora,
  sem precisar salvar.
- Escolher "Outro" mostra, ao lado, um campo de texto. Ao abrir a ficha, um valor
  gravado que não está na lista aparece como "Outro" com o texto preenchido.
  "Outro" com o texto vazio grava o campo vazio (nunca a palavra "Outro").
- Com "Uso / tipologia" = Outro (tipologia fora da lista), o card mostra o aviso
  "Esta tipologia não tem sistemas construtivos no catálogo. Use Outras características."
- Campos do catálogo podem morar em qualquer card (Programa, Terreno…); aparecem
  depois dos campos fixos daquele card.
- Ao salvar, os campos do catálogo que não estão visíveis (outra tipologia ou
  dependência não atendida) são limpos.
- Leitor (cliente) vê tudo, com as listas desabilitadas.
- Cards existentes, "Outras características", histórico e indicadores não mudam.

## 3. Catálogo (`catalogo_tipologias.py`)

Arquivo novo, sem Flet e sem banco (fácil de testar):

```python
@dataclass(frozen=True)
class CampoCatalogo:
    nome: str                      # "Tipo de laje"
    opcoes: tuple = ()             # vazio = campo de texto livre (ex.: carga de piso)
    unidade: str = ""              # "tf/m²"
    grupo: str = "Sistemas construtivos"
    depende_de: Optional[str] = None      # nome de outro campo da mesma tipologia
    valores_que_mostram: tuple = ()       # valores de depende_de que fazem aparecer

TIPOLOGIAS: tuple = (...)                 # as 7 tipologias, na ordem da lista
CAMPOS: dict[str, tuple[CampoCatalogo, ...]]  # tipologia -> campos, na ordem da tela
OUTRO = "Outro"
```

Funções puras usadas pela tela, pelo serviço e pelas atas:

- `campos_da_tipologia(tipologia)` → campos daquela tipologia.
- `campos_visiveis(tipologia, valores)` → campos que aparecem com os valores atuais
  (aplica as dependências).
- `campos_a_limpar(valores_atuais, valores_novos)` → itens `(grupo, nome, unidade, "")`
  dos campos do catálogo que têm valor e não estão visíveis com os valores novos.
  Considera todas as tipologias, então limpa também o que veio de uma tipologia anterior.
- `todos_os_campos()` → união de todos os campos do catálogo (para a API `/opcoes`).

"Uso / tipologia" continua com esse nome no grupo *Programa* (linhas `[F]` antigas e
a demonstração seguem valendo). Suas opções vêm de `TIPOLOGIAS`.

## 4. Regras no serviço da ficha

- `nucleo/servicos/ficha.aplicar()` passa a acrescentar, na mesma transação, os itens
  de `campos_a_limpar` quando a gravação mexe na tipologia ou em um campo do qual
  outro depende. As limpezas entram no histórico com a mesma decisão e a mesma ata de
  origem. Vale para a tela, a API, as decisões e o fechamento de atas.
- `consultar_campos()` passa a incluir os campos do catálogo visíveis para a tipologia
  atual. Com isso, "Campo da ficha" nas decisões e as linhas `[F]` das atas os encontram.
- Fechamento de ata: se o texto tem `[F] Uso / tipologia = X`, os campos da tipologia
  X também valem para as linhas `[F]` daquela ata (a troca de tipologia e os novos
  sistemas podem vir na mesma ata).
- Valores fora da lista são aceitos em qualquer origem (equivalem a "Outro").

## 5. Dados existentes — migração `0011` (só dados)

- Para cada linha da tabela `padraoconstrutivo` com tipologia, grava em `caracteristica`
  os campos correspondentes e um registro em `caracteristicahistorico` por campo, com
  autor "Migração 0011". "Multifamiliar" vira "Residencial".
- "Uso / tipologia" recebe a tipologia do padrão. Se havia texto livre diferente, ele
  é substituído e fica no histórico como valor anterior.
- Correspondência de colunas:

| Coluna antiga | Campo novo |
| --- | --- |
| tipologia | Programa · Uso / tipologia |
| multi_sistema_principal, ind_estrutura, shop_estrutura | Sistema estrutural |
| multi_tipo_laje | Tipo de laje |
| ind_vedacao | Vedações |
| ind_carga_piso | Carga de piso (tf/m²), formatada em pt-BR |
| ind_pavimento_externo | Pavimento externo |
| corp_fachada | Fachada |
| shop_cobertura | Cobertura |
| dc_tier_redundancia | "Tier …" → Classificação Tier; demais → Redundância |

- A tabela `padraoconstrutivo` não é apagada; o app deixa de ler e gravar nela.
- `downgrade` desfaz o que a migração gravou, restaurando os valores anteriores a partir
  dos registros de histórico com autor "Migração 0011" e apagando esses registros.
- A migração define as tabelas que usa dentro dela mesma (não importa o app), como
  pede o padrão do Alembic.

## 6. Conteúdo do catálogo (para revisão)

Todas as listas terminam em "Outro". "Fundações" é a mesma lista em todas as tipologias
de edificação: Estaca hélice contínua · Estaca escavada · Estaca pré-moldada ·
Estaca metálica · Sapatas · Radier · Tubulão.

"Tipo de laje" (quando Sistema estrutural = Concreto armado convencional): Maciça ·
Nervurada · Treliçada · Protendida · Lisa (cogumelo).

| Tipologia | Campo | Opções |
| --- | --- | --- |
| Residencial | Tipo de empreendimento | Edifício vertical · Casas em condomínio · Casa unifamiliar |
| Residencial | Sistema estrutural | Concreto armado convencional · Alvenaria estrutural · Paredes de concreto in loco · Estrutura metálica · Light steel frame · Wood frame |
| Residencial | Tipo de laje | (lista acima, com dependência) |
| Residencial | Fundações | (lista acima) |
| Residencial | Vedações | Bloco cerâmico · Bloco de concreto · Drywall (internas) |
| Residencial | Fachada | Textura acrílica · Porcelanato aderido · Porcelanato ventilado · ACM · Pele de vidro · Mista |
| Residencial | Esquadrias | Alumínio · PVC · Madeira |
| Residencial | Aquecimento de água | Gás individual · Gás central coletivo · Solar com apoio · Bomba de calor · Elétrico |
| Comercial | Sistema estrutural | Concreto armado convencional · Estrutura metálica · Pré-moldado de concreto · Mista |
| Comercial | Tipo de laje | (dependência) |
| Comercial | Fundações | (lista acima) |
| Comercial | Vedações | Bloco cerâmico · Bloco de concreto · Drywall (internas) |
| Comercial | Fachada | Textura acrílica · Porcelanato · ACM · Pele de vidro · Mista |
| Comercial | Climatização | Split · VRF · Central de água gelada · Ventilação natural |
| Industrial | Sistema estrutural | Pré-moldado de concreto · Metálica · Mista (concreto e metálica) |
| Industrial | Fundações | (lista acima) |
| Industrial | Vedações | Blocos · Telhas · Mistas (blocos e telhas) · Painéis pré-moldados · Painéis termoisolantes |
| Industrial | Cobertura | Telha metálica simples · Telha metálica termoacústica · Telha zipada |
| Industrial | Carga de piso (tf/m²) | texto livre (número) |
| Industrial | Pavimento externo | Rígido (concreto) · Flexível (asfalto) · Intertravado |
| Condomínio de lotes | Pavimentação viária | Asfalto (CBUQ) · Bloquete intertravado · Paralelepípedo · Concreto |
| Condomínio de lotes | Drenagem pluvial | Rede convencional com galerias · Rede com bacia de retenção |
| Condomínio de lotes | Abastecimento de água | Rede pública · Poço com reservatório elevado |
| Condomínio de lotes | Esgotamento sanitário | Rede pública · Estação de tratamento própria (ETE) · Fossa e sumidouro por lote |
| Condomínio de lotes | Rede elétrica | Aérea · Subterrânea |
| Condomínio de lotes | Iluminação viária | LED em postes · Convencional em postes |
| Condomínio de lotes | Fechamento do perímetro | Muro de alvenaria · Muro pré-moldado · Gradil |
| Corporativo | Sistema estrutural | Concreto armado convencional · Estrutura metálica · Mista |
| Corporativo | Tipo de laje | (dependência) |
| Corporativo | Fundações | (lista acima) |
| Corporativo | Fachada | Pele de vidro (cortina de vidro) · ACM · Concreto aparente · Mista |
| Corporativo | Climatização | VRF · Central de água gelada · Split |
| Shopping Center | Sistema estrutural | Concreto armado convencional · Metálica · Mista |
| Shopping Center | Fundações | (lista acima) |
| Shopping Center | Cobertura | Telha metálica · Laje impermeabilizada · Mista |
| Shopping Center | Climatização | Central de água gelada · VRF · Rooftop |
| Data Center | Sistema estrutural | Concreto armado convencional · Pré-moldado de concreto · Estrutura metálica |
| Data Center | Fundações | (lista acima) |
| Data Center | Classificação Tier | Tier I · Tier II · Tier III · Tier IV |
| Data Center | Redundância | N · N+1 · 2N · 2N+1 |
| Data Center | Climatização | Expansão direta (DX) · Água gelada · Free cooling |

## 7. O que muda em cada parte

| Parte | Mudança |
| --- | --- |
| `catalogo_tipologias.py` | Novo (seção 3) |
| `models.py` | `GRUPO_SISTEMAS = "Sistemas construtivos"`; reexporta as tipologias do catálogo |
| `nucleo/servicos/ficha.py` | Regras da seção 4; sai `salvar_padrao`/`obter_padrao`; `obter()` deixa de devolver `padrao` |
| `nucleo/servicos/atas.py` | Validação das `[F]` com a tipologia definida na própria ata |
| `views/ficha.py` | Tela única (seção 2) |
| `views/questionario_sistemas.py`, `ficha.py` e `questionario_sistemas.py` da raiz | Removidos |
| `database.py` | Saem `obter_/salvar_padrao_construtivo` |
| `relatorio_pdf.py` | Card "Sistemas construtivos" depois de *Programa* |
| `api` | Sai `/padrao-construtivo`; `FichaSaida` sem `padrao`; `/opcoes` devolve `tipologias` e `campos_por_tipologia` |
| `migracoes/versions/0011_padrao_para_ficha.py` | Nova (seção 5) |
| `nucleo/tabelas.py` | `PadraoConstrutivo` continua (tabela mantida), com nota de que não é mais usada |
| `scripts/dados_demo.py`, `seed_demo.py` | Sistemas nos campos novos; passos de padrão viram alterações da ficha; exigência de migração passa a `0011` |
| `docs/ARQUITETURA_API.md` | Rotas e migração atualizadas |

## 8. Testes

- Catálogo: toda tipologia tem campos; nomes únicos por tipologia; `depende_de` aponta
  para campo existente; `campos_visiveis` e `campos_a_limpar` nos casos de troca de
  tipologia, de dependência e de campo comum às duas tipologias.
- Serviço: troca de tipologia limpa os campos e grava o histórico com a origem;
  decisão com `alteracao_ficha` na tipologia também limpa; ata com `[F]` de tipologia
  e de sistema da nova tipologia fecha sem erro.
- Migração `0011`: banco com padrão construtivo migra para campos e histórico; o
  `downgrade` restaura o valor anterior de "Uso / tipologia".
- Tela: a ficha monta como Editor e como Leitor; escolher a tipologia mostra o card;
  a cascata mostra e esconde "Tipo de laje"; "Outro" mostra o campo de texto; salvar
  limpa os campos invisíveis.
- API: `/ficha` grava e devolve os campos novos; `/opcoes` traz o catálogo; os testes
  de `/padrao-construtivo` são substituídos.
- Demonstração: `tests/test_demo.py` continua passando; a ficha da demo mostra
  "Tipo de laje = Nervurada" com histórico ligado à D-010.
- Critério de aceite: nenhum teste que passa hoje passa a falhar (hoje são 124
  passando e 10 falhas antigas).
