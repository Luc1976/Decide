from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from nucleo.armazenamento import armazenamento_padrao
from nucleo.servicos import anexos

rotas = APIRouter(tags=["Anexos"])


@rotas.get("/arquivos/{token}", summary="Baixar arquivo por link assinado (sem login)")
def baixar(token: str):
    """O link é gerado por .../anexos/{indice}/link depois de checar o acesso, e expira em
    poucos minutos. Por isso esta rota não pede o token de login."""
    chave = anexos.chave_do_link(token)
    caminho = armazenamento_padrao().caminho_local(chave) if chave else None
    if chave is None:
        raise HTTPException(403, "Link inválido ou expirado. Abra o anexo pelo app novamente.")
    if caminho is None:
        raise HTTPException(404, "Arquivo não encontrado.")
    # attachment + nosniff: o navegador baixa o arquivo em vez de executá-lo no site.
    return FileResponse(caminho, filename=Path(caminho).name,
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})
