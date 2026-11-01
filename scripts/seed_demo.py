"""Carga (seed) do projeto de demonstração do Decidiu, numa organização separada.

Uso (na raiz do repositório):
    DECIDIU_DATABASE_URL="<DATABASE_PUBLIC_URL do Railway>" \\
    DECIDIU_DEMO_SENHA="<senha dos usuários de demonstração>" \\
        uv run python scripts/seed_demo.py --zerar

O que faz:
1. Confere se o banco está na versão de migração esperada (o seed só roda no esquema atual).
2. Com --zerar, apaga a organização de demonstração (slug em dados_demo.ORG_SLUG) e TUDO o que
   pertence a ela. Nenhuma outra organização é tocada.
3. Cria a organização, os usuários e o projeto, e executa as ETAPAS de dados_demo.py pelos
   serviços do próprio app (nucleo/servicos): numeração D-001/P-001/Ata 01, ligação
   ata -> decisão -> ficha, histórico da ficha e auditoria saem como o app os gera.
4. Depois de cada etapa, reescreve os carimbos de data/hora daquela etapa para a data fictícia
   (os serviços gravam "agora"), sempre restrito à organização e ao projeto de demonstração.

Tudo roda numa sequência de transações; se algo falhar no meio, rode de novo com --zerar.
"""
import argparse
import datetime as dt
import os
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from sqlalchemy import bindparam, text, update  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

import dados_demo as D  # noqa: E402
from nucleo.ator import Ator  # noqa: E402
from nucleo.db import endereco_seguro, engine, nova_sessao  # noqa: E402
from nucleo.migracoes import revisao_atual  # noqa: E402
from nucleo.numeracao import codigo_decisao  # noqa: E402
from cronograma_calculos import Item as ItemCronograma  # noqa: E402
from nucleo.servicos import atas as s_atas  # noqa: E402
from nucleo.servicos import cronograma as s_cronograma  # noqa: E402
from nucleo.servicos import decisoes as s_decisoes  # noqa: E402
from nucleo.servicos import documentos as s_documentos  # noqa: E402
from nucleo.servicos import ficha as s_ficha  # noqa: E402
from nucleo.servicos import organizacoes as s_organizacoes  # noqa: E402
from nucleo.servicos import pendencias as s_pendencias  # noqa: E402
from nucleo.servicos import projetos as s_projetos  # noqa: E402
from nucleo.servicos import usuarios as s_usuarios  # noqa: E402
from nucleo.tabelas import (  # noqa: E402
    AtaAdendo, Caracteristica, CaracteristicaHistorico, CronogramaVersao, Decisao, DocumentoArquivo,
    DocumentoReferencia, MembroProjeto, Organizacao, PadraoConstrutivo, Pendencia, Projeto,
    RegistroAuditoria, Reuniao, Usuario, UsoIA,
)

REVISAO_ESPERADA = "0012"   # cronograma macro (migração 0012)
FUSO = ZoneInfo("America/Sao_Paulo")
_REF = re.compile(r"\{D:(\w+)\}")


def _utc(local: dt.datetime) -> dt.datetime:
    """Horário de Brasília -> UTC com fuso (o SQLModel exige fuso, como os serviços gravam)."""
    return local.replace(tzinfo=FUSO).astimezone(dt.timezone.utc)


