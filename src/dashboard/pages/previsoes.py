from dash import html, dcc, Input, Output, State, no_update, dash_table
import dash_bootstrap_components as dbc, pandas as pd, threading, uuid, json, os
from pathlib import Path
from datetime import date
from src.models.regressor_preco import executar_pipeline_multidia

# --- LOCALIZAÇÃO DO REPOSITÓRIO BASE ---
# src/dashboard/pages/previsoes.py → src/dashboard/pages → src/dashboard → src → project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CACHE_STATUS_DIR = str(_PROJECT_ROOT / "cache_status")
CACHE_RESULTS_DIR = str(_PROJECT_ROOT / "cache_results")
# -----------------------------------------

# --- CONFIGURAÇÃO DAS PASTAS DE CACHE ---
if not os.path.exists(CACHE_STATUS_DIR):
    os.makedirs(CACHE_STATUS_DIR)
if not os.path.exists(CACHE_RESULTS_DIR):
    os.makedirs(CACHE_RESULTS_DIR)
# -----------------------------------------

def calculation_worker(job_id, ticker, n_days):
    """Esta função faz o trabalho pesado em segundo plano."""
    status_file = os.path.join(CACHE_STATUS_DIR, f"{job_id}.json")
    result_file = os.path.join(CACHE_RESULTS_DIR, f"{job_id}.json")

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

        # Remoção dos arquivos de cache foi REMOVIDA daqui!
        # O arquivo será removido pelo callback após leitura.

    except Exception as e:
        print(f"THREAD {job_id}: ERRO - {e}")
        error_status = {"status": "error", "progress": 0, "text": f"Ocorreu um erro: {e}"}
        with open(status_file, "w") as f:
            json.dump(error_status, f)
        # Remoção dos arquivos de cache foi REMOVIDA daqui!
        # Remove os arquivos das pastas de cache também em caso de erro
        for folder in [CACHE_STATUS_DIR, CACHE_RESULTS_DIR]:
            try:
                for filename in os.listdir(folder):
                    file_path = os.path.join(folder, filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
            except Exception as e:
                print(f"Erro ao limpar arquivos em {folder}: {e}")


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
                        dbc.Label("Ticker", html_for="input-ticker-prev", className="text-muted small mb-1"),
                        dbc.Input(id="input-ticker-prev", type="text", placeholder="Ex: PETR4", className="input-dark", value="PETR4"),
                    ], width=12, sm=4, md=2),
                    dbc.Col([
                        dbc.Label("Dias à frente", html_for="input-n-days-prev", className="text-muted small mb-1"),
                        dbc.Input(id="input-n-days-prev", type="number", min=1, step=1, value=10, placeholder="Dias", className="input-dark"),
                    ], width=12, sm=4, md=2),
                    dbc.Col(
                        dbc.Button("Gerar Previsão", id="btn-load-pred", className="w-100 btn-botaoacao"),
                        width=12, sm=4, md=2, className="align-self-end"
                    ),
                ], className="g-2 mb-4", justify="start"),

                # Envolva barra de progresso e texto em um Div controlável
                html.Div(
                    id="progress-container",
                    style={"display": "none"},
                    children=[
                        dbc.Progress(id="loading-progress-bar", value=0, style={"height": "20px"}, className="progress-bar-purple", striped=True, animated=True),
                        html.P(id="progress-text", className="text-center mt-2"),
                    ]
                ),
                dash_table.DataTable(
                    id="table-previsao", columns=[], data=[], page_size=20, sort_action="native",
                    style_table={"overflowX": "auto"},
                    style_header={"backgroundColor": "#5561ff", "color": "#ffffff", "fontWeight": "bold"},
                    style_cell={"backgroundColor": "#1e1e2f", "color": "#e0e0e0", "textAlign": "center",
                                "padding": "6px", "whiteSpace": "normal", "height": "auto"},
                    style_data_conditional=[{"if": {"state": "selected"}, "backgroundColor": "#5561ff", "color": "#ffffff"}],
                )
            ])
        ])
    ], fluid=True)


def register_callbacks_previsoes(app):
    # Callback de início de tarefa
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
        Output('progress-container', 'style', allow_duplicate=True),  # Adicione allow_duplicate=True aqui
        Input('progress-interval', 'n_intervals'),
        State('job-id-store', 'data'),
        prevent_initial_call=True
    )
    def update_progress(n, job_data):
        job_id = job_data.get("job_id")
        if not job_id:
            return no_update, no_update, no_update, no_update, True, False, {"display": "none"}

        status_file = os.path.join(CACHE_STATUS_DIR, f"{job_id}.json")
        
        try:
            with open(status_file, "r") as f:
                status = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Esconde barra de progresso se não houver status
            return no_update, "", no_update, no_update, False, False, {"display": "none"}

        progress = status.get("progress", 0)
        text = status.get("text", "")

        if status.get("status") == "complete":
            result_file = os.path.join(CACHE_RESULTS_DIR, f"{job_id}.json")
            final_df = pd.read_json(result_file, orient="split")

            if 'data_previsao' in final_df.columns:
                final_df['data_previsao'] = pd.to_datetime(final_df['data_previsao']).dt.strftime('%Y-%m-%d')
            
            column_name_map = {
                'acao': 'Ação',
                'data_previsao': 'Data da Previsão',
                'preco_previsto': 'Preço Previsto',
                'dias_a_frente': 'Dias à Frente'
            }

            columns = [
                {"name": column_name_map.get(col, col), "id": col}
                for col in final_df.columns
            ]
            
            try:
                if os.path.isfile(status_file):
                    os.remove(status_file)
                if os.path.isfile(result_file):
                    os.remove(result_file)
            except Exception as e:
                print(f"Erro ao remover arquivos do job {job_id}: {e}")

            # Esconde barra de progresso ao concluir e habilita botão
            return 100, "Concluído!", final_df.to_dict('records'), columns, True, False, {"display": "none"}
        
        elif status.get("status") == "error":
            # Esconde barra de progresso em caso de erro e habilita botão
            return 0, text, [], [], True, False, {"display": "none"}

        else:
            # Mostra barra de progresso enquanto processa e desabilita botão
            return progress, text, no_update, no_update, False, True, {"display": "block"}