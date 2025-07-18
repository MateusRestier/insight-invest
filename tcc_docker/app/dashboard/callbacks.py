# dashboard/callbacks.py

import os
import sys

# Garante que "tcc_docker/app" esteja no path
ROOT = os.path.abspath(os.path.join(__file__, os.pardir, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dash import Input, Output, State, no_update, dash_table, html, dcc
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px

# Importa seus módulos de backend
from scraper_indicadores import coletar_indicadores
from regressor_preco import executar_pipeline_regressor
from recomendador_acoes import recomendar_acao
from db_connection import get_connection


def register_callbacks(app):
    @app.callback(
        Output("tab-content", "children"),
        Input("tabs", "active_tab")
    )
    def render_tab(tab):
        if tab == "tab-indicadores":
            return dbc.Row([
                dbc.Col([
                    html.H5("Selecione um ticker:"),
                    dcc.Input(
                        id="input-ticker-ind",
                        value="PETR4",
                        type="text",
                        style={"width": "150px"}
                    ),
                    dbc.Button(
                        "Carregar",
                        id="btn-load-ind",
                        color="primary",
                        className="mt-2"
                    ),
                    html.Hr(),
                    dash_table.DataTable(
                        id="table-indicadores",
                        columns=[],    # preenchidas pelo callback
                        data=[],       # preenchidas pelo callback
                        page_size=10,
                        style_table={"overflowX": "auto"},
                        style_cell={
                            "textAlign": "left",
                            "minWidth": "80px",
                            "whiteSpace": "normal"
                        },
                    )
                ], width=12)
            ])

        elif tab == "tab-regressor":
            # busca datas de cálculo no banco
            conn = get_connection()
            df_dates = pd.read_sql_query(
                "SELECT DISTINCT data_calculo FROM resultados_precos ORDER BY data_calculo",
                conn
            )
            conn.close()
            options = [
                {"label": d.strftime("%Y-%m-%d"), "value": d.strftime("%Y-%m-%d")}
                for d in df_dates["data_calculo"]
            ]

            return dbc.Row([
                dbc.Col([
                    html.H5("Previsão de Preço - 10 dias à frente"),
                    dcc.Dropdown(
                        id="dropdown-data-calculo",
                        options=options,
                        value=options[-1]["value"] if options else None,
                        style={"width": "200px"}
                    ),
                    dbc.Button(
                        "Prever",
                        id="btn-predict-price",
                        color="success",
                        className="mt-2"
                    ),
                    html.Hr(),
                    dcc.Graph(id="graf-previsao")
                ], width=12)
            ])

        elif tab == "tab-recomendador":
            return dbc.Row([
                dbc.Col([
                    html.H5("Recomendador de Ações"),
                    dcc.Input(
                        id="input-ticker-rec",
                        value="ITUB4",
                        type="text",
                        style={"width": "150px"}
                    ),
                    dbc.Button(
                        "Recomendar",
                        id="btn-recommend",
                        color="warning",
                        className="mt-2"
                    ),
                    html.Hr(),
                    html.Pre(
                        id="recomendation-output",
                        style={"whiteSpace": "pre-wrap", "wordBreak": "break-all"}
                    )
                ], width=12)
            ])

        else:
            return html.Div()

    @app.callback(
        Output("table-indicadores", "data"),
        Output("table-indicadores", "columns"),
        Input("btn-load-ind", "n_clicks"),
        State("input-ticker-ind", "value")
    )
    def update_indicators(n_clicks, ticker):
        if not n_clicks:
            return no_update, no_update

        resultado = coletar_indicadores(ticker)
        if isinstance(resultado, str):
            # erro na coleta
            return [{"error": resultado}], [{"name": "error", "id": "error"}]

        dados, _ = resultado
        df = pd.DataFrame([dados])

        data = df.to_dict("records")
        columns = [{"name": col, "id": col} for col in df.columns]

        return data, columns

    @app.callback(
        Output("graf-previsao", "figure"),
        Input("btn-predict-price", "n_clicks"),
        State("dropdown-data-calculo", "value")
    )
    def update_regressor(n_clicks, data_calculo):
        if not n_clicks or not data_calculo:
            return no_update

        # Executa regressão e retorna DataFrame de comparação
        _, comp = executar_pipeline_regressor(n_dias=10, data_calculo=data_calculo)
        # Garante colunas corretas
        if comp.empty:
            fig = px.scatter(title="Nenhum dado para essa data de cálculo.")
            return fig

        fig = px.scatter(
            comp,
            x="preco_real",
            y="predito",
            color="acao",
            title=f"Preço Previsto vs Real ({data_calculo})",
            labels={"predito": "Previsto", "preco_real": "Real"}
        )
        # Linha diagonal de referência
        fig.add_shape(
            type="line",
            x0=comp.preco_real.min(),
            y0=comp.preco_real.min(),
            x1=comp.preco_real.max(),
            y1=comp.preco_real.max(),
            line=dict(dash="dash")
        )
        return fig

    @app.callback(
        Output("recomendation-output", "children"),
        Input("btn-recommend", "n_clicks"),
        State("input-ticker-rec", "value")
    )
    def update_recommend(n_clicks, ticker):
        if not n_clicks:
            return no_update

        # Captura saída do recomendador
        from io import StringIO
        import sys
        buffer = StringIO()
        old_stdout = sys.stdout
        sys.stdout = buffer

        recomendar_acao(ticker)

        sys.stdout = old_stdout
        return buffer.getvalue()