class Carga:
    def __init__(self, s: Session, senha: str):
        self.s = s
        self.senha = senha
        # Tudo que os serviços gravarem durante a carga fica com data >= inicio. Margem de 2 dias
        # cobre diferença de fuso da sessão do banco; as datas fictícias são todas anteriores.
        self.inicio = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=2)
        self.hoje = dt.date.today()
        self.org = None
        self.pid = None
        self.atores = {}
        self.decisoes = {}   # chave -> número

    # ------------------------------------------------------------ carimbos de data

    def carimbar(self, quando: dt.datetime) -> None:
        """Leva para 'quando' tudo o que a última etapa gravou com o horário real."""
        m = _utc(quando)
        s, pid, org_id, ini = self.s, self.pid, self.org.id, self.inicio
        s.exec(update(Organizacao).where(Organizacao.id == org_id, Organizacao.data_criacao >= ini)
               .values(data_criacao=m))
        s.exec(update(RegistroAuditoria).where(RegistroAuditoria.organizacao_id == org_id,
                                               RegistroAuditoria.momento >= ini).values(momento=m))
        if pid is not None:
            por_projeto = [
                (Projeto, Projeto.id, "data_criacao"),
                (Caracteristica, Caracteristica.projeto_id, "data_atualizacao"),
                (CaracteristicaHistorico, CaracteristicaHistorico.projeto_id, "data_registro"),
                (Reuniao, Reuniao.projeto_id, "data_fechamento"),
                (Pendencia, Pendencia.projeto_id, "data_criacao"),
                (Pendencia, Pendencia.projeto_id, "data_resolucao"),
                (DocumentoReferencia, DocumentoReferencia.projeto_id, "data_atualizacao"),
                (CronogramaVersao, CronogramaVersao.projeto_id, "criado_em"),
            ]
            for tabela, coluna_projeto, campo in por_projeto:
                coluna = getattr(tabela, campo)
                s.exec(update(tabela).where(coluna_projeto == pid, coluna >= ini).values({campo: m}))
            atas = select(Reuniao.id).where(Reuniao.projeto_id == pid)
            s.exec(update(AtaAdendo).where(AtaAdendo.reuniao_id.in_(atas), AtaAdendo.data_registro >= ini)
                   .values(data_registro=m))
            # Decisões criadas ao resolver pendência nascem com a data de hoje.
            s.exec(update(Decisao).where(Decisao.projeto_id == pid, Decisao.data_decisao == self.hoje)
                   .values(data_decisao=quando.date()))
        s.commit()
        s.expire_all()

    # ------------------------------------------------------------ apoio

    def ator(self, username: str) -> Ator:
        return self.atores[username]

    def refs(self, texto: str) -> str:
        def troca(m):
            chave = m.group(1)
            if chave not in self.decisoes:
                raise KeyError(f"Referência {{D:{chave}}} usada antes de a decisão existir.")
            return codigo_decisao(self.decisoes[chave])
        return _REF.sub(troca, texto or "")

    def decisao_id(self, chave: str) -> int:
        numero = self.decisoes[chave]
        return self.s.exec(select(Decisao.id).where(Decisao.projeto_id == self.pid,
                                                    Decisao.numero == numero)).one()

    @staticmethod
    def itens_cronograma(linhas):
        return [ItemCronograma(l["nome"], l["tipo"], l["inicio"], l["entrega"], l["depende"], l["padrao"])
                for l in linhas]

    def pendencia(self, trecho: str) -> Pendencia:
        achadas = [p for p in self.s.exec(select(Pendencia).where(Pendencia.projeto_id == self.pid)).all()
                   if trecho.lower() in p.titulo.lower()]
        if len(achadas) != 1:
            raise ValueError(f"Pendência '{trecho}': {len(achadas)} encontradas (esperado 1).")
        return achadas[0]

    # ------------------------------------------------------------ organização e usuários

    def criar_organizacao(self) -> None:
        s = self.s
        org = s_organizacoes.nova_organizacao(s, D.ORG_NOME)
        org.slug = D.ORG_SLUG
        org.plano = "interno"            # sem cobrança, sem limites, sem vencimento
        org.assinatura_status = "ativa"
        org.ativa = True
        s.add(org)
        s.commit()
        self.org = org
        for u in D.USUARIOS:
            usuario = s_usuarios.novo_usuario(
                s, u["username"], self.senha, u["nome"], org.id,
                admin=u["admin"], pode_criar_projetos=u["pode_criar_projetos"],
            )
            usuario.tema = "claro"
            s.add(usuario)
            s.commit()
            self.atores[u["username"]] = Ator.de_usuario(usuario)
        primeira = D.ETAPAS[0]["quando"] - dt.timedelta(days=3)
        self.carimbar(primeira)

    # ------------------------------------------------------------ etapas

    def etapa(self, e: dict) -> None:
        tipo, quando = e["tipo"], e["quando"]
        s = self.s
        ator = self.ator(e["autor"])
        if tipo == "projeto":
            p = s_projetos.criar(s, ator, D.PROJETO_NOME, D.PROJETO_CLIENTE, D.PROJETO_DESCRICAO)
            self.pid = p.id
        elif tipo == "projeto_arquivado":
            # projeto concluído e arquivado: aparece em "Projetos arquivados" (capturas da ajuda)
            outro = s_projetos.criar(s, ator, e["nome"], e["cliente"], e.get("descricao"))
            s_projetos.arquivar(s, ator, outro.id, True)
            s.exec(update(Projeto).where(Projeto.id == outro.id).values(data_criacao=_utc(e["criado_em"])))
            s.commit()
        elif tipo == "membros":
            for u in D.USUARIOS:
                if u["papel"] and u["username"] != D.CRIADOR:
                    s_projetos.definir_membro(s, ator, self.pid, u["username"], u["papel"])
        elif tipo == "ficha":
            s_ficha.salvar(s, ator, self.pid, e["itens"])
        elif tipo == "documento":
            doc = s.exec(select(DocumentoReferencia).where(
                DocumentoReferencia.projeto_id == self.pid, DocumentoReferencia.nome == e["nome"])).one()
            s_documentos.atualizar(s, ator, doc.id, situacao=e["situacao"],
                                   observacao=e.get("observacao"),
                                   data_recebimento=e.get("data_recebimento"))
        elif tipo == "decisao":
            dados = s_decisoes.DadosDecisao(
                titulo=self.refs(e["titulo"]), categoria=e["categoria"],
                descricao=self.refs(e["descricao"]), justificativa=self.refs(e["justificativa"]),
                impacto=e["impacto"], alternativa_descartada=e.get("alternativa"),
                data_decisao=quando.date(), checklist=e.get("checklist"),
            )
            dec = s_decisoes.criar(s, ator, self.pid, dados)
            self.decisoes[e["chave"]] = dec.numero
            ficha = e.get("ficha")  # um item (grupo, nome, unidade, valor) ou uma lista deles
            if ficha:
                s_ficha.salvar(s, ator, self.pid, ficha if isinstance(ficha, list) else [ficha],
                               decisao_id=dec.id)
        elif tipo == "ata":
            self.ata(e, ator)
            return  # a ata carimba as próprias etapas (criação e fechamento)
        elif tipo == "adendo":
            ata = s.exec(select(Reuniao).where(Reuniao.projeto_id == self.pid,
                                               Reuniao.numero == e["ata"])).one()
            s_atas.adicionar_adendo(s, ator, ata.id, self.refs(e["texto"]))
        elif tipo == "pendencia":
            s_pendencias.criar(s, ator, self.pid, e["titulo"], e.get("descricao", ""),
                               e.get("categoria", "Geral"), e.get("responsavel", ""), e.get("prazo"))
        elif tipo == "resolver":
            p = self.pendencia(e["pendencia"])
            nova = e.get("nova_decisao")
            if nova:
                dados = {k: self.refs(v) for k, v in nova.items() if k != "chave"}
                p = s_pendencias.resolver(s, ator, p.id, nova_decisao=dados,
                                          observacao=e.get("observacao", ""))
                self.decisoes[nova["chave"]] = s.get(Decisao, p.decisao_id).numero
            else:
                s_pendencias.resolver(s, ator, p.id, decisao_id=self.decisao_id(e["decisao"]),
                                      observacao=e.get("observacao", ""))
        elif tipo == "cronograma":
            s_cronograma.criar(s, ator, self.pid, self.itens_cronograma(e["itens"]))
        elif tipo == "revisao_cronograma":
            s_cronograma.revisar(s, ator, self.pid, self.itens_cronograma(e["itens"]),
                                 decisao_id=self.decisao_id(e["decisao"]))
        elif tipo == "cancelar":
            p = self.pendencia(e["pendencia"])
            s_pendencias.cancelar(s, ator, p.id, e["motivo"])
        else:
            raise ValueError(f"Etapa desconhecida: {tipo}")
        self.carimbar(quando)

    def ata(self, e: dict, ator: Ator) -> None:
        s = self.s
        ata = s_atas.criar(s, ator, self.pid, e["titulo"], e["quando"].date(),
                           e["participantes"], self.refs(e["texto"]))
        self.carimbar(e["quando"])
        if not e.get("fechamento"):
            return  # fica como rascunho (só a equipe vê)
        criadas = s_atas.fechar(s, ator, ata.id)
        chaves = e.get("chaves", [])
        if len(chaves) != len(criadas):
            raise ValueError(f"Ata '{e['titulo']}': {len(criadas)} linhas [D], {len(chaves)} chaves.")
        for chave, dec in zip(chaves, criadas):
            self.decisoes[chave] = dec.numero
        for item in e.get("pendencias", []):
            p = self.pendencia(item["pendencia"])
            s_pendencias.atualizar(s, ator, p.id, p.titulo, p.descricao, item["categoria"],
                                   item.get("responsavel", ""), item.get("prazo"))
        self.carimbar(e["fechamento"])

    def executar(self) -> None:
        self.criar_organizacao()
        for e in D.ETAPAS:
            self.etapa(e)


