"""Serviços: as regras de negócio do Decidiu, um módulo por assunto.

Convenções (valem para todos):
- Recebem a sessão do banco ('s') e o Ator; nunca abrem sessão própria.
- Checam a permissão no começo (inclusive em leituras).
- Cada função pública de gravação é UMA transação: valida, grava, registra auditoria e
  faz commit. Se algo falha no meio, nada é gravado.
- Funções 'consultar_*' / 'consultar' não checam permissão: são para uso interno (por
  outro serviço que já checou) e para o database.py legado do app Flet.
- Erros: ValueError/ErroDominio (regra), NaoEncontrado, Conflito, SemPermissao.
"""
