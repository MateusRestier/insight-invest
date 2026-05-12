"""
Script utilitário para executar jobs de treino local e salvar resultados no Railway.

Pré-requisitos:
- Variáveis no `.env`: `DB_*`, `API_URL`, `API_KEY`.
- Endpoint `/modelo/upload` disponível na API em produção.

Exemplos:
- Rodar tudo:
    python scripts/treinar_local_e_salvar.py --job todos

- Rodar só classificador + enviar modelo para Railway:
    python scripts/treinar_local_e_salvar.py --job classificador

- Rodar só regressor e salvar previsões no banco:
    python scripts/treinar_local_e_salvar.py --job regressor --n-dias 10

- Backfill do regressor por período (sem vazamento temporal):
    python scripts/treinar_local_e_salvar.py --job regressor --n-dias 10 --data-inicio 2026-04-20 --data-fim 2026-04-30 --sem-vazamento-temporal

- Rodar apenas os dias pendentes desde a última execução:
    python scripts/treinar_local_e_salvar.py --job regressor --n-dias 10 --pendente

- Rodar só recomendações e salvar no banco:
    python scripts/treinar_local_e_salvar.py --job recomendacoes
"""

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path
import requests

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.core.db_connection import get_connection
from src.models.classificador import executar_pipeline_classificador
from src.models.regressor_preco import executar_pipeline_regressor, preparar_dados_cache
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
    parser.add_argument(
        "--data-inicio",
        default=None,
        help="Início de período (AAAA-MM-DD) para backfill do regressor.",
    )
    parser.add_argument(
        "--data-fim",
        default=None,
        help="Fim de período (AAAA-MM-DD) para backfill do regressor.",
    )
    parser.add_argument(
        "--sem-vazamento-temporal",
        action="store_true",
        help=(
            "No regressor, treina apenas com exemplos cujo alvo já seria conhecido "
            "na data_calculo (evita uso indireto de futuro no treino)."
        ),
    )
    parser.add_argument(
        "--pendente",
        action="store_true",
        help=(
            "Detecta a última data_calculo em resultados_precos e roda o backfill "
            "do dia seguinte até hoje. Ignora --data-inicio e --data-fim."
        ),
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
        # Resolve intervalo de datas a processar
        if args.pendente:
            conn = get_connection()
            try:
                import pandas as pd
                ultima = pd.read_sql_query(
                    "SELECT MAX(data_calculo) AS ultima FROM resultados_precos", conn
                ).iloc[0, 0]
            finally:
                conn.close()
            if ultima is None:
                raise RuntimeError(
                    "Tabela resultados_precos está vazia. Use --data-inicio/--data-fim para o primeiro backfill."
                )
            data_inicio = pd.Timestamp(ultima).date() + timedelta(days=1)
            data_fim = date.today()
            if data_inicio > data_fim:
                print("[2] Nenhum dia pendente — resultados_precos já está atualizado.")
                data_inicio = data_fim = None
            else:
                print(f"[2] Pendente detectado: {data_inicio} → {data_fim}")
        elif args.data_inicio or args.data_fim:
            if not (args.data_inicio and args.data_fim):
                raise ValueError("Para backfill, informe ambos --data-inicio e --data-fim.")
            data_inicio = date.fromisoformat(args.data_inicio)
            data_fim = date.fromisoformat(args.data_fim)
            if data_inicio > data_fim:
                raise ValueError("--data-inicio não pode ser maior que --data-fim.")
        else:
            data_inicio = data_fim = None

        if data_inicio and data_fim:
            print("[2] Regressor em backfill por período...")
            print("[2] Pré-carregando e processando dados (uma única vez)...")
            dados_cache = preparar_dados_cache(n_dias=args.n_dias)
            print("[2] Dados prontos. Iniciando iterações...")
            atual = data_inicio
            total = (data_fim - data_inicio).days + 1
            i = 1
            while atual <= data_fim:
                print(f"[2] [{i}/{total}] Rodando regressor para data_calculo={atual} ...")
                executar_pipeline_regressor(
                    n_dias=args.n_dias,
                    data_calculo=atual,
                    save_to_db=True,
                    sem_vazamento_temporal=args.sem_vazamento_temporal,
                    _dados_cache=dados_cache,
                )
                atual += timedelta(days=1)
                i += 1
            print("[2] Backfill do regressor concluído.")
        elif not args.pendente:
            print("[2] Treinando regressor e salvando no banco Railway...")
            executar_pipeline_regressor(
                n_dias=args.n_dias,
                data_calculo=data_calculo,
                save_to_db=True,
                sem_vazamento_temporal=args.sem_vazamento_temporal,
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