# ------------------------------------------------------------------ zerar

def zerar(s: Session) -> bool:
    """Apaga a organização de demonstração e tudo o que pertence a ela. Devolve se havia algo."""
    org = s.exec(select(Organizacao).where(Organizacao.slug == D.ORG_SLUG)).first()
    if org is None:
        return False
    pids = list(s.exec(select(Projeto.id).where(Projeto.organizacao_id == org.id)).all())
    uids = list(s.exec(select(Usuario.id).where(Usuario.organizacao_id == org.id)).all())
    chaves = []
    if pids:
        docs = select(DocumentoReferencia.id).where(DocumentoReferencia.projeto_id.in_(pids))
        for arq in s.exec(select(DocumentoArquivo).where(DocumentoArquivo.documento_id.in_(docs))).all():
            chaves.append(arq.chave)
            s.delete(arq)
        for d in s.exec(select(Decisao).where(Decisao.projeto_id.in_(pids))).all():
            chaves += [c for c in (d.anexos or "").split(",") if c]
        s.flush()
        for tabela in (CaracteristicaHistorico, Caracteristica, PadraoConstrutivo, Pendencia,
                       DocumentoReferencia):
            s.exec(tabela.__table__.delete().where(tabela.projeto_id.in_(pids)))
        for pid in pids:  # antes das decisões: as versões apontam para elas
            s_cronograma.excluir_do_projeto(s, pid)
        atas = select(Reuniao.id).where(Reuniao.projeto_id.in_(pids))
        s.exec(AtaAdendo.__table__.delete().where(AtaAdendo.reuniao_id.in_(atas)))
        s.exec(Decisao.__table__.delete().where(Decisao.projeto_id.in_(pids)))
        s.exec(Reuniao.__table__.delete().where(Reuniao.projeto_id.in_(pids)))
        s.exec(MembroProjeto.__table__.delete().where(MembroProjeto.projeto_id.in_(pids)))
        s.exec(Projeto.__table__.delete().where(Projeto.id.in_(pids)))
    if uids:
        s.exec(MembroProjeto.__table__.delete().where(MembroProjeto.usuario_id.in_(uids)))
        try:  # eventos de uso (logins etc.) dos usuários de demonstração; tabela sem FK
            s.execute(text("DELETE FROM eventos WHERE usuario_id IN :ids")
                      .bindparams(bindparam("ids", expanding=True)), {"ids": uids})
        except Exception:
            s.rollback()
            raise
        s.exec(Usuario.__table__.delete().where(Usuario.id.in_(uids)))
    s.exec(RegistroAuditoria.__table__.delete().where(RegistroAuditoria.organizacao_id == org.id))
    s.exec(UsoIA.__table__.delete().where(UsoIA.organizacao_id == org.id))
    s.exec(Organizacao.__table__.delete().where(Organizacao.id == org.id))
    s.commit()
    if chaves:
        try:
            from nucleo.armazenamento import armazenamento_padrao
            armazenamento_padrao().apagar(chaves)
        except Exception as erro:  # arquivos órfãos não impedem a carga
            print(f"  aviso: {len(chaves)} anexo(s) não apagado(s) do armazenamento: {erro}")
    print(f"  removidos: {len(pids)} projeto(s), {len(uids)} usuário(s), {len(chaves)} anexo(s)")
    return True


