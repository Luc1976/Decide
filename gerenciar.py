"""Gestão de usuários pela linha de comando (útil no servidor).

  python gerenciar.py listar
  python gerenciar.py criar-usuario <usuario> "<Nome Completo>" [--admin] [--cliente]
      --cliente = não pode criar projetos próprios (só acompanha os que receber acesso)
  python gerenciar.py trocar-senha <usuario>

A senha é pedida no terminal (não aparece na tela nem fica no histórico).
No Docker:  docker compose exec app python gerenciar.py trocar-senha lucas
"""
import getpass
import sys

from database import alterar_senha, criar_usuario, init_db, listar_usernames


def _pedir_senha() -> str:
    senha = getpass.getpass("Nova senha (mín. 6 caracteres): ")
    if senha != getpass.getpass("Repita a senha: "):
        raise ValueError("As senhas não conferem.")
    return senha


def main(argv: list) -> int:
    init_db()
    if not argv or argv[0] == "listar":
        print("\n".join(listar_usernames()) or "(nenhum usuário)")
        return 0
    try:
        if argv[0] == "criar-usuario" and len(argv) >= 3:
            criar_usuario(
                argv[1],
                _pedir_senha(),
                argv[2],
                admin="--admin" in argv[3:],
                pode_criar_projetos="--cliente" not in argv[3:],
            )
            print(f"Usuário '{argv[1]}' criado.")
            return 0
        if argv[0] == "trocar-senha" and len(argv) == 2:
            alterar_senha(argv[1], _pedir_senha())
            print(f"Senha de '{argv[1]}' alterada.")
            return 0
    except ValueError as erro:
        print(f"Erro: {erro}")
        return 1
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
