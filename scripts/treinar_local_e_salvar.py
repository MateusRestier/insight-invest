import argparse
import os
import sys
from datetime import date
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.core.db_connection import get_connection
from src.models.classificador import executar_pipeline_classificador
from src.models.regressor_preco import executar_pipeline_regressor
from src.models.recomendador_acoes import recomendar_varias_acoes


def main():
    parser = argparse.ArgumentParser(
        description="Executa treino local e salva resultados no banco configurado no .env."
    )
    parser.add_argument("--n-dias", type=int, default=10, help="Horizonte em dias para regressão.")
    parser.add_argument(
        "--data-calculo",
        default=date.today().isoformat(),
        help="Data base no formato AAAA-MM-DD. Padrão: hoje.",
    )
    parser.add_argument("--sem-classificador", action="store_true", help="Pula treino classificador.")
    parser.add_argument("--sem-regressor", action="store_true", help="Pula treino regressor.")
    parser.add_argument("--sem-recomendacoes", action="store_true", help="Pula geração de recomendações.")
    args = parser.parse_args()

    data_calculo = date.fromisoformat(args.data_calculo)

    print("=== Pipeline local iniciado ===")
    print(f"Data cálculo: {data_calculo} | n_dias: {args.n_dias}")

    if not args.sem_classificador:
        print("[1/3] Treinando classificador...")
        executar_pipeline_classificador()
        print("[1/3] Classificador concluído.")
    else:
        print("[1/3] Classificador pulado.")

    if not args.sem_regressor:
        print("[2/3] Treinando regressor e salvando no banco...")
        executar_pipeline_regressor(
            n_dias=args.n_dias,
            data_calculo=data_calculo,
            save_to_db=True,
        )
        print("[2/3] Regressor concluído.")
    else:
        print("[2/3] Regressor pulado.")

    if not args.sem_recomendacoes:
        print("[3/3] Gerando recomendações e salvando no banco...")
        conn = get_connection()
        try:
            recomendar_varias_acoes(conn)
        finally:
            conn.close()
        print("[3/3] Recomendações concluídas.")
    else:
        print("[3/3] Recomendações puladas.")

    print("=== Pipeline local finalizado ===")


if __name__ == "__main__":
    main()
