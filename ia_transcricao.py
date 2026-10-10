"""Rascunho de ata a partir da transcrição de uma reunião (Teams, etc.) usando IA.

A IA NUNCA registra nada sozinha: ela devolve sugestões, este módulo as transforma em um
texto de ata com linhas [D] (decisão) e [F] (ficha), e uma pessoa revisa, edita e fecha a ata
no editor de sempre.

Configuração (variáveis de ambiente, só no servidor; a chave nunca vai para o navegador):
  ANTHROPIC_API_KEY        chave da API da Anthropic (ou MEMORIA_ANTHROPIC_API_KEY).
  MEMORIA_ANTHROPIC_WORKSPACE_ID  ID do workspace (wrkspc_...), se a chave não for de workspace.
  MEMORIA_IA_MODELO        modelo (padrão claude-sonnet-5-5; claude-haiku-5-5 é mais barato).
  MEMORIA_IA_LIMITE_MES    máximo de transcrições por projeto por mês (padrão 30; 0 = sem limite).

Só usa a biblioteca padrão do Python (urllib): não precisa instalar nada novo.
"""
import datetime
import json
import os
import re
import urllib.error
import urllib.request
from typing import Callable, Optional

import config
from ficha_calculos import localizar_campo

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
MODELO_PADRAO = "claude-sonnet-5-5"
LIMITE_MES_PADRAO = 30
# Reuniões longas são divididas em blocos para não estourar o limite de resposta.
TAMANHO_BLOCO = 120_000  # caracteres (~30 mil tokens)
MAX_TRANSCRICAO = 600_000  # caracteres; acima disso o usuário deve dividir a reunião
AVISO_PRIVACIDADE = (
    "O texto da transcrição será enviado a um serviço de IA (Anthropic) apenas para gerar o "
    "rascunho. Avise os participantes e evite incluir dados pessoais sensíveis."
)


class ErroIA(Exception):
    """Falha esperada (sem chave, limite, resposta ruim); a mensagem pode ir direto ao usuário."""


# ---------------------------------------------------------------- configuração