# ------------------------------------------------------------------ resumo

def resumo(s: Session, pid: int) -> None:
    contar = lambda t: len(s.exec(select(t.id).where(t.projeto_id == pid)).all())  # noqa: E731
    atas = s.exec(select(Reuniao).where(Reuniao.projeto_id == pid)).all()
    pend = s.exec(select(Pendencia).where(Pendencia.projeto_id == pid)).all()
    ligadas = len(s.exec(select(Decisao.id).where(Decisao.projeto_id == pid, Decisao.reuniao_id != None)).all())  # noqa: E711
    via_ficha = len({h.decisao_id for h in s.exec(select(CaracteristicaHistorico).where(
        CaracteristicaHistorico.projeto_id == pid, CaracteristicaHistorico.decisao_id != None)).all()})  # noqa: E711
    print(f"  decisões: {contar(Decisao)} ({ligadas} vindas de atas, {via_ficha} alteram a ficha)")
    print(f"  atas: {len(atas)} ({sum(a.status == 'Fechada' for a in atas)} fechadas, "
          f"{sum(a.status != 'Fechada' for a in atas)} em rascunho)")
    print(f"  pendências: " + ", ".join(f"{st} {sum(p.status == st for p in pend)}"
                                       for st in ("Aberta", "Resolvida", "Cancelada")))
    print(f"  ficha: {contar(Caracteristica)} campos, {contar(CaracteristicaHistorico)} registros no histórico")


