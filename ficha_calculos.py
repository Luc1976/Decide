"""Funções puras da ficha de características (sem Flet nem banco, fáceis de testar)."""
import re
import unicodedata
from typing import Optional

from models import (
    CAMPO_AREA_CONSTRUIDA,
    CAMPO_AREA_TERRENO,
    CAMPO_CA,
    CAMPO_TO,
    CAMPO_TP,
)

_MILHAR = re.compile(r"^\d{1,3}(\.\d{3})+$")


def numero_br(texto) -> Optional[float]:
    """Lê números como o brasileiro escreve: '1.250,50', '1250,5', '60%', 'R$ 1.000'.
    Devolve None se não houver número."""
    t = re.sub(r"[^\d,.\-]", "", str(texto or ""))
    if not re.search(r"\d", t):
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif _MILHAR.match(t.lstrip("-")):
        t = t.replace(".", "")
    try:
        return float(t)
    except ValueError:
        return None


def fmt_br(valor: float, casas: int = 2) -> str:
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def calcular_indicadores(valores: dict) -> list:
    """Devolve [(rótulo, texto, alerta)] a partir dos campos digitados."""
    area = numero_br(valores.get(CAMPO_AREA_TERRENO))
    if not area or area <= 0:
        return []
    ocupacao = numero_br(valores.get(CAMPO_TO))
    aproveitamento = numero_br(valores.get(CAMPO_CA))
    permeabilidade = numero_br(valores.get(CAMPO_TP))
    prevista = numero_br(valores.get(CAMPO_AREA_CONSTRUIDA))

    linhas = []
    if ocupacao is not None:
        linhas.append(
            ("Projeção máxima no terreno", f"{fmt_br(area * ocupacao / 100)} m²", False)
        )
    potencial = None
    if aproveitamento is not None:
        potencial = area * aproveitamento
        linhas.append(("Potencial construtivo", f"{fmt_br(potencial)} m²", False))
    if permeabilidade is not None:
        linhas.append(
            ("Área permeável mínima", f"{fmt_br(area * permeabilidade / 100)} m²", False)
        )
    if potencial is not None and prevista is not None and prevista > potencial:
        linhas.append(
            (
                "Atenção: área prevista acima do potencial",
                f"{fmt_br(prevista - potencial)} m² a mais (confira as áreas não computáveis)",
                True,
            )
        )
    return linhas


def calcular_alteracoes(existentes: dict, itens: list) -> list:
    """Compara o que está salvo com o que foi digitado.

    existentes: {(grupo, nome): valor}
    itens: [(grupo, nome, unidade, valor)]
    Devolve só o que mudou: [(grupo, nome, unidade, anterior, novo)], com None
    para 'vazio / não existia'."""
    mudancas = []
    for grupo, nome, unidade, valor in itens:
        novo = (valor or "").strip()
        existe = (grupo, nome) in existentes
        anterior = (existentes.get((grupo, nome)) or "").strip()
        if novo == anterior:
            continue  # inclui o caso "não existia e continua vazio"
        mudancas.append((grupo, nome, unidade, anterior or None, novo or None))
    return mudancas


# --- Ligação ata -> ficha: linhas "[F] campo = valor" ---

_RE_DECISAO = re.compile(r"^\s*\[D\]\s*(.+?)\s*$", re.IGNORECASE)
_RE_FICHA = re.compile(r"^\s*\[F\]\s*(.*?)\s*$", re.IGNORECASE)


def normalizar_texto(texto: str) -> str:
    """Minúsculas, sem acentos e com espaços simples ('Orçamento' casa com 'orcamento')."""
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return " ".join(sem_acento.casefold().split())


def _sigla(nome: str) -> str:
    achado = re.search(r"\(([^)]+)\)", nome)
    return normalizar_texto(achado.group(1)) if achado else ""


def localizar_campo(rotulo: str, campos: list):
    """Acha o campo da ficha pelo que foi escrito na ata.

    campos: [(grupo, nome, unidade)]. Aceita o nome completo, a sigla entre
    parênteses ('CA', 'TO') ou o começo / um trecho do nome (mín. 3 letras).
    Devolve (campo, None) ou (None, mensagem de erro)."""
    alvo = normalizar_texto(rotulo)
    if not alvo:
        return None, "campo vazio"
    etapas = [
        lambda c: normalizar_texto(c[1]) == alvo,
        lambda c: _sigla(c[1]) == alvo,
    ]
    if len(alvo) >= 3:
        etapas.append(lambda c: normalizar_texto(c[1]).startswith(alvo))
        etapas.append(lambda c: alvo in normalizar_texto(c[1]))
    for teste in etapas:
        candidatos = [c for c in campos if teste(c)]
        if len(candidatos) == 1:
            return candidatos[0], None
        if len(candidatos) > 1:
            nomes = ", ".join(c[1] for c in candidatos)
            return None, f"'{rotulo}' é ambíguo ({nomes})"
    return None, f"campo '{rotulo}' não existe na ficha"


def analisar_alteracoes_ata(texto: str, campos: list):
    """Lê as linhas [F] da ata.

    Devolve (alteracoes, erros):
    - alteracoes: [(indice_da_decisao | None, grupo, nome, unidade, valor)]
      O índice é o da última linha [D] acima da [F]; None se não houver nenhuma.
    - erros: mensagens para o usuário corrigir antes de fechar a ata."""
    alteracoes, erros = [], []
    decisoes_vistas = 0
    for linha in (texto or "").splitlines():
        if _RE_DECISAO.match(linha):
            decisoes_vistas += 1
            continue
        achado = _RE_FICHA.match(linha)
        if not achado:
            continue
        conteudo = achado.group(1)
        if "=" not in conteudo:
            erros.append(f"linha [F] sem '=': {conteudo or '(vazia)'}")
            continue
        rotulo, valor = (parte.strip() for parte in conteudo.split("=", 1))
        if not valor:
            erros.append(f"linha [F] sem valor: {rotulo or '(vazia)'}")
            continue
        campo, erro = localizar_campo(rotulo, campos)
        if erro:
            erros.append(erro)
            continue
        grupo, nome, unidade = campo
        indice = decisoes_vistas - 1 if decisoes_vistas else None
        alteracoes.append((indice, grupo, nome, unidade, valor))
    return alteracoes, erros
