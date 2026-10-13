"""Migrações (Alembic): banco novo, banco de produção atual e banco muito antigo."""
import datetime
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, select

from nucleo.ator import Ator
from nucleo.db import criar_engine
from nucleo.migracoes import atualizar_banco, revisao_atual, voltar_banco
from nucleo.servicos import projetos
from nucleo.tabelas import Organizacao, Usuario

DADOS = Path(__file__).parent / "dados"

# Antes de qualquer migração: o banco de anos atrás (sem permissões, sem atas, sem numeração).
ESQUEMA_MUITO_ANTIGO = """
CREATE TABLE usuario (id INTEGER NOT NULL PRIMARY KEY, username VARCHAR NOT NULL UNIQUE,
    senha VARCHAR NOT NULL, nome_completo VARCHAR NOT NULL, admin BOOLEAN NOT NULL);
CREATE TABLE projeto (id INTEGER NOT NULL PRIMARY KEY, nome VARCHAR NOT NULL, cliente VARCHAR NOT NULL,
    descricao VARCHAR, data_criacao DATETIME NOT NULL);
CREATE TABLE decisao (id INTEGER NOT NULL PRIMARY KEY, projeto_id INTEGER NOT NULL REFERENCES projeto (id),
    titulo VARCHAR NOT NULL, categoria VARCHAR NOT NULL, descricao VARCHAR NOT NULL,
    justificativa VARCHAR NOT NULL, alternativa_descartada VARCHAR, impacto VARCHAR NOT NULL,
    autor VARCHAR NOT NULL, data_decisao DATE NOT NULL, anexos VARCHAR, checklist VARCHAR);
"""


def _banco(tmp_path, ddl: str = ""):
    eng = criar_engine(f"sqlite:///{tmp_path / 'teste.db'}")
    if ddl:
        sem_comentarios = "\n".join(l for l in ddl.splitlines() if not l.strip().startswith("--"))
        with eng.begin() as c:
            for comando in sem_comentarios.split(";"):
                if comando.strip():
                    c.exec_driver_sql(comando)
    return eng


def _diferencas(eng) -> list:
    with eng.connect() as c:
        return compare_metadata(MigrationContext.configure(c, opts={"compare_type": True}), SQLModel.metadata)


def _povoar_producao(eng) -> None:
    agora = datetime.datetime(2026, 9, 1, 10, 0)
    with eng.begin() as c:
        c.execute(text("INSERT INTO usuario (id, username, senha, nome_completo, admin, pode_criar_projetos) VALUES "
                       "(1,'lucas','x','Lucas',1,1),(2,'ana','x','Ana',0,1),(3,'chefe','x','Chefe',1,1),"
                       "(4,'cli','x','Cliente',0,0)"))
        c.execute(text("INSERT INTO projeto (id, nome, cliente, data_criacao) VALUES "
                       "(1,'Edifício Aurora','X',:a),(2,'Galpão Sinop','Y',:a)"), {"a": agora})
        c.execute(text("INSERT INTO membroprojeto (projeto_id, usuario_id, papel) VALUES (1,2,'Responsável'),(1,4,'Leitor')"))
        c.execute(text("INSERT INTO decisao (projeto_id, titulo, categoria, descricao, justificativa, impacto, autor, "
                       "data_decisao, numero) VALUES (1,'Laje','Estrutura','d','j','Alto','Ana','2026-09-01',1)"))


# ---------------------------------------------------------------- banco novo

def test_banco_novo_bate_com_o_modelo(tmp_path):
    eng = _banco(tmp_path)
    atualizar_banco(eng)
    assert revisao_atual(eng) == "0004"
    assert _diferencas(eng) == []
    atualizar_banco(eng)  # de novo: não faz nada nem quebra
    assert revisao_atual(eng) == "0004"


def test_banco_novo_nao_cria_organizacao_vazia(tmp_path):
    eng = _banco(tmp_path)
    atualizar_banco(eng)
    with eng.connect() as c:
        assert c.execute(text("SELECT count(*) FROM organizacao")).scalar() == 0


# ---------------------------------------------------------------- banco de produção (Railway hoje)

