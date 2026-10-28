"""Logotipos que aparecem no cabeçalho dos PDFs (relatório de decisões e atas).

- Logo da empresa (do escritório): um por organização, só o administrador dela troca.
- Logo do cliente: um por projeto, trocado pelo Responsável do projeto.

As imagens ficam em DATA_DIR/logos, fora da pasta pública. Toda imagem enviada é aberta
com o Pillow, reduzida e regravada como PNG: o que chega ao PDF é sempre uma imagem limpa
(sem metadados nem conteúdo estranho), e um arquivo que não seja imagem é recusado."""
import io
from pathlib import Path
from typing import Optional

from config import DATA_DIR

LOGOS_DIR = DATA_DIR / "logos"
TAMANHO_MAXIMO = 5 * 1024 * 1024  # 5 MB por arquivo enviado
LADO_MAXIMO = 1200  # px; o cabeçalho do PDF tem ~1,5 cm de altura, isso sobra
EXTENSOES = ["png", "jpg", "jpeg", "webp", "gif", "bmp"]


LOGO_EMPRESA_LEGADO = "empresa.png"  # de antes das organizações (um só para o sistema)


def caminho_logo_empresa(organizacao_id: Optional[int]) -> Optional[Path]:
    if organizacao_id is None:
        return None
    return LOGOS_DIR / f"empresa-org{int(organizacao_id)}.png"


def migrar_logo_legado(organizacao_id: int) -> bool:
    """Passa o logo antigo (único) para a organização informada. Roda uma vez, na partida."""
    antigo, novo = LOGOS_DIR / LOGO_EMPRESA_LEGADO, caminho_logo_empresa(organizacao_id)
    if antigo.is_file() and not novo.exists():
        antigo.replace(novo)
        return True
    return False


def caminho_logo_projeto(projeto_id: int) -> Path:
    return LOGOS_DIR / f"projeto-{int(projeto_id)}.png"


def _existente(caminho: Path) -> Optional[Path]:
    return caminho if caminho.is_file() else None


def logo_empresa(organizacao_id: Optional[int] = None) -> Optional[Path]:
    """Caminho do logo da empresa (da organização), ou None se não houver."""
    caminho = caminho_logo_empresa(organizacao_id)
    return _existente(caminho) if caminho else None


def logo_projeto(projeto_id: int) -> Optional[Path]:
    """Caminho do logo do cliente do projeto, ou None se não houver."""
    return _existente(caminho_logo_projeto(projeto_id))


def normalizar_imagem(dados: bytes) -> bytes:
    """Confere que 'dados' é uma imagem e devolve um PNG reduzido. Levanta ValueError
    com mensagem clara para o usuário quando não dá."""
    if not dados:
        raise ValueError("O arquivo está vazio.")
    if len(dados) > TAMANHO_MAXIMO:
        raise ValueError("A imagem passa de 5 MB. Use um arquivo menor.")
    from PIL import Image, UnidentifiedImageError  # vem junto com o reportlab

    Image.MAX_IMAGE_PIXELS = 40_000_000  # recusa imagens gigantes ("bombas" de descompressão)
    try:
        with Image.open(io.BytesIO(dados)) as imagem:
            imagem.load()
            imagem.seek(0)  # GIF animado: só o primeiro quadro
            tem_transparencia = imagem.mode in ("RGBA", "LA", "PA") or "transparency" in imagem.info
            imagem = imagem.convert("RGBA" if tem_transparencia else "RGB")
            imagem.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
            saida = io.BytesIO()
            imagem.save(saida, format="PNG", optimize=True)
    except (UnidentifiedImageError, Image.DecompressionBombError):
        raise ValueError("O arquivo não é uma imagem válida (use PNG ou JPG).") from None
    except OSError as erro:
        raise ValueError(f"Não foi possível ler a imagem: {erro}") from None
    return saida.getvalue()


def _gravar(destino: Path, dados: bytes) -> Path:
    png = normalizar_imagem(dados)
    LOGOS_DIR.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(".tmp")
    temporario.write_bytes(png)
    temporario.replace(destino)  # troca de uma vez: o PDF nunca pega um arquivo pela metade
    return destino


def salvar_logo_empresa(dados: bytes, usuario) -> Path:
    if not getattr(usuario, "admin", False) or getattr(usuario, "organizacao_id", None) is None:
        raise PermissionError("Só administradores podem trocar o logo da empresa.")
    return _gravar(caminho_logo_empresa(usuario.organizacao_id), dados)


def salvar_logo_projeto(projeto_id: int, dados: bytes, usuario) -> Path:
    _exigir_responsavel(projeto_id, usuario)
    return _gravar(caminho_logo_projeto(projeto_id), dados)


def remover_logo_empresa(usuario) -> None:
    if not getattr(usuario, "admin", False) or getattr(usuario, "organizacao_id", None) is None:
        raise PermissionError("Só administradores podem remover o logo da empresa.")
    caminho_logo_empresa(usuario.organizacao_id).unlink(missing_ok=True)


def remover_logo_projeto(projeto_id: int, usuario=None) -> None:
    """Remove o logo do cliente. Sem 'usuario', é a limpeza feita ao excluir o projeto."""
    if usuario is not None:
        _exigir_responsavel(projeto_id, usuario)
    caminho_logo_projeto(projeto_id).unlink(missing_ok=True)


def _exigir_responsavel(projeto_id: int, usuario) -> None:
    from database import pode_no_projeto

    if not pode_no_projeto(usuario.id, projeto_id, "Responsável"):
        raise PermissionError("Só o Responsável pelo projeto pode trocar o logo do cliente.")
