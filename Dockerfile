FROM python:3.12-slim

# uv: gerenciador de pacotes/projeto do Python (instala as dependências do pyproject.toml)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    MEMORIA_MODO_WEB=1 \
    MEMORIA_DATA_DIR=/dados \
    FLET_FORCE_WEB_SERVER=true

# 1) dependências (camada em cache; usa uv.lock se existir)
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project

# 2) código do app
COPY . .

# /dados = volume persistente: banco, anexos e segredo. Sem a instrução VOLUME de propósito:
# o Railway a rejeita; no Docker/Compose o volume é declarado no docker-compose.yml.
# A porta vem da variável PORT (o Railway define; sem ela o app usa 8000).
RUN useradd --create-home app && mkdir -p /dados && chown -R app /dados /app
USER app
EXPOSE 8000

CMD ["python", "main.py"]