def instalar_logos(org_id: int, projeto_id: int) -> None:
    """Grava os logos fictícios onde o app os procura (DATA_DIR/logos). Só faz sentido no
    servidor, onde DATA_DIR é o volume do app."""
    from logos import _gravar, caminho_logo_empresa, caminho_logo_projeto
    pasta = Path(__file__).resolve().parent / "logos_demo"
    _gravar(caminho_logo_empresa(org_id), (pasta / "logo-traco-austral.png").read_bytes())
    _gravar(caminho_logo_projeto(projeto_id), (pasta / "logo-cambara.png").read_bytes())


def _apagar_logos(s: Session) -> None:
    """Logos da demonstração anterior (os nomes dos arquivos usam os ids, que mudam)."""
    from logos import caminho_logo_empresa, caminho_logo_projeto
    org = s.exec(select(Organizacao).where(Organizacao.slug == D.ORG_SLUG)).first()
    if org is None:
        return
    caminhos = [caminho_logo_empresa(org.id)]
    caminhos += [caminho_logo_projeto(pid) for pid in
                 s.exec(select(Projeto.id).where(Projeto.organizacao_id == org.id)).all()]
    for caminho in caminhos:
        try:
            caminho.unlink(missing_ok=True)
        except OSError:
            pass


def _revisao_compativel(revisao) -> bool:
    """O seed usa os serviços do app, então migrações POSTERIORES (que só acrescentam) não o
    quebram; anterior à 0010 não serve."""
    try:
        return int(revisao) >= int(REVISAO_ESPERADA)
    except (TypeError, ValueError):
        return False


