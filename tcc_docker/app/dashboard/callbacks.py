import dash
from dash import Input, Output, no_update, html
from dashboard.pages.indicadores import layout_indicadores, register_callbacks_indicadores
from dashboard.pages.previsoes   import layout_previsoes,   register_callbacks_previsoes
from dashboard.pages.recomendador import layout_recomendador, register_callbacks_recomendador

def register_callbacks(app):
    # Callback de troca de aba: injeta o layout certo em #tab-content
    @app.callback(
        Output("tab-content", "children"),
        Output("tab-indicadores-link", "className"),
        Output("tab-regressor-link", "className"),
        Output("tab-recomendador-link", "className"),
        Input("tab-indicadores-link", "n_clicks"),
        Input("tab-regressor-link", "n_clicks"),
        Input("tab-recomendador-link", "n_clicks"),
    )
    def render_tab(indicadores_click, regressor_click, recomendador_click):
        ctx = dash.callback_context

        if not ctx.triggered:
            # Se nenhum clique ocorreu, a aba "Indicadores" é a padrão
            return layout_indicadores(), "nav-link active", "nav-link", "nav-link"

        triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
        
        if triggered_id == "tab-indicadores-link":
            return layout_indicadores(), "nav-link active", "nav-link", "nav-link"
        elif triggered_id == "tab-regressor-link":
            return layout_previsoes(), "nav-link", "nav-link active", "nav-link"
        elif triggered_id == "tab-recomendador-link":
            return layout_recomendador(), "nav-link", "nav-link", "nav-link active"

        return no_update, "nav-link", "nav-link", "nav-link"

    # -----------------------------------------------------------------------------  
    # Registra callbacks de cada página
    # -----------------------------------------------------------------------------  
    register_callbacks_indicadores(app)
    register_callbacks_previsoes(app)
    register_callbacks_recomendador(app)
