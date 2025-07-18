# dashboard/callbacks.py

from dash import Input, Output, State, no_update, dash_table, html, dcc
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
from datetime import datetime

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
            # pega a última data_calculo só para exibir
            conn = get_connection()
            df_date = pd.read_sql_query(
                "SELECT MAX(data_calculo) AS ultima_data FROM resultados_precos",
                conn
            )
            conn.close()
            ultima_calc = df_date["ultima_data"].iloc[0].strftime("%Y-%m-%d")

            return dbc.Row([
                dbc.Col([
                    html.H5("Previsão de Preço - 10 dias à frente"),

                    # botão único de disparo
                    dbc.Button("Carregar", id="btn-load-pred", color="success", className="mb-3"),

                    # exibe apenas a data de cálculo usada
                    html.Div([
                        html.Strong("Data de Cálculo: "),
                        html.Span(ultima_calc)
                    ], className="mb-2"),

                    html.Hr(),

                    # tabela onde virão todas as 10 datas e todas as ações
                    dash_table.DataTable(
                        id="table-previsao",
                        columns=[],
                        data=[],
                        page_size=20,
                        sort_action="native",
                        filter_action="native",    # ativa filtros por coluna
                        style_table={"overflowX": "auto"},
                        style_cell={"textAlign": "left", "minWidth": "100px"},
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
        Output("table-previsao", "data"),
        Output("table-previsao", "columns"),
        Input("btn-load-pred", "n_clicks")
    )
    def update_regressor_table(n_clicks):
        if not n_clicks:
            return no_update, no_update

        # 1) pega última data_calculo
        conn = get_connection()
        df_date = pd.read_sql_query(
            "SELECT MAX(data_coleta) AS ultima_data FROM indicadores_fundamentalistas",
            conn
        )
        conn.close()
        ultima_calc = df_date["ultima_data"].iloc[0]
        if isinstance(ultima_calc, str):
            ultima_calc = datetime.strptime(ultima_calc, "%Y-%m-%d").date()

        # 2) para cada horizonte de 1 a 10 dias, roda o pipeline e coleta o comp
        all_comps = []
        for dias in range(1, 11):
            _, comp = executar_pipeline_regressor(n_dias=dias, data_calculo=ultima_calc)
            # vamos usar apenas as colunas acao, data (previsao) e predito
            comp_slice = comp[["acao", "data", "predito"]].copy()
            all_comps.append(comp_slice)

        # concatena tudo: terá 150 ações × 10 datas = 1500 linhas (se não houver faltantes)
        df_all = pd.concat(all_comps, ignore_index=True)
        df_all.sort_values(["data", "acao"], inplace=True)

        # 3) prepara colunas e dados
        columns = [
            {"name": "Ação",           "id": "acao"},
            {"name": "Data Previsão",  "id": "data",    "type":"datetime"},
            {"name": "Preço Previsto","id": "predito","type":"numeric", "format":{"specifier":".2f"}},
        ]
        data = df_all.to_dict("records")

        return data, columns


    
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
