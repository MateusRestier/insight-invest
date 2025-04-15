import subprocess
import os
from pathlib import Path
import schedule
import time

# Diretório base
BASE_DIR = Path(__file__).parent
scraper_path = BASE_DIR / "scraper_indicadores.py"
backup_path = BASE_DIR / "backup.py"

def executar_comando_chcp():
    print("🔧 Configurando terminal para UTF-8 (chcp 65001)...")
    subprocess.run("chcp 65001", shell=True)

def executar_script(script_path):
    print(f"▶️ Executando: {script_path.name}")
    resultado = subprocess.run(
        ["python", str(script_path)],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"}
    )

    if resultado.returncode == 0:
        print(f"✅ {script_path.name} executado com sucesso.\n")
    else:
        print(f"❌ Erro ao executar {script_path.name}:\n{resultado.stderr}")

def main():
    executar_comando_chcp()
    executar_script(scraper_path)
    executar_script(backup_path)

# Agendar execução
schedule.every().day.at("01:00").do(main)

while True:
    schedule.run_pending()
    time.sleep(1)

'''if __name__ == "__main__":
    main()'''
