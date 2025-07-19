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
# Inicialização da aplicação Dash com tema Litera
# -----------------------------------------------------------------------------
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.LITERA],  # tema mais clean e moderno
    suppress_callback_exceptions=True,
)
server = app.server  # Exposto para WSGI

# -----------------------------------------------------------------------------
# Layout principal com fundo cinza e padding
# -----------------------------------------------------------------------------
app.layout = html.Div(
    style={
        "backgroundColor": "#f8f9fa",  # cinza claro de fundo
        "minHeight": "100vh",          # preenche a altura da janela
        "paddingTop": "1rem"           # espaçamento superior
    },
    children=[
        dbc.Container(
            [
                dbc.NavbarSimple(
                    brand="TCC: Sistema de Análise e Recomendação de Ações",
                    color="primary",
                    dark=True,
                    className="mb-4"
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

                # Container para injetar o conteúdo de cada aba
                html.Div(id="tab-content", className="p-4"),
            ],
            fluid=True,
        )
    ]
)

# -----------------------------------------------------------------------------
# Registro de callbacks centralizados
# ----------------------------------------------------------------------------
register_callbacks(app)

# ----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
