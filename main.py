import flet as ft

from app import main
from config import ASSETS_DIR, DATA_DIR, MODO_WEB, PORTA, UPLOAD_DIR, verificar_gravacao

_erro_pasta = verificar_gravacao()
if _erro_pasta:
    print(f"[memoria] ERRO: {_erro_pasta}", flush=True)
    raise SystemExit(1)

from database import (  # noqa: E402  (depois de checar a pasta)
    aplicar_reset_de_senha_do_ambiente,
    init_db,
    usuarios_com_senha_padrao,
)

init_db()  # cria o banco e o administrador inicial uma única vez, na partida do servidor
aplicar_reset_de_senha_do_ambiente()  # só age se MEMORIA_RESETAR_SENHA estiver definida

_inseguros = usuarios_com_senha_padrao()
if _inseguros:
    print(
        "[memoria] ATENÇÃO: estes usuários ainda usam a senha '123': "
        + ", ".join(_inseguros)
        + ". Troque antes de publicar: python gerenciar.py trocar-senha <usuario>",
        flush=True,
    )

if MODO_WEB:
    print(f"[memoria] Modo site: porta {PORTA}, dados em {DATA_DIR}", flush=True)
    # Site: o Python roda no servidor e o navegador é só a tela. Exportamos o app ASGI
    # (FastAPI) para acrescentar a rota protegida dos anexos e servir com o uvicorn.
    try:
        from anexos_web import registrar_rota_anexos

        asgi = ft.run(
            main,
            export_asgi_app=True,
            assets_dir=str(ASSETS_DIR),
            upload_dir=str(UPLOAD_DIR),
        )
        registrar_rota_anexos(asgi)
    except Exception as erro:  # versão do Flet sem export_asgi_app, FastAPI ausente etc.
        print(
            f"[memoria] ERRO ao montar o servidor web: {type(erro).__name__}: {erro}\n"
            "          Confira as versões no uv.lock (flet, flet-web, fastapi, uvicorn).",
            flush=True,
        )
        raise

    if __name__ == "__main__":
        import uvicorn

        uvicorn.run(asgi, host="0.0.0.0", port=PORTA, proxy_headers=True, forwarded_allow_ips="*")
else:
    ft.run(main)  # desktop, como antes
