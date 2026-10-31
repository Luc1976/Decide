"""Cálculos do cronograma macro (sem Flet e sem banco: usado pela tela, serviço, PDF e API).

Regras (docs/superpowers/specs/2026-10-31-cronograma-macro-design.md, seção 3):
- Cadeia principal: o primeiro item e todos os itens com "depende da anterior". Cada
  item da cadeia depende do item da cadeia imediatamente anterior. Os demais correm em
  paralelo e só mudam quando editados.
- Recálculo: percorrendo a cadeia, carrega-se um deslocamento em dias. Item editado fica
  com as datas digitadas, e o deslocamento passa a ser a mudança da entrega dele. Item
  não editado anda o deslocamento (duração, intervalo e sobreposição preservados).
  Mudar só o início não move os seguintes. Vale para atraso e para antecipação.
"""
import datetime
import unicodedata
from dataclasses import dataclass, replace
from typing import Dict, Iterable, List, Optional, Tuple

ETAPA, MARCO = "etapa", "marco"

# (nome, tipo, marcado por padrão)
ITENS_PADRAO = (
    ("Kick-off", MARCO, True),
    ("Projeto conceitual", ETAPA, False),
    ("Estudo preliminar", ETAPA, True),
    ("Anteprojeto", ETAPA, True),
    ("Projeto básico", ETAPA, True),
    ("Projeto executivo", ETAPA, True),
    ("Liberado para obra", MARCO, True),
)


@dataclass(frozen=True)
class Item:
    nome: str
    tipo: str = ETAPA
    inicio: Optional[datetime.date] = None
    entrega: Optional[datetime.date] = None
    depende_da_anterior: bool = True
    padrao: bool = False


@dataclass(frozen=True)
class Desvio:
    inicio_dias: int = 0
    entrega_dias: int = 0
    novo: bool = False


def chave(nome: str) -> str:
    """Nome para comparar itens entre versões: sem acentos, minúsculas, espaços simples."""
    sem = unicodedata.normalize("NFKD", nome or "")
    sem = "".join(c for c in sem if not unicodedata.combining(c))
    return " ".join(sem.casefold().split())


def normalizar_item(item: Item) -> Item:
    """Marco tem uma data só (a entrega acompanha o início)."""
    if item.tipo == MARCO and item.inicio is not None:
        return replace(item, entrega=item.inicio)
    return item


def itens_padrao() -> List[Tuple[Item, bool]]:
    return [(Item(nome, tipo, depende_da_anterior=i > 0, padrao=True), marcado)
            for i, (nome, tipo, marcado) in enumerate(ITENS_PADRAO)]


# ---------------------------------------------------------------- recálculo

def recalcular(base: List[Item], editados: Dict[str, Tuple[datetime.date, datetime.date]]
               ) -> List[Tuple[Item, bool]]:
    """Itens na ordem de 'base', com as datas recalculadas.

    base: os itens como estão na tela (ordem, tipo, dependência), com as datas da versão
          de partida (os itens novos já com as datas digitadas).
    editados: {nome: (início, entrega)} que o usuário digitou nesta revisão.
    Devolve [(item, recalculado)], recalculado=True quando o item andou sem ser editado."""
    deslocamento = datetime.timedelta(0)
    saida: List[Tuple[Item, bool]] = []
    for indice, original in enumerate(base):
        original = normalizar_item(original)
        na_cadeia = indice == 0 or original.depende_da_anterior
        if original.nome in editados:
            inicio, entrega = editados[original.nome]
            item = normalizar_item(replace(original, inicio=inicio, entrega=entrega))
            if na_cadeia and original.entrega and item.entrega:
                deslocamento = item.entrega - original.entrega
            saida.append((item, False))
            continue
        if na_cadeia and deslocamento and original.inicio and original.entrega:
            item = replace(original, inicio=original.inicio + deslocamento,
                           entrega=original.entrega + deslocamento)
            saida.append((item, True))
            continue
        saida.append((original, False))
    return saida


# ---------------------------------------------------------------- comparação entre versões

def desvios(atual: Iterable[Item], referencia: Iterable[Item]) -> Tuple[Dict[str, Desvio], List[str]]:
    """({chave(nome): Desvio}, [nomes que saíram]) da versão atual em relação à referência."""
    ref = {chave(i.nome): normalizar_item(i) for i in referencia}
    resultado: Dict[str, Desvio] = {}
    vistos = set()
    for item in atual:
        item = normalizar_item(item)
        k = chave(item.nome)
        vistos.add(k)
        antes = ref.get(k)
        if antes is None:
            resultado[k] = Desvio(novo=True)
            continue
        resultado[k] = Desvio(
            inicio_dias=(item.inicio - antes.inicio).days if item.inicio and antes.inicio else 0,
            entrega_dias=(item.entrega - antes.entrega).days if item.entrega and antes.entrega else 0,
        )
    removidos = [i.nome for k, i in ref.items() if k not in vistos]
    return resultado, removidos


def texto_desvio(dias: int) -> str:
    if dias == 0:
        return "no prazo"
    sinal = "+" if dias > 0 else "−"
    n = abs(dias)
    return f"{sinal}{n} dia" + ("" if n == 1 else "s")


# ---------------------------------------------------------------- validação

def validar(itens: List[Item]) -> List[str]:
    """Mensagens para o usuário; lista vazia = pode gravar."""
    if not itens:
        return ["Inclua ao menos uma etapa ou marco."]
    erros = []
    vistos = set()
    for item in itens:
        nome = (item.nome or "").strip()
        if not nome:
            erros.append("Há um item sem nome.")
            continue
        k = chave(nome)
        if k in vistos:
            erros.append(f"'{nome}' está repetido.")
        vistos.add(k)
        item = normalizar_item(item)
        if item.inicio is None or item.entrega is None:
            erros.append(f"'{nome}': informe as datas.")
        elif item.entrega < item.inicio:
            erros.append(f"'{nome}': entrega antes do início.")
    return erros


def iguais(a: List[Item], b: List[Item]) -> bool:
    """Mesmo cronograma (para recusar uma revisão em que nada mudou)."""
    def forma(lista):
        return [(chave(i.nome), i.tipo, i.inicio, i.entrega, i.depende_da_anterior)
                for i in map(normalizar_item, lista)]
    return forma(a) == forma(b)


# ---------------------------------------------------------------- escala do Gantt

def _primeiro_do_mes(dia: datetime.date) -> datetime.date:
    return dia.replace(day=1)


def _mes_seguinte(dia: datetime.date) -> datetime.date:
    return (dia.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)


def escala(*listas: Iterable[Item]) -> Tuple[datetime.date, datetime.date, List[datetime.date]]:
    """(início, fim, primeiros dias de cada mês) cobrindo todos os itens, com meio mês de
    margem; a escala começa no dia 1 do mês. Sem datas, usa o mês atual."""
    datas = [x for lista in listas for i in lista for x in (i.inicio, i.entrega) if x]
    if not datas:
        hoje = datetime.date.today()
        datas = [hoje]
    inicio = _primeiro_do_mes(min(datas) - datetime.timedelta(days=15))
    fim = max(datas) + datetime.timedelta(days=15)
    meses = []
    mes = inicio
    while mes <= fim:
        meses.append(mes)
        mes = _mes_seguinte(mes)
    return inicio, fim, meses


def posicao(dia: datetime.date, inicio: datetime.date, fim: datetime.date) -> float:
    """Posição de 'dia' na escala, de 0 (início) a 1 (fim)."""
    total = max((fim - inicio).days, 1)
    return min(max((dia - inicio).days / total, 0.0), 1.0)
