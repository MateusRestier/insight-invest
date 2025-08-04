# dashboard/pages/previsoes.py

from dash import html, dcc, Input, Output, State, no_update, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import date
from regressor_preco import executar_pipeline_regressor

# -----------------------------------------------------------------------------
# Layout e callbacks para a página "Previsões de Preço"
# -----------------------------------------------------------------------------

def layout_previsoes():
    return dbc.Container([
        dbc.Card([
            dbc.CardHeader("🔮 Previsão de Preço — Multi-Dia"),
            dbc.CardBody([
                # Inputs: Ticker, Dias à frente e Botão (alinhados)
                dbc.Row([
                    dbc.Col(
                        dbc.Input(
                            id="input-ticker-prev",
                            type="text",
                            placeholder="Ticker (ex: PETR4)",
                            className="input-dark mb-2",
                            style={
                                "backgroundColor": "#2c2c3e",
                                "color": "#e0e0e0",
                                "border": "1px solid #444",
                                "height": "38px"
                            }
                        ),
                        width=4
                    ),
                    dbc.Col(
                        dbc.Input(
                            id="input-n-days-prev",
                            type="number",
                            min=1,
                            step=1,
                            value=10,
                            placeholder="Dias à frente",
                            className="input-dark mb-2",
                            style={
                                "backgroundColor": "#2c2c3e",
                                "color": "#e0e0e0",
                                "border": "1px solid #444",
                                "height": "38px"
                            }
                        ),
                        width=4
                    ),
                    dbc.Col(
                        dbc.Button(
                            "Carregar",
                            id="btn-load-pred",
                            color="primary",
                            className="btn-botaoacao",
                            style={"height": "38px"}
                        ),
                        width=4
                    ),
                ], className="g-3 mb-4", align="end"),  # alinhamento vertical

                # Tabela de resultados
                dash_table.DataTable(
                    id="table-previsao",
                    columns=[],
                    data=[],
                    page_size=20,
                    sort_action="native",
                    style_table={"overflowX": "auto"},
                    style_header={
                        "backgroundColor": "#34344e",
                        "color": "#ffffff",
                        "fontWeight": "bold"
                    },
                    style_cell={
                        "backgroundColor": "#2a2a3d",
                        "color": "#e0e0e0",
                        "padding": "5px",
                        "minWidth": "100px"
                    },
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "#252535"}
                    ]
                )
            ])
        ], className="shadow-sm mb-4")
    ], fluid=True)


def register_callbacks_previsoes(app):
    @app.callback(
        Output("table-previsao", "data"),
        Output("table-previsao", "columns"),
        Input("btn-load-pred", "n_clicks"),
        State("input-ticker-prev", "value"),
        State("input-n-days-prev", "value"),
    )
    def load_multi_day_predictions(n_clicks, ticker, n_days):
        if not n_clicks or not ticker or not n_days:
            return no_update, no_update

        ticker = ticker.strip().upper()
        try:
            n_days = int(n_days)
        except ValueError:
            return no_update, no_update

        all_preds = []
        for i in range(1, n_days + 1):
            _, comp = executar_pipeline_regressor(
                n_dias=i,
                data_calculo=date.today(),
                save_to_db=False,
                tickers=[ticker]
            )
            comp = comp.copy()
            comp["dias_a_frente"] = i
            all_preds.append(comp)

        if not all_preds:
            return [], []

        df = pd.concat(all_preds, ignore_index=True)
        data = df.to_dict("records")
        columns = [
            {"name": "Ação",           "id": "acao"},
            {"name": "Dias à Frente",  "id": "dias_a_frente", "type": "numeric"},
            {"name": "Data Previsão",  "id": "data_previsao", "type": "datetime"},
            {"name": "Preço Previsto", "id": "preco_previsto", "type": "numeric", "format": {"specifier": ".2f"}},
        ]
        return data, columns
