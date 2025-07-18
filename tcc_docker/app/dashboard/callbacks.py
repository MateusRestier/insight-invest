# dashboard/callbacks.py

from dash import Input, Output, State, no_update, dash_table, html, dcc
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# Importa seus módulos de backend
from scraper_indicadores import coletar_indicadores
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


        if tab == "tab-regressor":
            # --- 1) Busca última data_calculo e prepara as opções
            conn = get_connection()
            df_date = pd.read_sql_query(
                "SELECT MAX(data_calculo) AS ultima_data FROM resultados_precos", conn
            )
            df_prevs = pd.read_sql_query(
                """
                SELECT DISTINCT data_previsao
                FROM resultados_precos
                WHERE data_calculo = %s
                ORDER BY data_previsao DESC
                LIMIT 10
                """,
                conn,
                params=[df_date["ultima_data"].iloc[0]]
            )
            df_acao = pd.read_sql_query(
                "SELECT DISTINCT acao FROM resultados_precos WHERE data_calculo = %s ORDER BY acao",
                conn,
                params=[df_date["ultima_data"].iloc[0]]
            )
            conn.close()

            ultima_calc = df_date["ultima_data"].iloc[0].strftime("%Y-%m-%d")
            opts_prevs = [
                {"label": d.strftime("%Y-%m-%d"), "value": d.strftime("%Y-%m-%d")}
                for d in pd.to_datetime(df_prevs["data_previsao"])
            ]
            opts_acoes = [{"label": a, "value": a} for a in df_acao["acao"]]

            return dbc.Row([
                dbc.Col([
                    html.H5("Previsão de Preço - 10 dias à frente"),
                    dcc.Store(id="store-previsao-data"),
                    dbc.Button("Carregar", id="btn-load-pred", color="success", className="mb-3"),
                    html.Div([html.Strong("Data de Cálculo: "), html.Span(ultima_calc)], className="mb-2"),
                    html.Div([
                        html.Label("Data Previsão:"),
                        dcc.Dropdown(id="filter-previsao", options=opts_prevs,
                                     placeholder="Selecione um dia", clearable=False, style={"width":"180px"}),
                    ], style={"display":"inline-block","margin-right":"20px"}),
                    html.Div([
                        html.Label("Filtrar Ação:"),
                        dcc.Dropdown(id="filter-acao", options=opts_acoes,
                                     multi=True, placeholder="Todas", style={"width":"180px"}),
                    ], style={"display":"inline-block"}),
                    html.Hr(),
                    dash_table.DataTable(
                        id="table-previsao",
                        columns=[],
                        data=[],
                        page_size=20,
                        sort_action="native",
                        filter_action="none",  # usaremos filtros via callbacks
                        style_table={"overflowX":"auto"},
                        style_cell={"textAlign":"left","minWidth":"100px"},
                    )
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
        Output("store-previsao-data", "data"),
        Output("table-previsao", "columns"),
        Input("btn-load-pred", "n_clicks"),
    )
    def load_all_predictions(n_clicks):
        if not n_clicks:
            return no_update, no_update

        # 1) Pega última data_calculo
        conn = get_connection()
        df_date = pd.read_sql_query(
            "SELECT MAX(data_calculo) AS ultima_data FROM resultados_precos",
            conn
        )
        ultima_calc = pd.to_datetime(df_date["ultima_data"].iloc[0]).date()
        conn.close()

        # 2) Intervalo 1–10 dias
        start = ultima_calc + timedelta(days=1)
        end   = ultima_calc + timedelta(days=10)

        # 3) Consulta tudo de uma vez
        query = """
            SELECT acao,
                   data_previsao AS data,
                   preco_previsto AS predito
            FROM resultados_precos
            WHERE data_calculo = %s
              AND data_previsao BETWEEN %s AND %s
            ORDER BY data_previsao, acao
        """
        conn = get_connection()
        df = pd.read_sql_query(query, conn, params=[ultima_calc, start, end])
        conn.close()

        # 4) Prepara colunas (são fixas após o load)
        columns = [
            {"name":"Ação",           "id":"acao"},
            {"name":"Data Previsão",  "id":"data",    "type":"datetime"},
            {"name":"Preço Previsto","id":"predito", "type":"numeric", "format":{"specifier":".2f"}},
        ]

        # 5) Guarda tudo no Store
        data = df.to_dict("records")
        return data, columns


    @app.callback(
        Output("table-previsao", "data"),
        Input("store-previsao-data", "data"),
        Input("filter-previsao", "value"),
        Input("filter-acao", "value"),
    )
    def filter_predictions(stored, date_pref, acoes_sel):
        if stored is None:
            return no_update

        df = pd.DataFrame(stored)

        # aplica filtros em memória
        if date_pref:
            df = df[df["data"] == date_pref]
        if acoes_sel:
            df = df[df["acao"].isin(acoes_sel)]

        return df.to_dict("records")


    
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
