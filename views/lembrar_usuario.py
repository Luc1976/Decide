"""Guarda só o nome de usuário neste aparelho, para a próxima entrada. A senha nunca é guardada.

No Flet 1.0 o armazenamento do navegador é o serviço ft.SharedPreferences (a antiga
page.shared_preferences/client_storage não existe mais). Criado dentro da sessão, ele se
registra na própria página, e não na View do login: continua ativo depois que a tela de
login é trocada pela de projetos, que é justamente quando o nome é gravado. Guardamos uma
referência na página para o Flet não descartá-lo. Se algo falhar, o login segue normal."""
import flet as ft

CHAVE = "decidiu.usuario_lembrado"
_ATRIBUTO = "_decidiu_preferencias"


def _armazenamento(page):
    preferencias = getattr(page, _ATRIBUTO, None)
    if preferencias is None:
        preferencias = ft.SharedPreferences()
        setattr(page, _ATRIBUTO, preferencias)  # referência forte: o serviço vive com a sessão
    return preferencias


async def ler(page) -> str:
    try:
        valor = await _armazenamento(page).get(CHAVE)
        return valor if isinstance(valor, str) else ""
    except Exception:  # armazenamento indisponível: entrada normal, sem preencher
        return ""


async def gravar(page, usuario: str) -> None:
    """usuario vazio apaga o nome guardado."""
    try:
        await _armazenamento(page).set(CHAVE, usuario or "")
    except Exception:
        pass
