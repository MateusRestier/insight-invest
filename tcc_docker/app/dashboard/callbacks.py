from dash import Input, Output, State, html, dcc
import dash_bootstrap_components as dbc
import dash
import pandas as pd
import joblib
from app.scraper_indicadores import coletar_indicadores
from recomendador_acoes import recomendar_acao
from regressor_preco import executar_pipeline_regressor
import plotly.express as px
from db_connection import get_connection

def register_callbacks(app: dash.Dash):

    @app.callback(
        Output("tab-content", "children"),
        Input("tabs", "active_tab")
    )
    def render_tab(tab):
        if tab == "tab-indicadores":
            return dbc.Row([
                dbc.Col([
                    html.H5("Selecione um ticker:"),
                    dcc.Input(id="input-ticker-ind", value="PETR4", type="text"),
                    dbc.Button("Carregar", id="btn-load-ind", color="primary", className="mt-2"),
                    dcc.Graph(id="graf-indicadores")
                ])
            ])
        if tab == "tab-regressor":
            return dbc.Row([
                dbc.Col([
                    html.H5("Previsão de Preço - 10 dias à frente"),
                    dcc.Dropdown(id="dropdown-data-calculo", options=_load_datas_calculo(), value=None),
                    dbc.Button("Prever", id="btn-predict-price", color="success", className="mt-2"),
                    dcc.Graph(id="graf-previsao")
                ])
            ])
        if tab == "tab-recomendador":
            return dbc.Row([
                dbc.Col([
                    html.H5("Recomendador de Ações"),
                    dcc.Input(id="input-ticker-rec", value="ITUB4", type="text"),
                    dbc.Button("Recomendar", id="btn-recommend", color="warning", className="mt-2"),
                    html.Div(id="recomendation-output", className="mt-3")
                ])
            ])

    # Callbacks individuais…

    @app.callback(
        Output("graf-indicadores", "figure"),
        Input("btn-load-ind", "n_clicks"),
        State("input-ticker-ind", "value")
    )
    def update_indicators(n, ticker):
        if not n: return dash.no_update
        dados, _ = coletar_indicadores(ticker)
        df = pd.DataFrame([dados])
        fig = px.bar(df.melt(id_vars=["acao"]), x="variable", y="value",
                     title=f"Indicadores de {ticker.upper()}")
        return fig

    @app.callback(
        Output("graf-previsao", "figure"),
        Input("btn-predict-price", "n_clicks"),
        State("dropdown-data-calculo", "value")
    )
    def update_regressor(n, data_calculo):
        if not n: return dash.no_update
        # executa pipeline para uma data e retorna comp DataFrame
        _, comp = executar_pipeline_regressor(n_dias=10, data_calculo=data_calculo)
        fig = px.scatter(comp, x="preco_real", y="predito", color="acao",
                         title=f"Preço Previsto vs Real ({data_calculo})",
                         labels={"predito":"Previsto","preco_real":"Real"})
        fig.add_shape(type="line", x0=comp.preco_real.min(), y0=comp.preco_real.min(),
                      x1=comp.preco_real.max(), y1=comp.preco_real.max(),
                      line=dict(dash="dash"))
        return fig

    @app.callback(
        Output("recomendation-output", "children"),
        Input("btn-recommend", "n_clicks"),
        State("input-ticker-rec", "value")
    )
    def update_recommend(n, ticker):
        if not n: return dash.no_update
        # Captura a saída do recomendador como texto
        from io import StringIO
        import sys
        buffer = StringIO()
        sys_stdout = sys.stdout
        sys.stdout = buffer
        recomendar_acao(ticker)
        sys.stdout = sys_stdout
        return dbc.Card(dbc.CardBody(html.Pre(buffer.getvalue())))
