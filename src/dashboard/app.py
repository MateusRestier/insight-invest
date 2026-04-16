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
from src.dashboard.pages.indicadores  import layout_indicadores
from src.dashboard.pages.previsoes    import layout_previsoes
from src.dashboard.pages.recomendador import layout_recomendador

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
# Layout principal — single-page com scroll anchors
# -----------------------------------------------------------------------------
app.layout = dbc.Container(
    [
        # dcc.Location mantido apenas para rastrear hash (active state da navbar)
        dcc.Location(id="url", refresh=False),

        dbc.NavbarSimple(
            brand="Insight Invest",
            brand_href="#section-indicadores",
            color="dark",
            dark=True,
            children=[
                dbc.Nav(
                    [
                        dbc.NavLink(
                            "Indicadores",
                            href="#section-indicadores",
                            id="nav-indicadores",
                            external_link=True,
                            className="px-3",
                        ),
                        dbc.NavLink(
                            "Previsões de Preço",
                            href="#section-previsoes",
                            id="nav-previsoes",
                            external_link=True,
                            className="px-3",
                        ),
                        dbc.NavLink(
                            "Recomendações",
                            href="#section-recomendador",
                            id="nav-recomendador",
                            external_link=True,
                            className="px-3",
                        ),
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

        # Todas as seções renderizadas de uma vez, empilhadas verticalmente
        html.Div(className="p-4", children=[
            html.Div(id="section-indicadores", className="mb-4",
                     children=layout_indicadores()),
            html.Div(id="section-previsoes", className="mb-4",
                     children=layout_previsoes()),
            html.Div(id="section-recomendador", className="mb-4",
                     children=dbc.Container(layout_recomendador(), fluid=True)),
        ]),
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
