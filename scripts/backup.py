import subprocess
import datetime
import os
import shutil
import gzip
import io
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "user")
DB_PASS = os.getenv("DB_PASS", "password")
DB_PORT = os.getenv("DB_PORT", "5432")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM = os.getenv("RESEND_FROM", "onboarding@resend.dev")
BACKUP_EMAIL_TO = os.getenv("BACKUP_EMAIL_TO", "")

BASE_DIR = Path(__file__).resolve().parent.parent
BACKUP_DIR = BASE_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)


def _pg_env():
    env = os.environ.copy()
    env["PGPASSWORD"] = DB_PASS
    return env


def _get_server_major_version() -> int:
    """Consulta a versão major do PostgreSQL no servidor via psycopg2."""
    import psycopg2
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=int(DB_PORT), dbname=DB_NAME,
            user=DB_USER, password=DB_PASS, connect_timeout=10,
        )
        cur = conn.cursor()
        cur.execute("SHOW server_version;")
        version_str = cur.fetchone()[0]  # ex: "18.3"
        conn.close()
        major = int(version_str.split(".")[0])
        print(f"Versão do servidor PostgreSQL detectada: {major}")
        return major
    except Exception as exc:
        print(f"Aviso: não foi possível detectar versão do servidor ({exc}). Assumindo v17.")
        return 17


def _find_pg_tool(tool: str, preferred_major: int | None = None) -> str | None:
    """
    Retorna o caminho do binário pg_dump / pg_restore.
    Tenta encontrar a versão que corresponde ao servidor primeiro.
    """
    found = shutil.which(tool)
    if found:
        return found

    candidates: dict[int, str] = {}
    if os.name == "nt":
        for v in range(20, 13, -1):
            p = Path(rf"C:\Program Files\PostgreSQL\{v}\bin\{tool}.exe")
            if p.exists():
                candidates[v] = str(p)
    else:
        for v in range(20, 13, -1):
            p = Path(f"/usr/lib/postgresql/{v}/bin/{tool}")
            if p.exists():
                candidates[v] = str(p)

    if not candidates:
        return None

    if preferred_major and preferred_major in candidates:
        return candidates[preferred_major]

    return candidates[max(candidates)]


