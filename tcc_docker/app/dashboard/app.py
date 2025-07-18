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
    external_stylesheets=[dbc.themes.BOOTSTRAP],
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
        ),
        
        # Abas de navegação
        dbc.Tabs(
            [
                dbc.Tab(label="Indicadores",       tab_id="tab-indicadores"),
                dbc.Tab(label="Previsões de Preço", tab_id="tab-regressor"),
                dbc.Tab(label="Recomendações",      tab_id="tab-recomendador"),
            ],
            id="tabs",
            active_tab="tab-indicadores",
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
