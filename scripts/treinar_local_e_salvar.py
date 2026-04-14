import argparse
import os
import sys
from datetime import date
from pathlib import Path
import requests

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.core.db_connection import get_connection
from src.models.classificador import executar_pipeline_classificador
from src.models.regressor_preco import executar_pipeline_regressor
from src.models.recomendador_acoes import recomendar_varias_acoes

MODELO_NOME = "modelo_classificador_desempenho.pkl"


def upload_modelo_para_railway():
    api_url = os.getenv("API_URL", "").rstrip("/")
    api_key = os.getenv("API_KEY", "")
    modelo_path = _PROJECT_ROOT / "modelo" / MODELO_NOME

    if not api_url:
        raise RuntimeError("API_URL ausente no .env. Não foi possível enviar modelo para Railway.")
    if not api_key:
        raise RuntimeError("API_KEY ausente no .env. Não foi possível enviar modelo para Railway.")
    if not modelo_path.exists():
        raise FileNotFoundError(f"Modelo local não encontrado em: {modelo_path}")

    endpoint = f"{api_url}/modelo/upload"
    headers = {"X-API-Key": api_key}

    with modelo_path.open("rb") as f:
        files = {"arquivo": (MODELO_NOME, f, "application/octet-stream")}
        resp = requests.post(endpoint, headers=headers, files=files, timeout=180)

    if resp.status_code != 200:
        raise RuntimeError(f"Upload falhou ({resp.status_code}): {resp.text}")

    print(f"Modelo enviado para Railway com sucesso: {endpoint}")
    print(f"Resposta: {resp.text}")


def main():
    parser = argparse.ArgumentParser(
        description="Executa job local e salva dados no PostgreSQL Railway via .env."
    )
    parser.add_argument(
        "--job",
        choices=["todos", "classificador", "regressor", "recomendacoes"],
        default="todos",
        help="Seleciona qual job executar. Padrão: todos.",
    )
    parser.add_argument("--n-dias", type=int, default=10, help="Horizonte em dias para regressão.")
    parser.add_argument(
        "--data-calculo",
        default=date.today().isoformat(),
        help="Data base no formato AAAA-MM-DD. Padrão: hoje.",
    )
    parser.add_argument(
        "--nao-enviar-modelo",
        action="store_true",
        help="Quando rodar classificador, não envia .pkl para Railway.",
    )
    args = parser.parse_args()

    data_calculo = date.fromisoformat(args.data_calculo)

    print("=== Pipeline local iniciado ===")
    print(f"Job: {args.job} | Data cálculo: {data_calculo} | n_dias: {args.n_dias}")

    if args.job in ("todos", "classificador"):
        print("[1] Treinando classificador local...")
        executar_pipeline_classificador()
        print("[1] Classificador concluído.")
        if not args.nao_enviar_modelo:
            print("[1] Enviando modelo para Railway...")
            upload_modelo_para_railway()
        else:
            print("[1] Upload de modelo pulado por flag.")

    if args.job in ("todos", "regressor"):
        print("[2] Treinando regressor e salvando no banco Railway...")
        executar_pipeline_regressor(
            n_dias=args.n_dias,
            data_calculo=data_calculo,
            save_to_db=True,
        )
        print("[2] Regressor concluído.")

    if args.job in ("todos", "recomendacoes"):
        print("[3] Gerando recomendações e salvando no banco Railway...")
        conn = get_connection()
        try:
            recomendar_varias_acoes(conn)
        finally:
            conn.close()
        print("[3] Recomendações concluídas.")

    print("=== Pipeline local finalizado ===")


if __name__ == "__main__":
    main()
