import os

import flet as ft

import flet_ajustes
from app import main
from config import ASSETS_DIR, DATA_DIR, MODO_WEB, PORTA, UPLOAD_DIR, verificar_gravacao

flet_ajustes.aplicar()  # resposta atrasada do navegador (iPhone) não derruba mais a conexão

_erro_pasta = verificar_gravacao()
if _erro_pasta:
    print(f"[memoria] ERRO: {_erro_pasta}", flush=True)
    raise SystemExit(1)

from database import (  # noqa: E402  (depois de checar a pasta)
    aplicar_reset_de_senha_do_ambiente,
    init_db,
    usuarios_com_senha_padrao,
)

from nucleo.db import ErroConexaoBanco, endereco_seguro  # noqa: E402

print(f"[memoria] Banco: {endereco_seguro()}", flush=True)
try:
    init_db()  # migrações + administrador inicial (só num banco novo), na partida do servidor
except ErroConexaoBanco as erro:
    print(f"[memoria] ERRO: {erro}", flush=True)
    raise SystemExit(1)
aplicar_reset_de_senha_do_ambiente()  # só age se MEMORIA_RESETAR_SENHA estiver definida

if os.getenv("DECIDIU_CARREGAR_DEMO"):  # só no ambiente de demonstração/testes
    from scripts.seed_demo import carregar_pelo_ambiente

    carregar_pelo_ambiente()

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
    # O Flet só aceita uploads (anexos e logos) com FLET_SECRET_KEY definida, e a lê ao
    # montar o servidor. Sem ela no ambiente, usamos uma chave derivada do segredo do app.
    if not os.getenv("FLET_SECRET_KEY"):
        from seguranca import segredo_uploads_flet

        os.environ["FLET_SECRET_KEY"] = segredo_uploads_flet()
    try:
        from anexos_web import registrar_rota_anexos

        asgi = ft.run(
            main,
            export_asgi_app=True,
            assets_dir=str(ASSETS_DIR),
            upload_dir=str(UPLOAD_DIR),
        )
        registrar_rota_anexos(asgi)
        from webhook_asaas import registrar_rota_webhook

        registrar_rota_webhook(asgi)
        from ajuda_web import registrar_rota_ajuda

        registrar_rota_ajuda(asgi)
        from icones_web import registrar_rota_icones

        registrar_rota_icones(asgi)
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
