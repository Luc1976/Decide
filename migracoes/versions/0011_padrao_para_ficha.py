"""Padrão construtivo vira campos da ficha (ficha do empreendimento por tipologia).

Revisão: 0011
Anterior: 0010
Criada em: 2026-10-31

Só dados: cada linha de padraoconstrutivo com tipologia gera os campos correspondentes
em caracteristica (grupo "Sistemas construtivos" e "Uso / tipologia" em "Programa"),
com um registro de histórico por campo (autor "Migração 0011"). "Multifamiliar" vira
"Residencial". A tabela padraoconstrutivo NÃO é apagada; o app deixa de usá-la.

O downgrade restaura os valores anteriores a partir do histórico desta migração.
As tabelas são descritas aqui mesmo (não importa o app), como pede o Alembic.
"""
import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

AUTOR = "Migração 0011"
PROGRAMA, TIPOLOGIA = "Programa", "Uso / tipologia"
SISTEMAS = "Sistemas construtivos"
TIPOLOGIAS = {"Multifamiliar": "Residencial"}  # demais nomes continuam iguais

# coluna antiga -> (nome do campo novo, unidade)
COLUNAS = {
    "multi_sistema_principal": ("Sistema estrutural", ""),
    "ind_estrutura": ("Sistema estrutural", ""),
    "shop_estrutura": ("Sistema estrutural", ""),
    "multi_tipo_laje": ("Tipo de laje", ""),
    "ind_vedacao": ("Vedações", ""),
    "ind_carga_piso": ("Carga de piso", "tf/m²"),
    "ind_pavimento_externo": ("Pavimento externo", ""),
    "corp_fachada": ("Fachada", ""),
    "shop_cobertura": ("Cobertura", ""),
    "dc_tier_redundancia": (None, ""),  # "Tier ..." -> Classificação Tier; demais -> Redundância
}

caracteristica = sa.table(
    "caracteristica",
    sa.column("id", sa.Integer), sa.column("projeto_id", sa.Integer), sa.column("grupo", sa.String),
    sa.column("nome", sa.String), sa.column("valor", sa.String), sa.column("unidade", sa.String),
    sa.column("atualizado_por", sa.String), sa.column("data_atualizacao", sa.DateTime),
)
historico = sa.table(
    "caracteristicahistorico",
    sa.column("id", sa.Integer), sa.column("projeto_id", sa.Integer), sa.column("grupo", sa.String),
    sa.column("nome", sa.String), sa.column("valor_anterior", sa.String), sa.column("valor_novo", sa.String),
    sa.column("autor", sa.String), sa.column("data_registro", sa.DateTime),
)
padrao = sa.table("padraoconstrutivo", sa.column("projeto_id", sa.Integer), sa.column("tipologia", sa.String),
                  *[sa.column(c) for c in COLUNAS])


def _numero_br(valor) -> str:
    texto = f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return texto.rstrip("0").rstrip(",") if "," in texto else texto


def _campos_do_padrao(linha) -> list:
    """[(grupo, nome, unidade, valor)] de uma linha da tabela antiga."""
    tipologia = (linha.tipologia or "").strip()
    if not tipologia:
        return []
    itens = [(PROGRAMA, TIPOLOGIA, "", TIPOLOGIAS.get(tipologia, tipologia))]
    for coluna, (nome, unidade) in COLUNAS.items():
        valor = getattr(linha, coluna)
        if valor is None or str(valor).strip() == "":
            continue
        if coluna == "ind_carga_piso":
            valor = _numero_br(valor)
        if coluna == "dc_tier_redundancia":
            nome = "Classificação Tier" if str(valor).startswith("Tier") else "Redundância"
        itens.append((SISTEMAS, nome, unidade, str(valor).strip()))
    return itens


def upgrade() -> None:
    conexao = op.get_bind()
    agora = datetime.datetime.now(datetime.timezone.utc)
    for linha in conexao.execute(sa.select(padrao)).all():
        for grupo, nome, unidade, valor in _campos_do_padrao(linha):
            filtro = sa.and_(caracteristica.c.projeto_id == linha.projeto_id, caracteristica.c.grupo == grupo,
                             caracteristica.c.nome == nome)
            atual = conexao.execute(sa.select(caracteristica.c.id, caracteristica.c.valor).where(filtro)).first()
            anterior = (atual.valor or "").strip() if atual else ""
            if anterior == valor:
                continue
            if atual:
                conexao.execute(caracteristica.update().where(caracteristica.c.id == atual.id).values(
                    valor=valor, atualizado_por=AUTOR, data_atualizacao=agora))
            else:
                conexao.execute(caracteristica.insert().values(
                    projeto_id=linha.projeto_id, grupo=grupo, nome=nome, valor=valor, unidade=unidade or None,
                    atualizado_por=AUTOR, data_atualizacao=agora))
            conexao.execute(historico.insert().values(
                projeto_id=linha.projeto_id, grupo=grupo, nome=nome, valor_anterior=anterior or None,
                valor_novo=valor, autor=AUTOR, data_registro=agora))


def downgrade() -> None:
    conexao = op.get_bind()
    registros = conexao.execute(sa.select(historico).where(historico.c.autor == AUTOR)
                                .order_by(historico.c.id.desc())).all()
    for r in registros:
        filtro = sa.and_(caracteristica.c.projeto_id == r.projeto_id, caracteristica.c.grupo == r.grupo,
                         caracteristica.c.nome == r.nome)
        if r.valor_anterior:
            conexao.execute(caracteristica.update().where(filtro).values(valor=r.valor_anterior))
        else:
            conexao.execute(caracteristica.delete().where(filtro))
    conexao.execute(historico.delete().where(historico.c.autor == AUTOR))
