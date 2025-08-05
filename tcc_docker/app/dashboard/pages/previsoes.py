# dashboard/pages/previsoes.py

from dash import html, dcc, Input, Output, State, no_update, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import date
import time
import threading # Para executar tarefas em paralelo
import uuid      # Para gerar IDs únicos para cada tarefa
import json      # Para ler e escrever nos ficheiros de status
import os        # Para criar as pastas de status e resultados

# Importação da sua função de regressão
from regressor_preco import executar_pipeline_regressor

# --- CONFIGURAÇÃO DAS PASTAS DE CACHE ---
# Cria as pastas para guardar o progresso e os resultados, se não existirem.
if not os.path.exists("cache_status"):
    os.makedirs("cache_status")
if not os.path.exists("cache_results"):
    os.makedirs("cache_results")
# -----------------------------------------

# Função que será executada na thread separada
def calculation_worker(job_id, ticker, n_days):
    """Esta função faz o trabalho pesado em segundo plano."""
    status_file = f"cache_status/{job_id}.json"
    result_file = f"cache_results/{job_id}.json"

    print(f"THREAD {job_id}: Iniciada para {ticker} por {n_days} dias.")

    all_preds = []
    try:
        for i in range(1, n_days + 1):
            # Escreve o progresso atual no ficheiro de status
            progress_info = {"status": "running", "progress": int((i / n_days) * 100), "text": f"Processando dia {i} de {n_days}..."}
            with open(status_file, "w") as f:
                json.dump(progress_info, f)

            # Executa a sua função de regressão
            _, comp = executar_pipeline_regressor(
                n_dias=i, data_calculo=date.today(), save_to_db=False, tickers=[ticker]
            )
            if not comp.empty:
                comp = comp.copy()
                comp["dias_a_frente"] = i
                all_preds.append(comp)

        # Após o loop, concatena os resultados
        final_df = pd.concat(all_preds, ignore_index=True)

        # Salva o resultado final num ficheiro
        final_df.to_json(result_file, orient="split")

        # Atualiza o status para "complete"
        final_status = {"status": "complete", "progress": 100, "text": "Concluído!"}
        with open(status_file, "w") as f:
            json.dump(final_status, f)

        print(f"THREAD {job_id}: Concluída com sucesso.")

    except Exception as e:
        # Em caso de erro, anota o erro no status
        print(f"THREAD {job_id}: ERRO - {e}")
        error_status = {"status": "error", "progress": 0, "text": f"Ocorreu um erro: {e}"}
        with open(status_file, "w") as f:
            json.dump(error_status, f)


def layout_previsoes():
    """Define o layout da página, incluindo um dcc.Store para o job_id."""
    input_style = {
        "backgroundColor": "#2c2c3e", "color": "#e0e0e0", "border": "1px solid #444",
        "height": "38px", "borderRadius": "0.375rem"
    }
    return dbc.Container([
        dcc.Store(id='job-id-store'), # Guarda o "ticket" da tarefa atual
        dcc.Interval(id='progress-interval', interval=1000, disabled=True), # O nosso "despertador"
        dbc.Card([
            dbc.CardHeader("🔮 Previsão de Preço — Multi-Dia"),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col(dbc.Input(id="input-ticker-prev", type="text", placeholder="Ticker (ex: PETR4)", style=input_style), width=4),
                    dbc.Col(dbc.Input(id="input-n-days-prev", type="number", min=1, step=1, value=10, placeholder="Dias à frente", style=input_style), width=4),
                    dbc.Col(dbc.Button("Carregar", id="btn-load-pred", color="primary", className="w-100", style=input_style), width=4),
                ], className="g-2 mb-4", align="center"),
                dbc.Progress(id="loading-progress-bar", value=0, style={"height": "20px"}),
                html.P(id="progress-text", className="text-center mt-2"),
                dash_table.DataTable(
                    id="table-previsao", columns=[], data=[], page_size=20, sort_action="native",
                    style_table={"overflowX": "auto"},
                    style_header={"backgroundColor": "#34344e", "color": "#ffffff", "fontWeight": "bold"},
                    style_cell={"backgroundColor": "#2a2a3d", "color": "#e0e0e0", "padding": "10px"},
                )
            ])
        ])
    ], fluid=True)


def register_callbacks_previsoes(app):

    # CALLBACK 1: Inicia a tarefa em segundo plano
    @app.callback(
        Output('job-id-store', 'data'),
        Output('progress-interval', 'disabled'),
        Output('btn-load-pred', 'disabled'),
        Output("table-previsao", "data"), # Limpa a tabela
        Input("btn-load-pred", "n_clicks"),
        State("input-ticker-prev", "value"),
        State("input-n-days-prev", "value"),
        prevent_initial_call=True
    )
    def start_job(n_clicks, ticker, n_days):
        if not ticker or not n_days:
            return no_update, no_update, no_update, no_update

        job_id = str(uuid.uuid4()) # Gera um "ticket" único

        # Cria a thread com a nossa função 'calculation_worker'
        thread = threading.Thread(target=calculation_worker, args=(job_id, ticker, int(n_days)))
        thread.start() # Inicia a thread

        # Retorna o ID do job, ativa o intervalo e desativa o botão
        return {"job_id": job_id}, False, True, []

    # CALLBACK 2: Atualiza a interface com o progresso
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
            # Tarefa concluída: carrega os resultados e para o intervalo
            result_file = f"cache_results/{job_id}.json"
            final_df = pd.read_json(result_file, orient="split")
            columns = [{"name": col, "id": col} for col in final_df.columns]
            return 100, "Concluído!", final_df.to_dict('records'), columns, True, False
        
        elif status.get("status") == "error":
            # Tarefa falhou: mostra o erro e para o intervalo
            return 0, text, [], [], True, False

        else:
            # Tarefa em andamento: atualiza a barra e continua
            return progress, text, no_update, no_update, False, True