def carregar_pelo_ambiente() -> None:
    """Carga sem terminal, na partida do servidor (chamada por main.py depois de init_db).

    DECIDIU_CARREGAR_DEMO=1      carrega a demonstração se ela ainda não existir.
    DECIDIU_CARREGAR_DEMO=zerar  apaga e recria a demonstração a CADA partida (deploy ou restart).
    DECIDIU_DEMO_SENHA           senha dos usuários demo.* (mínimo 6 caracteres).

    Use só no ambiente de demonstração/testes. Qualquer erro vai para o log e o app sobe assim mesmo."""
    modo = (os.getenv("DECIDIU_CARREGAR_DEMO") or "").strip().lower()
    if modo in ("", "0", "nao", "não", "false"):
        return
    try:
        senha = os.getenv("DECIDIU_DEMO_SENHA", "")
        if len(senha) < 6:
            print("[demo] DECIDIU_DEMO_SENHA ausente ou curta (mínimo 6): demonstração não carregada.", flush=True)
            return
        revisao = revisao_atual()
        if not _revisao_compativel(revisao):
            print(f"[demo] Banco na migração {revisao!r}; a demonstração exige {REVISAO_ESPERADA} ou posterior.",
                  flush=True)
            return
        with nova_sessao() as s:
            existe = s.exec(select(Organizacao.id).where(Organizacao.slug == D.ORG_SLUG)).first()
            if existe and modo != "zerar":
                print("[demo] Demonstração já carregada (DECIDIU_CARREGAR_DEMO=zerar para recriar).", flush=True)
                return
            if existe:
                _apagar_logos(s)
                zerar(s)
            carga = Carga(s, senha)
            carga.executar()
            try:
                instalar_logos(carga.org.id, carga.pid)
            except Exception as erro:
                print(f"[demo] Logos não instalados: {erro}", flush=True)
            resumo(s, carga.pid)
        print(f"[demo] Demonstração '{D.PROJETO_NOME}' carregada. Entre como demo.helena, demo.rafael "
              "ou demo.marcos (cliente) com a senha de DECIDIU_DEMO_SENHA.", flush=True)
    except Exception as erro:  # nunca derruba o app por causa da demonstração
        print(f"[demo] ERRO ao carregar a demonstração: {type(erro).__name__}: {erro}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Carga do projeto de demonstração do Decidiu.")
    ap.add_argument("--zerar", action="store_true",
                    help="apaga a organização de demonstração existente antes de carregar")
    ap.add_argument("--so-zerar", action="store_true", help="só apaga a demonstração, sem recarregar")
    ap.add_argument("--sim", action="store_true", help="não pede confirmação")
    args = ap.parse_args()

    print(f"Banco: {endereco_seguro()}")
    revisao = revisao_atual()
    if not _revisao_compativel(revisao):
        print(f"ERRO: o banco está na migração {revisao!r}, e este seed exige {REVISAO_ESPERADA!r} "
              "ou posterior. Atualize o banco antes de continuar.")
        return 2
    senha = os.getenv("DECIDIU_DEMO_SENHA", "")
    if not args.so_zerar and len(senha) < 6:
        print("ERRO: defina DECIDIU_DEMO_SENHA (mínimo 6 caracteres) para os usuários de demonstração.")
        return 2
    if not args.sim:
        acao = "apagar e recarregar" if args.zerar else ("apagar" if args.so_zerar else "carregar")
        if input(f"Vai {acao} a organização '{D.ORG_SLUG}' neste banco. Continuar? [s/N] ").strip().lower() != "s":
            return 1

    with nova_sessao() as s:
        if args.zerar or args.so_zerar:
            print("Zerando a demonstração...")
            if not zerar(s):
                print("  nada a apagar")
            if args.so_zerar:
                return 0
        elif s.exec(select(Organizacao.id).where(Organizacao.slug == D.ORG_SLUG)).first():
            print(f"ERRO: a organização '{D.ORG_SLUG}' já existe. Use --zerar para recriá-la.")
            return 2
        print("Carregando...")
        carga = Carga(s, senha)
        carga.executar()
        resumo(s, carga.pid)
        print("Pronto. Usuários (todos com a senha de DECIDIU_DEMO_SENHA):")
        for u in D.USUARIOS:
            papel = "administrador" if u["admin"] else u["papel"]
            print(f"  {u['username']:<14} {u['nome']:<20} {papel:<12} {u['cargo']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
