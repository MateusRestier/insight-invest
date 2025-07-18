import sys, os
import dash
import dash_bootstrap_components as dbc
from dash import html, dcc
from app.dashboard.callbacks import register_callbacks

# caminho absoluto até tcc_docker/app
ROOT = os.path.abspath(os.path.join(__file__, os.pardir, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Use um tema Bootstrap, por ex. BOOTSTRAP ou CYBORG
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server  # para deploy em serviços como Heroku/Render

# Layout principal
app.layout = dbc.Container([
    dbc.NavbarSimple(
        brand="TCC: Sistema de Recomendação de Ações",
        color="primary", dark=True
    ),
    dbc.Tabs([
        dbc.Tab(label="Indicadores", tab_id="tab-indicadores"),
        dbc.Tab(label="Previsões de Preço", tab_id="tab-regressor"),
        dbc.Tab(label="Recomendações", tab_id="tab-recomendador"),
    ], id="tabs", active_tab="tab-indicadores"),
    html.Div(id="tab-content", className="p-4")
], fluid=True)

# Registra todos os callbacks
register_callbacks(app)

if __name__ == "__main__":
    app.run_server(debug=True)
