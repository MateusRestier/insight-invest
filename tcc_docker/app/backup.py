import subprocess
import datetime
from pathlib import Path
import os

# Info do container e banco
CONTAINER_NAME = "tcc_docker-db-1"
DB_NAME = "stocks"
DB_USER = "user"

# Caminho da pasta atual
BASE_DIR = Path(__file__).parent
BACKUP_DIR = BASE_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

def criar_backup():
    data = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dump_name = f"backup_{data}.dump"
    dump_in_container = f"/var/lib/postgresql/data/{dump_name}"
    dump_local = BACKUP_DIR / dump_name

    print("🟡 Criando backup dentro do container...")
    subprocess.run([
        "docker", "exec", "-t", CONTAINER_NAME,
        "pg_dump", "-U", DB_USER, "-d", DB_NAME,
        "-F", "c", "-f", dump_in_container
    ], check=True)

    print("🟢 Copiando backup para o diretório local...")
    subprocess.run([
        "docker", "cp",
        f"{CONTAINER_NAME}:{dump_in_container}",
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

    print("⬆️ Enviando arquivo para o container...")
    subprocess.run([
        "docker", "cp",
        str(arquivo),
        f"{CONTAINER_NAME}:/var/lib/postgresql/data/{arquivo.name}"
    ], check=True)

    print("♻️ Restaurando o banco de dados...")
    subprocess.run([
        "docker", "exec", "-t", CONTAINER_NAME,
        "pg_restore", "-U", DB_USER, "-d", DB_NAME,
        f"/var/lib/postgresql/data/{arquivo.name}"
    ], check=True)

    print("✅ Banco restaurado com sucesso!")

def main():
    print("\n📌 Escolha uma opção:")
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
