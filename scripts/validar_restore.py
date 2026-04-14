import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.core.db_connection import get_connection


def main():
    tabelas = [
        "indicadores_fundamentalistas",
        "resultados_precos",
        "recomendacoes_acoes",
    ]

    conn = get_connection()
    cur = conn.cursor()
    try:
        print("Contagem de registros por tabela:")
        for tabela in tabelas:
            cur.execute(f"SELECT COUNT(*) FROM public.{tabela}")
            qtd = cur.fetchone()[0]
            print(f"- {tabela}: {qtd}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
