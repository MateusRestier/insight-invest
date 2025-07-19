from dash import html, dcc, dash_table, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import timedelta
from db_connection import get_connection

# -----------------------------------------------------------------------------
# Layout e callbacks para a página "Previsões de Preço"
# -----------------------------------------------------------------------------

def layout_previsoes():
    # 1) Busca a última data_calculo somente para exibição
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

            # Store para guardar o dataset carregado
            dcc.Store(id="store-previsao-data"),

            # Botão de carga inicial
            dbc.Button(
                "Carregar",
                id="btn-load-pred",
                color="success",
                className="mb-3"
            ),

            # Exibe a data_calculo fixa
            html.Div([
                html.Strong("Data de Cálculo: "),
                html.Span(ultima_calc)
            ], className="mb-2"),

            # Dropdown de Data Previsão (preenchido dinamicamente)
            html.Div([
                html.Label("Data Previsão:"),
                dcc.Dropdown(
                    id="filter-previsao",
                    options=[],        # definido em callback
                    placeholder="Selecione um dia",
                    clearable=False,
                    style={"width": "180px"}
                )
            ], style={"display": "inline-block", "margin-right": "20px"}),

            # Dropdown de Ação (preenchido dinamicamente)
            html.Div([
                html.Label("Filtrar Ação:"),
                dcc.Dropdown(
                    id="filter-acao",
                    options=[],        # definido em callback
                    multi=True,
                    placeholder="Todas",
                    style={"width": "180px"}
                )
            ], style={"display": "inline-block"}),

            html.Hr(),

            # Card contendo a tabela de previsões
            dbc.Card(
                [
                    dbc.CardHeader("📈 Previsões de Preço"),
                    dbc.CardBody(
                        dash_table.DataTable(
                            id="table-previsao",
                            columns=[],
                            data=[],
                            page_size=20,
                            sort_action="native",
                            filter_action="none",
                            style_table={"overflowX": "auto"},
                            style_cell={"textAlign": "left", "minWidth": "100px"},
                        )
                    ),
                ],
                className="shadow-sm mb-4"
            )
        ], width=12)
    ])


def register_callbacks_previsoes(app):
    @app.callback(
        Output("store-previsao-data", "data"),
        Output("table-previsao", "columns"),
        Input("btn-load-pred", "n_clicks"),
    )
    def load_all_predictions(n_clicks):
        if not n_clicks:
            return no_update, no_update

        # 1) Busca última data_calculo
        conn = get_connection()
        df_date = pd.read_sql_query(
            "SELECT MAX(data_calculo) AS ultima_data FROM resultados_precos",
            conn
        )
        ultima_calc = pd.to_datetime(df_date["ultima_data"].iloc[0]).date()
        conn.close()

        # 2) Define intervalo 1..10 dias após a última data_calculo
        start = ultima_calc + timedelta(days=1)
        end   = ultima_calc + timedelta(days=10)

        # 3) Consulta todas as previsões nesse intervalo
        query = """
            SELECT
                acao,
                data_previsao   AS data,
                preco_previsto AS predito
            FROM resultados_precos
            WHERE data_previsao BETWEEN %s AND %s
            ORDER BY data_previsao, acao
        """
        conn = get_connection()
        df = pd.read_sql_query(query, conn, params=[start, end])
        conn.close()

        # 4) Define as colunas fixas da DataTable
        columns = [
            {"name": "Ação",           "id": "acao"},
            {"name": "Data Previsão",  "id": "data",    "type": "datetime"},
            {"name": "Preço Previsto", "id": "predito","type": "numeric", "format": {"specifier": ".2f"}},
        ]
        data = df.to_dict("records")

        return data, columns

    @app.callback(
        Output("filter-previsao", "options"),
        Output("filter-previsao", "value"),
        Input("store-previsao-data", "data"),
    )
    def update_date_filter_options(stored):
        if not stored:
            return [], None
        df = pd.DataFrame(stored)
        dates = sorted(df["data"].unique())
        opts = [{"label": d, "value": d} for d in dates]
        return opts, None

    @app.callback(
        Output("filter-acao", "options"),
        Input("store-previsao-data", "data"),
    )
    def update_action_filter_options(stored):
        if not stored:
            return []
        df = pd.DataFrame(stored)
        acs = sorted(df["acao"].unique())
        opts = [{"label": a, "value": a} for a in acs]
        return opts

    @app.callback(
        Output("table-previsao", "data"),
        Input("store-previsao-data", "data"),
        Input("filter-previsao", "value"),
        Input("filter-acao", "value"),
    )
    def filter_predictions(stored, date_pref, acoes_sel):
        if not stored:
            return no_update
        df = pd.DataFrame(stored)
        if date_pref:
            df = df[df["data"] == date_pref]
        if acoes_sel:
            df = df[df["acao"].isin(acoes_sel)]
        return df.to_dict("records")
