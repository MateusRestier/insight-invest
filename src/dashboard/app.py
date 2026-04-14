import os
import sys

# Adiciona a raiz do projeto ao sys.path para imports absolutos
ROOT = os.path.abspath(os.path.join(__file__, os.pardir, os.pardir, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import dash
import dash_bootstrap_components as dbc
from dash import html, dcc
from src.dashboard.callbacks import register_callbacks

# -----------------------------------------------------------------------------
# Configuração da aplicação Dash
# -----------------------------------------------------------------------------
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    suppress_callback_exceptions=True,
    title="Insight Invest",
)
server = app.server  # Expondo servidor para WSGI

# -----------------------------------------------------------------------------
# Layout principal
# -----------------------------------------------------------------------------
app.layout = dbc.Container(
    [
        dcc.Location(id="url", refresh=False),

        dbc.NavbarSimple(
            brand="Insight Invest",
            brand_href="/",
            color="dark",
            dark=True,
            children=[
                dbc.Nav(
                    [
                        dbc.NavLink("Indicadores",        href="/",             active="exact",   className="px-3"),
                        dbc.NavLink("Previsões de Preço", href="/previsoes",    active="exact",   className="px-3"),
                        dbc.NavLink("Recomendações",      href="/recomendador", active="exact",   className="px-3"),
                    ],
                    pills=True,
                    className="ms-auto gap-1",
                ),
            ],
            fluid=True,
            expand="lg",
            id="navbar",
            style={"backgroundColor": "#2c2c3e", "padding": "0.5rem 1rem"},
        ),

        # Conteúdo das páginas é injetado aqui
        html.Div(id="tab-content", className="p-4"),
    ],
    fluid=True,
    className="p-0",
)

# -----------------------------------------------------------------------------
# Registra callbacks
# -----------------------------------------------------------------------------
register_callbacks(app)

# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8050)), debug=False)
