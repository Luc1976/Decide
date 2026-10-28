from urllib.parse import quote

from fastapi.responses import Response


def resposta_pdf(nome: str, conteudo: bytes) -> Response:
    return Response(
        content=conteudo,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(nome)}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
