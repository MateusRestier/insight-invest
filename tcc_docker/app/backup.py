import subprocess
import datetime
from pathlib import Path
import win32com.client as win32

# Info do container e banco
CONTAINER_NAME = "tcc_docker-db-1"
DB_NAME = "stocks"
DB_USER = "user"

# Caminho da pasta atual
BASE_DIR = Path(__file__).parent
BACKUP_DIR = BASE_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

def enviar_email_com_anexo(caminho_anexo):
    try:
        outlook = win32.Dispatch('outlook.application')
        mail = outlook.CreateItem(0)
        mail.To = "mateusrestier1@gmail.com; groundfordtv@gmail.com"
        mail.Subject = f"Backup do banco - {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}"
        mail.Body = "Segue em anexo o arquivo de backup gerado automaticamente."
        mail.Attachments.Add(str(caminho_anexo))
        mail.Send()
        print("📧 Email enviado com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao enviar email: {e}")

def criar_backup():
    data = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dump_name = f"backup_{data}.dump"
    dump_in_container = f"/tmp/{dump_name}"  # Mudado para /tmp/
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

    # Envia o backup por email
    enviar_email_com_anexo(dump_local)

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

    print("♻️ Restaurando o banco de dados via stdin...")
    # Abordagem via stdin para evitar problemas com caminhos com espaços
    with open(arquivo, 'rb') as f:
        subprocess.run([
            "docker", "exec", "-i", CONTAINER_NAME,
            "pg_restore",
            "-U", DB_USER,
            "-d", DB_NAME,
            "--clean",        # remove objetos existentes antes de restaurar
            "--if-exists",    # só tenta dropar se o objeto já existir
            "--verbose"       # mostra progresso
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
