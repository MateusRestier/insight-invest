# dashboard/pages/previsoes.py

from dash import html, dcc, Input, Output, State, no_update, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import date

# Importação real da sua função a partir do arquivo vizinho.
from regressor_preco import executar_pipeline_regressor

# -----------------------------------------------------------------------------
# Layout e callbacks para a página "Previsões de Preço"
# -----------------------------------------------------------------------------

def layout_previsoes():
    """Define o layout da página de previsões."""
    
    input_style = {
        "backgroundColor": "#2c2c3e",
        "color": "#e0e0e0",
        "border": "1px solid #444",
        "height": "38px",
        "borderRadius": "0.375rem"
    }

    return dbc.Container([
        dbc.Card([
            dbc.CardHeader("🔮 Previsão de Preço — Multi-Dia"),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col(
                        dbc.Input(id="input-ticker-prev", type="text", placeholder="Ticker (ex: PETR4)", style=input_style),
                        width=4
                    ),
                    dbc.Col(
                        dbc.Input(id="input-n-days-prev", type="number", min=1, step=1, value=10, placeholder="Dias à frente", style=input_style),
                        width=4
                    ),
                    dbc.Col(
                        dbc.Button("Carregar", id="btn-load-pred", color="primary", className="w-100", style={"height": "38px", "borderRadius": "0.375rem"}),
                        width=4
                    ),
                ], className="g-2 mb-4", align="center"),

                html.Div(id="progress-alert-container"),

                dash_table.DataTable(
                    id="table-previsao",
                    columns=[],
                    data=[],
                    page_size=20,
                    sort_action="native",
                    style_table={"overflowX": "auto"},
                    style_header={"backgroundColor": "#34344e", "color": "#ffffff", "fontWeight": "bold"},
                    style_cell={"backgroundColor": "#2a2a3d", "color": "#e0e0e0", "padding": "10px", "minWidth": "120px"},
                    style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "#252535"}]
                )
            ])
        ], className="shadow-sm mb-4"),

        # O dcc.Interval foi removido. O dcc.Store controlará todo o fluxo.
        dcc.Store(id="store-previsao-data"),
    ], fluid=True)


def register_callbacks_previsoes(app):
    """Registra os callbacks da página de previsões."""

    # CALLBACK 1: Inicia o processo, preparando o dcc.Store
    @app.callback(
        Output("store-previsao-data", "data"),
        Output("progress-alert-container", "children"),
        Output("table-previsao", "data"),
        Input("btn-load-pred", "n_clicks"),
        State("input-ticker-prev", "value"),
        State("input-n-days-prev", "value"),
        prevent_initial_call=True
    )
    def start_prediction_process(n_clicks, ticker, n_days):
        """
        Acionado pelo botão, este callback apenas prepara o estado inicial no dcc.Store.
        Essa atualização no dcc.Store será o gatilho para o próximo callback começar o trabalho.
        """
        if not ticker or not n_days:
            alert = dbc.Alert("Por favor, preencha o Ticker e o número de Dias.", color="warning", duration=4000)
            return no_update, alert, no_update

        try:
            n_days = int(n_days)
            if n_days <= 0: raise ValueError
        except (ValueError, TypeError):
            alert = dbc.Alert("O número de dias deve ser um inteiro positivo.", color="danger", duration=4000)
            return no_update, alert, no_update
        
        initial_state = {
            "ticker": ticker.strip().upper(),
            "n_days_total": n_days,
            "current_day": 0,
            "results": [],
            "status": "running" # Status inicial que começa a cadeia
        }

        progress_component = html.Div([
            dbc.Progress(id="loading-progress-bar", value=0, max=100, color="info", striped=True, animated=True),
            html.Div(id="loading-status", className="mt-2", style={"textAlign": "center", "color": "#e0e0e0"})
        ])

        return initial_state, progress_component, []


    # CALLBACK 2: Executa um passo do cálculo e se auto-aciona para o próximo passo
    @app.callback(
        Output("loading-progress-bar", "value"),
        Output("loading-status", "children"),
        Output("table-previsao", "data", allow_duplicate=True),
        Output("table-previsao", "columns"),
        Output("store-previsao-data", "data", allow_duplicate=True),
        Output("progress-alert-container", "children", allow_duplicate=True),
        # A MUDANÇA PRINCIPAL: O gatilho agora é a atualização do próprio dcc.Store
        Input("store-previsao-data", "data"),
        prevent_initial_call=True
    )
    def update_prediction_step(stored_data):
        """
        Acionado por uma atualização no dcc.Store. Ele executa um passo, atualiza o dcc.Store de novo,
        o que o aciona novamente, criando uma cadeia até a conclusão.
        """
        # Cláusula de guarda: Para o processo se o status não for 'running'
        if not stored_data or stored_data.get("status") != "running":
            # Se o status for 'complete' ou 'error', a cadeia para aqui.
            return no_update, no_update, no_update, no_update, no_update, no_update

        current_day = stored_data["current_day"] + 1
        n_days_total = stored_data["n_days_total"]
        
        # Se a primeira chamada já falhou, não tente de novo
        if current_day > n_days_total:
             stored_data["status"] = "complete"
             return 100, "Concluído!", stored_data['results'], no_update, stored_data, None

        ticker = stored_data["ticker"]
        
        try:
            _, comp = executar_pipeline_regressor(
                n_dias=current_day,
                data_calculo=date.today(),
                save_to_db=False,
                tickers=[ticker]
            )

            # Verifica se o pipeline retornou um resultado vazio para o ticker
            if comp.empty:
                print(f"⚠️ Aviso: Pipeline não retornou dados para o dia {current_day} do ticker {ticker}.")
            
            comp = comp.copy()
            comp["dias_a_frente"] = current_day
            
            updated_results = stored_data["results"]
            updated_results.extend(comp.to_dict("records"))

            progress_value = int((current_day / n_days_total) * 100)
            status_message = f"Processando previsão para o dia {current_day} de {n_days_total}..."

            columns = [
                {"name": "Ação", "id": "acao"},
                {"name": "Dias à Frente", "id": "dias_a_frente", "type": "numeric"},
                {"name": "Data Previsão", "id": "data_previsao", "type": "datetime"},
                {"name": "Preço Previsto", "id": "preco_previsto", "type": "numeric", "format": {"specifier": "R$ ,.2f"}},
            ]
            
            stored_data["current_day"] = current_day
            stored_data["results"] = updated_results

            if current_day >= n_days_total:
                stored_data["status"] = "complete" # Finaliza a cadeia
                return 100, "Concluído!", updated_results, columns, stored_data, None
            else:
                # O retorno aqui atualiza o dcc.Store, que vai disparar este mesmo callback de novo
                return progress_value, status_message, updated_results, columns, stored_data, no_update

        except Exception as e:
            print(f"❌ Erro ao executar o pipeline: {e}")
            alert = dbc.Alert(f"Ocorreu um erro ao processar o ticker {ticker}.", color="danger", dismissable=True)
            stored_data["status"] = "error" # Finaliza a cadeia com erro
            return 0, "Erro!", stored_data.get("results", []), no_update, stored_data, alert