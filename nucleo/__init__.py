"""Núcleo do Decidiu: modelos, regras de negócio e serviços.

Não depende de Flet nem de FastAPI. É usado pelas duas "portas de entrada":
- o app Flet atual (via database.py, que delega para cá), e
- a API REST (pasta api/), base do novo frontend.

Organização:
    tabelas.py      modelos SQLModel (tabelas do banco)
    db.py           engine e sessões (SQLite no PC, PostgreSQL via DECIDIU_DATABASE_URL)
    ator.py         quem está agindo (usuário autenticado)
    erros.py        erros de domínio (viram 404/403/422 na API)
    permissoes.py   níveis de acesso por projeto
    senhas.py       hash PBKDF2 das senhas
    marcacoes.py    leitura das linhas [D] e [P] das atas
    numeracao.py    sequenciais por projeto (D-001, P-001, Ata 01) com trava
    auditoria.py    trilha de auditoria (quem fez o quê)
    armazenamento.py  arquivos (disco local hoje; S3/R2 depois)
    servicos/       um módulo por assunto (projetos, decisões, atas...)
"""
