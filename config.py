"""Configuração por variáveis de ambiente (mesmo código no PC e no servidor).

MEMORIA_DATA_DIR  Pasta onde ficam o banco e os anexos. No servidor, aponte para o
                  volume/disco persistente (ex.: /dados). Sem ela, usa a pasta atual
                  (comportamento de desenvolvimento no PC).
MEMORIA_MODO_WEB  "1" para servir o app como site (a imagem Docker já define).
MEMORIA_SEGREDO   (opcional) segredo para assinar os links de anexos; se faltar, é gerado
                  e guardado em DATA_DIR/segredo.key.
PORT              Porta do site (padrão 8000).
"""
import os
import shutil
import time
from pathlib import Path
from typing import Optional

DATA_DIR = Path(os.getenv("MEMORIA_DATA_DIR") or ".")
DB_PATH = DATA_DIR / "memoria_projetos.db"

# Anexos enviados pelo navegador ficam em UPLOAD_DIR, FORA da pasta pública (ASSETS_DIR).
# Só são entregues por /anexo/<link assinado e temporário>, depois de checar o acesso.
ASSETS_DIR = DATA_DIR / "assets"   # pasta pública do Flet (fica vazia)
UPLOAD_DIR = DATA_DIR / "uploads"

NOME_APP = "Memória de Projetos"  # aparece no rodapé dos relatórios em PDF

# Relatórios em PDF gerados sob demanda; ficam fora da pasta pública e são apagados depois de 24 h.
RELATORIOS_DIR = DATA_DIR / "relatorios"

MODO_WEB = os.getenv("MEMORIA_MODO_WEB") == "1"
PORTA = int(os.getenv("PORT") or "8000")


def garantir_pastas() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    RELATORIOS_DIR.mkdir(parents=True, exist_ok=True)


def verificar_gravacao() -> Optional[str]:
    """Confere se dá para gravar em DATA_DIR. Devolve uma mensagem de erro clara, ou None."""
    try:
        garantir_pastas()
        teste = DATA_DIR / ".teste-gravacao"
        teste.write_text("ok")
        teste.unlink()
        return None
    except OSError as erro:
        return (
            f"Não foi possível gravar em '{DATA_DIR}' ({erro}). "
            "No Railway: crie o Volume com Mount Path /dados e defina RAILWAY_RUN_UID=0."
        )


def apagar_anexos(caminhos) -> int:
    """Apaga do disco os arquivos de anexos informados. Só mexe dentro das pastas de anexos
    (uploads do site e anexos_projetos do desktop). Devolve quantos arquivos foram apagados."""
    raizes = [UPLOAD_DIR.resolve(), (Path.cwd() / "anexos_projetos").resolve()]
    apagados = 0
    for caminho in caminhos or []:
        relativo = Path(caminho)
        for base in (DATA_DIR, Path.cwd()):
            alvo = (relativo if relativo.is_absolute() else base / relativo).resolve()
            raiz = next((r for r in raizes if r in alvo.parents), None)
            if raiz is None or not alvo.is_file():
                continue
            try:
                alvo.unlink()
                apagados += 1
                if alvo.parent != raiz and not any(alvo.parent.iterdir()):
                    alvo.parent.rmdir()  # pasta do envio, já vazia
            except OSError:
                pass
            break
    return apagados


def limpar_relatorios_antigos(horas: int = 24) -> int:
    """Apaga relatórios PDF com mais de 'horas' horas. Devolve quantas pastas foram removidas."""
    limite = time.time() - horas * 3600
    removidas = 0
    if not RELATORIOS_DIR.is_dir():
        return 0
    for pasta in RELATORIOS_DIR.iterdir():
        try:
            if pasta.stat().st_mtime < limite:
                shutil.rmtree(pasta) if pasta.is_dir() else pasta.unlink()
                removidas += 1
        except OSError:
            pass
    return removidas
