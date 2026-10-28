"""API REST do Decidiu (FastAPI). Base para o novo frontend web/PWA e apps futuros.

Roda separada do app Flet:   uvicorn api.main:app --host 0.0.0.0 --port 8000
Documentação interativa:     /api/docs   (OpenAPI em /api/openapi.json)

Camadas:
    rotas/      HTTP: lê a requisição, chama UM serviço, devolve o esquema de saída
    esquemas/   formatos de entrada e saída (validação automática pelo Pydantic)
    deps.py     sessão do banco e usuário autenticado (injeção de dependências)
    erros.py    erros de domínio -> códigos HTTP
Regras de negócio NÃO ficam aqui: ficam em nucleo/servicos/.
"""
