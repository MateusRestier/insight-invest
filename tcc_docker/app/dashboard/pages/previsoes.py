# dashboard/pages/previsoes.py

from dash import html, dcc, Input, Output, State, no_update, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import timedelta
from db_connection import get_connection

# -----------------------------------------------------------------------------
# Layout e callbacks para a página "Previsões de Preço"
# -----------------------------------------------------------------------------

def layout_previsoes():
    return dbc.Container([
        # Card principal
        dbc.Card([
            dbc.CardHeader("🔮 Previsão de Preço — 10 dias à frente"),
            dbc.CardBody([
                # Botão Carregar
                dbc.Button(
                    "Carregar",
                    id="btn-load-pred",
                    className="btn-botaoacao mb-3"
                ),

                # Exibição da última data de cálculo
                html.Div([
                    html.Strong("Data de Cálculo: "),
                    html.Span(id="ultima-data-calc")
                ], className="mb-3"),

                # Filtros em linha
                dbc.Row([
                    dbc.Col([
                        html.Label("Data Previsão:", className="form-label"),
                        dcc.Dropdown(
                            id="filter-previsao",
                            placeholder="Selecione…",
                            clearable=False
                        )
                    ], width="auto"),

                    dbc.Col([
                        html.Label("Ação:", className="form-label"),
                        dcc.Dropdown(
                            id="filter-acao",
                            multi=True,
                            placeholder="Todas"
                        )
                    ], width="auto"),
                ], className="g-3 mb-4"),

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
                        "fontWeight": "bold",
                    },
                    style_cell={
                        "backgroundColor": "#2a2a3d",
                        "color": "#e0e0e0",
                        "padding": "5px",
                        "minWidth": "100px",
                    },
                    style_data_conditional=[{
                        "if": {"row_index": "odd"},
                        "backgroundColor": "#252535"
                    }]
                )
            ])
        ], className="shadow-sm mb-4"),

        # Store para manter os dados em memória
        dcc.Store(id="store-previsao-data")
    ], fluid=True)


def register_callbacks_previsoes(app):

    # 1) Carrega do banco ao clicar em "Carregar"
    @app.callback(
        Output("store-previsao-data", "data"),
        Output("ultima-data-calc", "children"),
        Input("btn-load-pred", "n_clicks"),
    )
    def load_all_predictions(n_clicks):
        if not n_clicks:
            return no_update, no_update

        # Última data_calculo
        conn = get_connection()
        df_date = pd.read_sql_query(
            "SELECT MAX(data_calculo) AS ultima_data FROM resultados_precos",
            conn
        )
        ultima_calc = pd.to_datetime(df_date["ultima_data"].iloc[0]).date()

        # Intervalo de 1 a 10 dias depois
        start = ultima_calc + timedelta(days=1)
        end   = ultima_calc + timedelta(days=10)

        # Busca previsões para esse intervalo
        df = pd.read_sql_query(
            """
            SELECT acao,
                   data_previsao AS data,
                   preco_previsto AS predito
            FROM resultados_precos
            WHERE data_previsao BETWEEN %s AND %s
            ORDER BY data_previsao, acao
            """,
            conn,
            params=[start, end]
        )
        conn.close()

        # Retorna lista de dicts e exibe a data de cálculo
        return df.to_dict("records"), ultima_calc.strftime("%Y-%m-%d")


    # 2) Popula opções dos filtros assim que os dados chegam
    @app.callback(
        Output("filter-previsao", "options"),
        Output("filter-acao", "options"),
        Input("store-previsao-data", "data"),
    )
    def update_filters_options(stored):
        if not stored:
            return [], []

        df = pd.DataFrame(stored)
        prevs = sorted(df["data"].unique())
        prev_opts = [{"label": d, "value": d} for d in prevs]

        acoes = sorted(df["acao"].unique())
        acao_opts = [{"label": a, "value": a} for a in acoes]

        return prev_opts, acao_opts


    # 3) Renderiza a tabela aplicando filtros em memória
    @app.callback(
        Output("table-previsao", "columns"),
        Output("table-previsao", "data"),
        Input("store-previsao-data", "data"),
        Input("filter-previsao", "value"),
        Input("filter-acao", "value"),
    )
    def filter_predictions(stored, date_pref, acoes_sel):
        if not stored:
            return [], []

        df = pd.DataFrame(stored)

        # Aplica filtro de data_previsao
        if date_pref:
            df = df[df["data"] == date_pref]

        # Aplica filtro de ação
        if acoes_sel:
            df = df[df["acao"].isin(acoes_sel)]

        # Define colunas fixas
        columns = [
            {"name": "Ação",           "id": "acao"},
            {"name": "Data Previsão",  "id": "data",    "type": "datetime"},
            {"name": "Preço Previsto","id": "predito","type": "numeric","format":{"specifier":".2f"}},
        ]

        return columns, df.to_dict("records")
