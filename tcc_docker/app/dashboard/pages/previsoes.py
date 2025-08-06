# dashboard/pages/previsoes.py

from dash import html, dcc, Input, Output, State, no_update, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import date
import threading
import uuid
import json
import os

# Importação da sua função de regressão
from regressor_preco import executar_pipeline_regressor
from regressor_preco import executar_pipeline_multidia
# --- CONFIGURAÇÃO DAS PASTAS DE CACHE ---
if not os.path.exists("cache_status"):
    os.makedirs("cache_status")
if not os.path.exists("cache_results"):
    os.makedirs("cache_results")
# -----------------------------------------

def calculation_worker(job_id, ticker, n_days):
    """Esta função faz o trabalho pesado em segundo plano."""
    status_file = f"cache_status/{job_id}.json"
    result_file = f"cache_results/{job_id}.json"

    print(f"THREAD {job_id}: Iniciada para {ticker} por {n_days} dias.")

    try:
        # Função de callback para atualizar o progresso
        def report_progress(current_day, total_days):
            progress_info = {
                "status": "running",
                "progress": int((current_day / total_days) * 100),
                "text": f"Processando dia {current_day} de {total_days}..."
            }
            with open(status_file, "w") as f:
                json.dump(progress_info, f)

        # Chama a nova função otimizada UMA ÚNICA VEZ
        final_df = executar_pipeline_multidia(
            max_dias=n_days,
            data_calculo=date.today(),
            save_to_db=False,  # Não salva no DB neste contexto, pois é só para exibição
            tickers=[ticker],
            progress_callback=report_progress
        )

        if final_df.empty:
             raise ValueError("Nenhuma previsão foi gerada. Verifique os dados de entrada.")

        # Salva o resultado final
        final_df.to_json(result_file, orient="split", date_format="iso")

        # Atualiza o status para concluído
        final_status = {"status": "complete", "progress": 100, "text": "Concluído!"}
        with open(status_file, "w") as f:
            json.dump(final_status, f)

        print(f"THREAD {job_id}: Concluída com sucesso.")

    except Exception as e:
        print(f"THREAD {job_id}: ERRO - {e}")
        error_status = {"status": "error", "progress": 0, "text": f"Ocorreu um erro: {e}"}
        with open(status_file, "w") as f:
            json.dump(error_status, f)


def layout_previsoes():
    """Define o layout da página."""
    return dbc.Container([
        dcc.Store(id='job-id-store'),
        dcc.Interval(id='progress-interval', interval=1000, disabled=True),
        dbc.Card([
            dbc.CardHeader("🔮 Previsão de Preço — Multi-Dia"),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Input(id="input-ticker-prev", type="text", placeholder="Ticker (ex: PETR4)", className="input-dark", value="PETR4"),
                        dbc.Input(id="input-n-days-prev", type="number", min=1, step=1, value=10, placeholder="Dias à frente", className="input-dark mt-2"),
                    ], width=12, sm=5, md=2),
                        dbc.Col(
                            dbc.Button("Carregar", id="btn-load-pred", className="w-100 btn-botaoacao"),
                            width=12, sm=4, md=1
                        ),
                ], className="g-2 mb-4", justify="start"),

                dbc.Progress(id="loading-progress-bar", value=0, style={"height": "20px"}, className="progress-bar-purple", striped=True, animated=True),
                html.P(id="progress-text", className="text-center mt-2"),
                dash_table.DataTable(
                    id="table-previsao", columns=[], data=[], page_size=20, sort_action="native",
                    style_table={"overflowX": "auto"},
                )
            ])
        ])
    ], fluid=True)


def register_callbacks_previsoes(app):
    # Callback de início de tarefa (sem alterações)
    @app.callback(
        Output('job-id-store', 'data'),
        Output('progress-interval', 'disabled'),
        Output('btn-load-pred', 'disabled'),
        Output("table-previsao", "data"),
        Input("btn-load-pred", "n_clicks"),
        State("input-ticker-prev", "value"),
        State("input-n-days-prev", "value"),
        prevent_initial_call=True
    )
    def start_job(n_clicks, ticker, n_days):
        if not ticker or not n_days:
            return no_update, no_update, no_update, no_update

        job_id = str(uuid.uuid4())
        thread = threading.Thread(target=calculation_worker, args=(job_id, ticker, int(n_days)))
        thread.start()

        return {"job_id": job_id}, False, True, []

    # Callback de atualização de progresso
    @app.callback(
        Output('loading-progress-bar', 'value'),
        Output('progress-text', 'children'),
        Output('table-previsao', 'data', allow_duplicate=True),
        Output('table-previsao', 'columns'),
        Output('progress-interval', 'disabled', allow_duplicate=True),
        Output('btn-load-pred', 'disabled', allow_duplicate=True),
        Input('progress-interval', 'n_intervals'),
        State('job-id-store', 'data'),
        prevent_initial_call=True
    )
    def update_progress(n, job_data):
        job_id = job_data.get("job_id")
        if not job_id:
            return no_update, no_update, no_update, no_update, True, False

        status_file = f"cache_status/{job_id}.json"
        
        try:
            with open(status_file, "r") as f:
                status = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return no_update, "Aguardando início...", no_update, no_update, False, True

        progress = status.get("progress", 0)
        text = status.get("text", "")

        if status.get("status") == "complete":
            result_file = f"cache_results/{job_id}.json"
            final_df = pd.read_json(result_file, orient="split")

            if 'data_previsao' in final_df.columns:
                final_df['data_previsao'] = pd.to_datetime(final_df['data_previsao']).dt.strftime('%Y-%m-%d')
            
            # AJUSTE 1: Mapeamento dos nomes das colunas
            column_name_map = {
                'acao': 'Ação',
                'data_previsao': 'Data da Previsão',
                'preco_previsto': 'Preço Previsto',
                'dias_a_frente': 'Dias à Frente'
            }

            # Usa o mapa para criar os cabeçalhos da tabela
            columns = [
                {"name": column_name_map.get(col, col), "id": col}
                for col in final_df.columns
            ]
            
            return 100, "Concluído!", final_df.to_dict('records'), columns, True, False
        
        elif status.get("status") == "error":
            return 0, text, [], [], True, False

        else:
            return progress, text, no_update, no_update, False, True