def test_banco_de_producao_migra_sem_perder_nada(tmp_path, monkeypatch):
    monkeypatch.setenv("DECIDIU_ORG_INICIAL", "Ru.A Estúdio")
    eng = _banco(tmp_path, (DADOS / "esquema_producao.sql").read_text())
    _povoar_producao(eng)
    assert revisao_atual(eng) is None  # nunca viu o Alembic

    atualizar_banco(eng)

    assert revisao_atual(eng) == "0004"
    assert _diferencas(eng) == []
    with Session(eng) as s:
        orgs = s.exec(select(Organizacao)).all()
        assert [(o.nome, o.slug, o.ativa) for o in orgs] == [("Ru.A Estúdio", "ru-a-estudio", True)]
        usuarios = {u.username: u for u in s.exec(select(Usuario)).all()}
        assert {u.organizacao_id for u in usuarios.values()} == {orgs[0].id}
        # Só o administrador mais antigo vira dono da plataforma.
        assert [n for n, u in usuarios.items() if u.superadmin] == ["lucas"]
        assert usuarios["chefe"].admin and not usuarios["chefe"].superadmin
        # Ninguém perde acesso: Ana continua vendo o projeto dela; o admin vê os dois.
        assert [p.nome for p in projetos.listar_do_usuario(s, Ator.de_usuario(usuarios["ana"]))] == ["Edifício Aurora"]
        assert len(projetos.listar_do_usuario(s, Ator.de_usuario(usuarios["lucas"]))) == 2
        assert s.connection().execute(text("SELECT count(*) FROM decisao")).scalar() == 1
        assert s.connection().execute(text("SELECT count(*) FROM membroprojeto")).scalar() == 2


def test_volta_e_reaplica_a_0002(tmp_path):
    eng = _banco(tmp_path, (DADOS / "esquema_producao.sql").read_text())
    _povoar_producao(eng)
    atualizar_banco(eng)
    voltar_banco("0001", eng)
    assert revisao_atual(eng) == "0001"
    assert "organizacao" not in inspect(eng).get_table_names()
    assert "organizacao_id" not in {c["name"] for c in inspect(eng).get_columns("usuario")}
    with eng.connect() as c:
        assert c.execute(text("SELECT count(*) FROM usuario")).scalar() == 4  # dados ficaram
    atualizar_banco(eng)
    assert revisao_atual(eng) == "0004" and _diferencas(eng) == []


# ---------------------------------------------------------------- banco muito antigo

def test_banco_muito_antigo_e_completado(tmp_path):
    eng = _banco(tmp_path, ESQUEMA_MUITO_ANTIGO)
    with eng.begin() as c:
        c.execute(text("INSERT INTO usuario VALUES (1,'lucas','x','Lucas',1),(2,'bia','x','Bia',0)"))
        c.execute(text("INSERT INTO projeto VALUES (1,'P','C',NULL,'2024-01-01 00:00:00')"))
    atualizar_banco(eng)
    assert _diferencas(eng) == []
    with eng.connect() as c:
        # Usuário comum de antes das permissões vira Editor do projeto que já existia.
        assert c.execute(text("SELECT usuario_id, papel FROM membroprojeto")).all() == [(2, "Editor")]
        assert c.execute(text("SELECT pode_criar_projetos FROM usuario WHERE id = 2")).scalar() == 1


def test_app_completo_sobre_banco_migrado(tmp_path, monkeypatch):
    """O init_db do app (main.py) sobre um banco de produção: numera e não recria nada."""
    eng = _banco(tmp_path, (DADOS / "esquema_producao.sql").read_text())
    _povoar_producao(eng)
    import database

    monkeypatch.setattr(database, "engine", eng)
    database.init_db()
    with eng.connect() as c:
        assert c.execute(text("SELECT count(*) FROM organizacao")).scalar() == 1
        assert c.execute(text("SELECT count(*) FROM usuario")).scalar() == 4  # não criou admin novo
        assert c.execute(text("SELECT count(*) FROM projeto")).scalar() == 2  # nem projeto exemplo


@pytest.mark.parametrize("arquivo", ["0001_esquema_base.py", "0002_organizacoes.py", "0003_tema_do_usuario.py", "0004_documentos_referencia.py"])
def test_migracoes_tem_docstring_e_downgrade(arquivo):
    texto = (Path(__file__).parent.parent / "migracoes" / "versions" / arquivo).read_text()
    assert texto.startswith('"""') and "def downgrade" in texto


def test_projetos_existentes_ganham_a_lista_padrao(tmp_path):
    eng = _banco(tmp_path, (DADOS / "esquema_producao.sql").read_text())
    _povoar_producao(eng)
    atualizar_banco(eng)
    with eng.connect() as c:
        por_projeto = c.execute(text(
            "SELECT projeto_id, count(*), min(situacao), max(situacao) FROM documentoreferencia GROUP BY projeto_id"
        )).all()
        nomes = [r[0] for r in c.execute(text(
            "SELECT nome FROM documentoreferencia WHERE projeto_id = 1 ORDER BY ordem")).all()]
    assert por_projeto == [(1, 7, "Pendente", "Pendente"), (2, 7, "Pendente", "Pendente")]
    assert nomes[0] == "Levantamento topográfico" and nomes[-1] == "Outros"
