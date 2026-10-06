"""Entrega de anexos e relatórios no modo site: só por link assinado e temporário.

O app gera o link (/anexo/<token>) depois de conferir que o usuário tem acesso ao projeto
da decisão. O link vale poucos minutos; passado esse tempo, é preciso abrir pelo app de novo.
Os arquivos ficam em UPLOAD_DIR, fora da pasta pública do Flet."""
from pathlib import Path

from config import DATA_DIR, RELATORIOS_DIR, UPLOAD_DIR
from seguranca import segredo_do_servidor, verificar_token


def registrar_rota_anexos(app) -> None:
    """Acrescenta GET /anexo/{token} ao app ASGI (FastAPI) do Flet, ANTES da rota que
    atende o site, para a nossa rota não ser engolida por ela."""
    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    if not hasattr(app, "add_api_route"):
        raise RuntimeError("O app exportado pelo Flet não é FastAPI: anexos indisponíveis.")

    raizes = [UPLOAD_DIR.resolve(), RELATORIOS_DIR.resolve()]  # anexos e relatórios em PDF

    async def baixar_anexo(token: str):
        dados = verificar_token(segredo_do_servidor(), token)
        if not dados or not dados.get("p"):
            raise HTTPException(status_code=403, detail="Link inválido ou expirado. Abra o anexo pelo app novamente.")
        arquivo = (DATA_DIR / dados["p"]).resolve()
        if not any(raiz in arquivo.parents for raiz in raizes) or not arquivo.is_file():
            raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
        # attachment + nosniff: o navegador baixa o arquivo em vez de executá-lo no site.
        return FileResponse(
            arquivo,
            filename=Path(arquivo).name,
            headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
        )

    app.add_api_route("/anexo/{token}", baixar_anexo, methods=["GET"], include_in_schema=False)
    app.router.routes.insert(0, app.router.routes.pop())  # nossa rota passa à frente
