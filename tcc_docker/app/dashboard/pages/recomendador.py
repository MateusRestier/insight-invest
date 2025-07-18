from dash import html, dcc, Input, Output, State, no_update
import dash_bootstrap_components as dbc

from recomendador_acoes import recomendar_acao

# -----------------------------------------------------------------------------
# Layout e callbacks para a página "Recomendador de Ações"
# -----------------------------------------------------------------------------

def layout_recomendador():
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


def register_callbacks_recomendador(app):
    @app.callback(
        Output("recomendation-output", "children"),
        Input("btn-recommend", "n_clicks"),
        State("input-ticker-rec", "value")
    )
    def update_recommend(n_clicks, ticker):
        if not n_clicks:
            return no_update

        # Captura saída do recomendador no buffer
        from io import StringIO
        import sys
        buffer = StringIO()
        old_stdout = sys.stdout
        sys.stdout = buffer

        recomendar_acao(ticker)

        sys.stdout = old_stdout
        return buffer.getvalue()