def criar_backup() -> Path:
    """Cria o arquivo .dump e retorna seu caminho."""
    data = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dump_name = f"backup_{data}.dump"
    dump_local = BACKUP_DIR / dump_name

    print("Criando backup do banco de dados...")
    server_major = _get_server_major_version()
    pg_dump = _find_pg_tool("pg_dump", preferred_major=server_major)

    used_local_dump = False
    if pg_dump:
        result = subprocess.run(
            [pg_dump, "-h", DB_HOST, "-p", DB_PORT, "-U", DB_USER, "-d", DB_NAME,
             "-F", "c", "-f", str(dump_local)],
            env=_pg_env(),
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            used_local_dump = True
        elif "version mismatch" in result.stderr:
            print(
                f"[WARN] pg_dump local incompatível com o servidor "
                f"(cliente: {pg_dump!r}, servidor v{server_major})."
            )
        else:
            raise subprocess.CalledProcessError(result.returncode, pg_dump, result.stderr)

    if not used_local_dump:
        raise RuntimeError(
            "Não foi possível gerar backup porque o pg_dump local é incompatível com o servidor.\n"
            f"Servidor PostgreSQL: v{server_major}\n"
            f"pg_dump local encontrado: {pg_dump or 'nenhum'}\n"
            "Instale um PostgreSQL client compatível com essa versão e rode novamente."
        )

    print(f"[OK] Backup salvo em: {dump_local}")
    return dump_local


def enviar_backup_email(dump_path: Path) -> None:
    """Comprime o dump com gzip e envia por email via Resend."""
    if not RESEND_API_KEY:
        print("RESEND_API_KEY não configurado — envio de email ignorado.")
        return
    if not BACKUP_EMAIL_TO:
        print("BACKUP_EMAIL_TO não configurado — envio de email ignorado.")
        return

    try:
        import resend
    except ImportError:
        print("Pacote 'resend' não instalado. Execute: pip install resend")
        return

    print("Comprimindo dump para envio...")
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb") as gz:
        gz.write(dump_path.read_bytes())
    gz_bytes = buffer.getvalue()

    tamanho_mb = len(gz_bytes) / 1024 / 1024
    print(f"Tamanho comprimido: {tamanho_mb:.2f} MB")

    data_fmt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    subject = f"[insight-invest] Backup do banco — {data_fmt}"

    muita_grande = tamanho_mb > 40
    if muita_grande:
        print(f"[WARN] Arquivo comprimido ({tamanho_mb:.1f} MB) excede limite de 40 MB — enviando sem anexo.")

    params = {
        "from": RESEND_FROM,
        "to": [BACKUP_EMAIL_TO],
        "subject": subject,
        "html": f"""
            <h3>Backup do banco de dados — insight-invest</h3>
            <p>Gerado em: <b>{data_fmt}</b></p>
            <ul>
                <li><b>Host:</b> {DB_HOST}:{DB_PORT}</li>
                <li><b>Banco:</b> {DB_NAME}</li>
                <li><b>Arquivo:</b> {dump_path.name}</li>
                <li><b>Tamanho comprimido:</b> {tamanho_mb:.2f} MB</li>
            </ul>
            {"<p>⚠️ Arquivo muito grande para anexar (&gt;40 MB). Backup salvo localmente.</p>"
             if muita_grande else
             "<p>O arquivo <code>.dump.gz</code> está em anexo.</p>"}
        """,
    }

    if not muita_grande:
        params["attachments"] = [
            {
                "filename": dump_path.name + ".gz",
                "content": list(gz_bytes),
            }
        ]

    resend.api_key = RESEND_API_KEY
    response = resend.Emails.send(params)
    msg_id = response.get("id") if isinstance(response, dict) else str(response)
    print(f"[OK] Email enviado! ID: {msg_id}")


def restaurar_backup(arquivo_dump: str | None = None):
    backups = list(BACKUP_DIR.glob("*.dump"))
    if not backups:
        print("Nenhum arquivo de backup encontrado.")
        return

    if arquivo_dump:
        arquivo = Path(arquivo_dump)
        if not arquivo.is_file():
            possivel = BACKUP_DIR / arquivo_dump
            if possivel.is_file():
                arquivo = possivel
            else:
                print(f"Arquivo de dump não encontrado: {arquivo_dump}")
                return
    else:
        print("\nArquivos disponíveis na pasta de backup:")
        for i, file in enumerate(backups):
            print(f"[{i}] {file.name}")

        escolha = input("Digite o número do arquivo que deseja restaurar: ")
        try:
            arquivo = backups[int(escolha)]
        except (ValueError, IndexError):
            print("Escolha inválida.")
            return

    print("Restaurando o banco de dados...")

    flags_comuns = ["--clean", "--if-exists", "--no-owner", "--no-privileges", "--verbose"]

    pg_restore = _find_pg_tool("pg_restore")
    if not pg_restore:
        raise RuntimeError(
            "pg_restore não encontrado no sistema. Instale PostgreSQL client."
        )

    subprocess.run(
        [pg_restore, "-h", DB_HOST, "-p", DB_PORT, "-U", DB_USER, "-d", DB_NAME,
         *flags_comuns, str(arquivo)],
        check=True,
        env=_pg_env(),
    )

    print("[OK] Banco restaurado com sucesso!")


def main():
    parser = argparse.ArgumentParser(description="Backup e restauração PostgreSQL")
    parser.add_argument("--criar", action="store_true", help="Criar backup")
    parser.add_argument("--restaurar", action="store_true", help="Restaurar backup")
    parser.add_argument("--arquivo", type=str, help="Arquivo dump para restaurar (nome ou caminho)")
    parser.add_argument("--no-email", action="store_true", help="Não envia email após backup")
    args = parser.parse_args()

    if args.criar:
        try:
            dump = criar_backup()
            if not args.no_email:
                enviar_backup_email(dump)
        except Exception as exc:
            print(f"[ERRO] Erro ao criar backup: {exc}")
        return

    if args.restaurar:
        try:
            restaurar_backup(args.arquivo)
        except Exception as exc:
            print(f"[ERRO] Erro ao restaurar backup: {exc}")
        return

    print("\n Escolha uma opção:")
    print("1. Fazer backup do banco (e enviar por email se configurado)")
    print("2. Restaurar um backup")

    opcao = input("Digite 1 ou 2: ")

    if opcao == "1":
        try:
            dump = criar_backup()
            enviar_backup_email(dump)
        except Exception as exc:
            print(f"[ERRO] Erro ao criar backup: {exc}")
    elif opcao == "2":
        try:
            restaurar_backup(args.arquivo)
        except Exception as exc:
            print(f"[ERRO] Erro ao restaurar backup: {exc}")
    else:
        print("[ERRO] Opção inválida.")


if __name__ == "__main__":
    main()