def _chave() -> str:
    return (os.getenv("MEMORIA_ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or "").strip()


def ia_configurada() -> bool:
    return bool(_chave())


def _workspace() -> str:
    """ID do workspace da Anthropic, exigido quando a chave não está ligada a um workspace."""
    return (os.getenv("MEMORIA_ANTHROPIC_WORKSPACE_ID") or "").strip()


def _modelo() -> str:
    return (os.getenv("MEMORIA_IA_MODELO") or MODELO_PADRAO).strip()


def _limite_mes() -> int:
    try:
        return int(os.getenv("MEMORIA_IA_LIMITE_MES") or LIMITE_MES_PADRAO)
    except ValueError:
        return LIMITE_MES_PADRAO


# ---------------------------------------------------------------- limite de uso

def _arquivo_uso():
    return config.DATA_DIR / "uso_ia.json"


def _mes() -> str:
    return datetime.date.today().strftime("%Y-%m")


def _ler_uso() -> dict:
    try:
        return json.loads(_arquivo_uso().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def usos_no_mes(projeto_id) -> int:
    return int(_ler_uso().get(_mes(), {}).get(str(projeto_id), 0))


def conferir_limite(projeto_id) -> None:
    limite = _limite_mes()
    if limite and usos_no_mes(projeto_id) >= limite:
        raise ErroIA(
            f"Este projeto atingiu o limite de {limite} transcrições neste mês. "
            "Escreva a ata manualmente ou peça ao administrador para aumentar o limite."
        )


def registrar_uso(projeto_id) -> None:
    uso = _ler_uso()
    mes = uso.setdefault(_mes(), {})
    mes[str(projeto_id)] = int(mes.get(str(projeto_id), 0)) + 1
    for antigo in sorted(uso)[:-3]:  # guarda só os últimos meses
        uso.pop(antigo, None)
    try:
        _arquivo_uso().write_text(json.dumps(uso), encoding="utf-8")
    except OSError:
        pass  # contagem é best-effort


# ---------------------------------------------------------------- limpeza da transcrição

_RE_TEMPO = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?[.,]\d{3}\s*-->\s*\d{1,2}:\d{2}(:\d{2})?[.,]\d{3}")
_RE_VOZ = re.compile(r"<v\s+([^>]+)>(.*?)(?:</v>|$)", re.IGNORECASE)
_RE_TAG = re.compile(r"</?[a-zA-Z][^>]*>")
_RE_ID_CUE = re.compile(r"^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}(/\d+-\d+)?$", re.IGNORECASE)


def limpar_transcricao(texto: str):
    """Aceita o texto colado do Teams (.vtt ou texto corrido). Tira cabeçalho WEBVTT,
    horários e marcações e junta falas seguidas da mesma pessoa.
    Devolve (texto_limpo, participantes) com os nomes na ordem em que falaram."""
    bruto = (texto or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not bruto:
        return "", []
    if not (bruto.upper().startswith("WEBVTT") or "-->" in bruto):
        return bruto, []  # texto corrido: não mexe

    falas, participantes = [], []
    for linha in bruto.split("\n"):
        linha = linha.strip()
        if (
            not linha
            or linha.upper().startswith(("WEBVTT", "NOTE", "STYLE", "KIND:", "LANGUAGE:"))
            or _RE_TEMPO.match(linha)
            or _RE_ID_CUE.match(linha)
            or linha.isdigit()
        ):
            continue
        achado = _RE_VOZ.search(linha)
        if achado:
            quem, fala = achado.group(1).strip(), _RE_TAG.sub("", achado.group(2)).strip()
        else:
            quem, fala = "", _RE_TAG.sub("", linha).strip()
        if not fala:
            continue
        if quem and quem not in participantes:
            participantes.append(quem)
        if falas and falas[-1][0] == quem:
            falas[-1][1] += " " + fala
        else:
            falas.append([quem, fala])
    return "\n".join(f"{q}: {f}" if q else f for q, f in falas), participantes


def dividir_em_blocos(texto: str, tamanho: int = TAMANHO_BLOCO) -> list:
    """Divide em blocos de até 'tamanho' caracteres, sempre entre linhas (nunca no meio de uma fala)."""
    blocos, atual, usado = [], [], 0
    for linha in texto.split("\n"):
        while len(linha) > tamanho:  # linha gigante: corta
            if atual:
                blocos.append("\n".join(atual))
                atual, usado = [], 0
            blocos.append(linha[:tamanho])
            linha = linha[tamanho:]
        if usado + len(linha) + 1 > tamanho and atual:
            blocos.append("\n".join(atual))
            atual, usado = [], 0
        atual.append(linha)
        usado += len(linha) + 1
    if atual:
        blocos.append("\n".join(atual))
    return blocos


# ---------------------------------------------------------------- chamada à API

SISTEMA = """Você é secretário(a) técnico(a) de uma equipe de projetos de arquitetura e engenharia no Brasil.
Recebe a transcrição de uma reunião e o contexto do projeto, e propõe o que deve entrar na ata.
Regras:
- Responda SOMENTE com um objeto JSON válido, sem texto antes ou depois e sem cercas de código.
- Só inclua DECISÕES realmente tomadas na reunião. Dúvidas, ideias em discussão e tarefas sem decisão vão em "pendencias".
- Não invente nada que não esteja na transcrição. Se não houver responsável ou prazo, use "".
- "trecho" é uma frase curta (até 200 caracteres) copiada da transcrição que sustenta o item.
- "alteracoes_ficha" só quando a reunião fixou ou mudou um dado da ficha do empreendimento; "campo" deve ser um dos nomes de campo informados no contexto.
- Escreva em português do Brasil, de forma objetiva.
Formato:
{"resumo": "2 a 4 frases sobre o que foi tratado",
 "decisoes": [{"titulo": "curto", "descricao": "o que foi decidido, em uma frase",
               "categoria": "uma das categorias informadas", "impacto": "Alto|Médio|Baixo",
               "responsavel": "", "prazo": "", "trecho": ""}],
 "alteracoes_ficha": [{"campo": "", "valor": "", "trecho": ""}],
 "pendencias": ["..."]}"""


def _motivo_erro(erro: urllib.error.HTTPError) -> str:
    """Lê a mensagem que a API devolve junto com o erro (ex.: saldo insuficiente, modelo inválido)."""
    try:
        dados = json.loads(erro.read().decode("utf-8"))
        detalhe = dados.get("error", {})
        return _uma_linha(detalhe.get("message") or detalhe.get("type") or dados)[:300]
    except Exception:
        return "sem detalhes"


def _chamar_api(sistema: str, usuario: str, max_tokens: int = 8000) -> str:
    chave = _chave()
    if not chave:
        raise ErroIA("A IA não está configurada neste servidor (falta a chave ANTHROPIC_API_KEY).")
    corpo = json.dumps(
        {
            "model": _modelo(),
            "max_tokens": max_tokens,
            "system": sistema,
            "messages": [{"role": "user", "content": usuario}],
        }
    ).encode("utf-8")
    pedido = urllib.request.Request(
        API_URL,
        data=corpo,
        method="POST",
        headers={
            "content-type": "application/json",
            "x-api-key": chave,
            "anthropic-version": API_VERSION,
            **({"anthropic-workspace-id": _workspace()} if _workspace() else {}),
        },
    )
    try:
        with urllib.request.urlopen(pedido, timeout=180) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        motivo = _motivo_erro(erro)
        print(f"[IA] erro {erro.code} da API: {motivo}", flush=True)  # aparece nos logs do Railway
        if erro.code in (401, 403):
            raise ErroIA("A chave da API foi recusada. Confira ANTHROPIC_API_KEY no servidor.")
        if erro.code == 429:
            raise ErroIA("A IA está com muitas solicitações. Tente de novo em alguns minutos.")
        if erro.code == 400:
            raise ErroIA(f"A API recusou o pedido: {motivo}")
        raise ErroIA(f"A IA respondeu com erro {erro.code}: {motivo}")
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ErroIA("Não foi possível falar com a IA (rede ou tempo esgotado). Tente novamente.")
    partes = [b.get("text", "") for b in dados.get("content", []) if b.get("type") == "text"]
    texto = "".join(partes).strip()
    if not texto:
        raise ErroIA("A IA devolveu uma resposta vazia. Tente novamente.")
    return texto


def _extrair_json(texto: str) -> dict:
    texto = texto.strip()
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto)
    try:
        return json.loads(texto)
    except ValueError:
        pass
    inicio, fim = texto.find("{"), texto.rfind("}")
    if inicio >= 0 and fim > inicio:
        try:
            return json.loads(texto[inicio : fim + 1])
        except ValueError:
            pass
    raise ErroIA("Não consegui interpretar a resposta da IA. Tente novamente.")


def _contexto(projeto_nome, categorias, impactos, campos_ficha, decisoes_recentes) -> str:
    linhas = [f"Projeto: {projeto_nome}", f"Categorias: {', '.join(categorias)}"]
    linhas.append(f"Impactos: {', '.join(impactos)}")
    nomes = [c[1] for c in campos_ficha]
    if nomes:
        linhas.append("Campos da ficha do empreendimento: " + "; ".join(nomes))
    if decisoes_recentes:
        linhas.append("Decisões já registradas (não repita as que forem iguais):")
        linhas += [f"- {d}" for d in decisoes_recentes[-30:]]
    return "\n".join(linhas)


# ---------------------------------------------------------------- montagem do rascunho

def _uma_linha(texto) -> str:
    return " ".join(str(texto or "").split())


def _juntar(resultados: list) -> dict:
    """Une as respostas de vários blocos, sem repetir decisões iguais."""
    junto = {"resumo": [], "decisoes": [], "alteracoes_ficha": [], "pendencias": []}
    vistos = set()
    for r in resultados:
        if r.get("resumo"):
            junto["resumo"].append(_uma_linha(r["resumo"]))
        for d in r.get("decisoes") or []:
            chave = _uma_linha(d.get("titulo")).casefold()
            if chave and chave not in vistos:
                vistos.add(chave)
                junto["decisoes"].append(d)
        junto["alteracoes_ficha"] += r.get("alteracoes_ficha") or []
        junto["pendencias"] += r.get("pendencias") or []
    junto["resumo"] = " ".join(junto["resumo"])
    return junto


def montar_texto_ata(dados: dict, campos_ficha: list, categorias, impactos):
    """Transforma a resposta da IA no texto da ata. Devolve (texto, avisos)."""
    avisos, linhas = [], []
    linhas.append("RASCUNHO GERADO POR IA A PARTIR DA TRANSCRIÇÃO - revise tudo antes de fechar a ata.")
    resumo = _uma_linha(dados.get("resumo"))
    if resumo:
        linhas += ["", "Resumo", resumo]

    decisoes = dados.get("decisoes") or []
    alteracoes = list(dados.get("alteracoes_ficha") or [])

    # As linhas [F] vêm ANTES das [D]: assim não ficam ligadas a uma decisão por engano.
    # Para ligar uma alteração a uma decisão, mova a linha [F] para logo abaixo da [D].
    cabecalho_f = False
    for a in alteracoes:
        campo, valor = _uma_linha(a.get("campo")), _uma_linha(a.get("valor"))
        if not campo or not valor:
            continue
        achado, erro = localizar_campo(campo, campos_ficha)
        if erro:
            avisos.append(f"Alteração da ficha ignorada ({erro}); valor sugerido: {valor}.")
            continue
        if not cabecalho_f:
            linhas += ["", "Alterações da ficha"]
            cabecalho_f = True
        linhas.append(f"[F] {achado[1]} = {valor}")
        if _uma_linha(a.get("trecho")):
            linhas.append(f"   Trecho: \"{_uma_linha(a['trecho'])}\"")

    if decisoes:
        linhas += ["", "Decisões"]
    for d in decisoes:
        titulo, descricao = _uma_linha(d.get("titulo")), _uma_linha(d.get("descricao"))
        if not (titulo or descricao):
            continue
        linha = f"[D] {titulo}: {descricao}" if titulo and descricao else f"[D] {titulo or descricao}"
        extras = []
        if _uma_linha(d.get("responsavel")):
            extras.append(f"responsável: {_uma_linha(d['responsavel'])}")
        if _uma_linha(d.get("prazo")):
            extras.append(f"prazo: {_uma_linha(d['prazo'])}")
        if extras:
            linha += " (" + "; ".join(extras) + ")"
        linhas.append(linha)
        categoria, impacto = _uma_linha(d.get("categoria")), _uma_linha(d.get("impacto"))
        detalhes = []
        if categoria in categorias:
            detalhes.append(f"sugestão de categoria: {categoria}")
        if impacto in impactos:
            detalhes.append(f"impacto sugerido: {impacto}")
        if detalhes:
            linhas.append("   " + "; ".join(detalhes))
        if _uma_linha(d.get("trecho")):
            linhas.append(f"   Trecho: \"{_uma_linha(d['trecho'])}\"")

    pendencias = [_uma_linha(p) for p in dados.get("pendencias") or [] if _uma_linha(p)]
    if pendencias:
        linhas += ["", "Pendências (sem decisão)"] + [f"- {p}" for p in pendencias]
    if not decisoes and not cabecalho_f:
        avisos.append("A IA não encontrou decisões nesta transcrição.")
    return "\n".join(linhas), avisos


def gerar_rascunho(
    transcricao: str,
    projeto_id,
    projeto_nome: str,
    categorias,
    impactos,
    campos_ficha: list,
    decisoes_recentes: Optional[list] = None,
    chamar: Optional[Callable[[str, str], str]] = None,
) -> dict:
    """Gera o rascunho da ata. Devolve {"texto", "participantes", "avisos"}.
    'chamar' (sistema, usuario) -> texto existe para testes; em produção usa a API."""
    limpo, participantes = limpar_transcricao(transcricao)
    if len(limpo) < 200:
        raise ErroIA("A transcrição está muito curta. Cole o texto completo da reunião.")
    if len(limpo) > MAX_TRANSCRICAO:
        raise ErroIA("A transcrição é muito longa. Divida a reunião em partes e gere um rascunho de cada.")
    if chamar is None:
        if not ia_configurada():
            raise ErroIA("A IA não está configurada neste servidor (falta a chave ANTHROPIC_API_KEY).")
        conferir_limite(projeto_id)
        chamar = _chamar_api

    contexto = _contexto(projeto_nome, categorias, impactos, campos_ficha, decisoes_recentes or [])
    blocos = dividir_em_blocos(limpo)
    resultados = []
    for i, bloco in enumerate(blocos, 1):
        parte = f" (parte {i} de {len(blocos)})" if len(blocos) > 1 else ""
        pedido = f"{contexto}\n\nTranscrição{parte}:\n<transcricao>\n{bloco}\n</transcricao>"
        resultados.append(_extrair_json(chamar(SISTEMA, pedido)))
    if chamar is _chamar_api:
        registrar_uso(projeto_id)

    texto, avisos = montar_texto_ata(_juntar(resultados), campos_ficha, categorias, impactos)
    return {"texto": texto, "participantes": participantes, "avisos": avisos}
