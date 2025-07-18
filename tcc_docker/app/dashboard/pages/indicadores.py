from dash import html, dcc, dash_table, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import pandas as pd
from scraper_indicadores import coletar_indicadores

# -----------------------------------------------------------------------------
# Layout e callbacks para a página "Indicadores"
# -----------------------------------------------------------------------------

def layout_indicadores():
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


def register_callbacks_indicadores(app):
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
