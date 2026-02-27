import subprocess
import datetime
import os
import shutil
from pathlib import Path

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "stocks")
DB_USER = os.getenv("DB_USER", "user")
DB_PASS = os.getenv("DB_PASS", "password")
DB_PORT = os.getenv("DB_PORT", "5432")
POSTGRES_CONTAINER = os.getenv("POSTGRES_CONTAINER", "insight-db-1")

BASE_DIR = Path(__file__).parent
BACKUP_DIR = BASE_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

def _pg_env():
    env = os.environ.copy()
    env["PGPASSWORD"] = DB_PASS
    return env

def criar_backup():
    data = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dump_name = f"backup_{data}.dump"
    dump_local = BACKUP_DIR / dump_name

    print("🟡 Criando backup do banco de dados...")

    if shutil.which("pg_dump"):
        # Dentro do container: pg_dump disponível via postgresql-client
        subprocess.run([
            "pg_dump",
            "-h", DB_HOST, "-p", DB_PORT, "-U", DB_USER, "-d", DB_NAME,
            "-F", "c", "-f", str(dump_local)
        ], check=True, env=_pg_env())
    else:
        # No host sem postgres instalado: delega para o container do banco via docker exec
        dump_in_container = f"/tmp/{dump_name}"
        subprocess.run([
            "docker", "exec", "-t", POSTGRES_CONTAINER,
            "pg_dump", "-U", DB_USER, "-d", DB_NAME,
            "-F", "c", "-f", dump_in_container
        ], check=True)
        subprocess.run([
            "docker", "cp",
            f"{POSTGRES_CONTAINER}:{dump_in_container}",
            str(dump_local)
        ], check=True)

    print(f"✅ Backup salvo com sucesso em: {dump_local}")

def restaurar_backup():
    print("\n📁 Arquivos disponíveis na pasta de backup:")
    backups = list(BACKUP_DIR.glob("*.dump"))
    if not backups:
        print("❌ Nenhum arquivo de backup encontrado.")
        return

    for i, file in enumerate(backups):
        print(f"[{i}] {file.name}")

    escolha = input("Digite o número do arquivo que deseja restaurar: ")
    try:
        escolha = int(escolha)
        arquivo = backups[escolha]
    except (ValueError, IndexError):
        print("❌ Escolha inválida.")
        return

    print("♻️ Restaurando o banco de dados...")

    if shutil.which("pg_restore"):
        # Dentro do container: pg_restore disponível via postgresql-client
        with open(arquivo, "rb") as f:
            subprocess.run([
                "pg_restore",
                "-h", DB_HOST, "-p", DB_PORT, "-U", DB_USER, "-d", DB_NAME,
                "--clean", "--if-exists", "--verbose"
            ], stdin=f, check=True, env=_pg_env())
    else:
        # No host sem postgres instalado: delega para o container do banco via docker exec
        with open(arquivo, "rb") as f:
            subprocess.run([
                "docker", "exec", "-i", POSTGRES_CONTAINER,
                "pg_restore", "-U", DB_USER, "-d", DB_NAME,
                "--clean", "--if-exists", "--verbose"
            ], stdin=f, check=True)

    print("✅ Banco restaurado com sucesso!")

def main():
    print("\n Escolha uma opção:")
    print("1. Fazer backup do banco")
    print("2. Restaurar um backup")

    opcao = input("Digite 1 ou 2: ")

    if opcao == "1":
        criar_backup()
    elif opcao == "2":
        restaurar_backup()
    else:
        print("❌ Opção inválida.")

if __name__ == "__main__":
    main()
