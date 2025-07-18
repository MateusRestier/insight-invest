# dashboard/callbacks.py

from dash import Input, Output, no_update, html
from dashboard.pages.indicadores import layout_indicadores, register_callbacks_indicadores
from dashboard.pages.previsoes   import layout_previsoes,   register_callbacks_previsoes
from dashboard.pages.recomendador import layout_recomendador, register_callbacks_recomendador

def register_callbacks(app):
    # -----------------------------------------------------------------------------
    # Callback de troca de aba: injeta o layout certo em #tab-content
    # -----------------------------------------------------------------------------
    @app.callback(
        Output("tab-content", "children"),
        Input("tabs", "active_tab")
    )
    def render_tab(active_tab):
        if active_tab == "tab-indicadores":
            return layout_indicadores()
        elif active_tab == "tab-regressor":
            return layout_previsoes()
        elif active_tab == "tab-recomendador":
            return layout_recomendador()
        else:
            return html.Div()  # fallback vazio

    # -----------------------------------------------------------------------------
    # Registra callbacks de cada página
    # -----------------------------------------------------------------------------
    register_callbacks_indicadores(app)
    register_callbacks_previsoes(app)
    register_callbacks_recomendador(app)
