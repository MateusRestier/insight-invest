import os
import sys

# Garante que "tcc_docker/app" esteja no path para importações internas
ROOT = os.path.abspath(os.path.join(__file__, os.pardir, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import dash
import dash_bootstrap_components as dbc
from dash import html, dcc
from dashboard.callbacks import register_callbacks

# -----------------------------------------------------------------------------
# Configuração da aplicação Dash
# -----------------------------------------------------------------------------
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.LITERA],  # tema mais leve e elegante
    suppress_callback_exceptions=True,
)
server = app.server  # Expondo servidor para WSGI

# -----------------------------------------------------------------------------
# Layout principal
# -----------------------------------------------------------------------------
app.layout = dbc.Container(
    [

    dbc.NavbarSimple(
        brand="TCC: Sistema de Análise e Recomendação de Ações",
        color="primary",
        dark=True,
        children=[
        dbc.Nav(
            [
                dbc.NavItem(dbc.NavLink("Indicadores", href="#tab-indicadores", id="tab-indicadores-link", className="nav-link")),
                dbc.NavItem(dbc.NavLink("Previsões de Preço", href="#tab-regressor", id="tab-regressor-link", className="nav-link")),
                dbc.NavItem(dbc.NavLink("Recomendações", href="#tab-recomendador", id="tab-recomendador-link", className="nav-link")),
            ],
            pills=True,
            className="ml-auto",  # Garante que as abas fiquem à direita no menu hamburguer
        )
        ],
        fluid=True,
        className="navbar-expand-lg",  # Responsividade
        id="navbar",
        brand_href="#",
        expand="lg",  # Transição para hambúrguer em telas pequenas
        style={
            "backgroundColor": "#2c2c3e",  # Ajuste a cor de fundo
            "width": "100%",  # Faz com que o fundo se estenda por toda a largura
            "marginLeft": "0",  # Remove margem à esquerda
            "marginRight": "0",  # Remove margem à direita
        },
    ),

        # Conteúdo das abas será injetado aqui
        html.Div(id="tab-content", className="p-4"),
    ],
    fluid=True,
)

# -----------------------------------------------------------------------------
# Registra callbacks importados de dashboard/callbacks.py
# -----------------------------------------------------------------------------
register_callbacks(app)

# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
