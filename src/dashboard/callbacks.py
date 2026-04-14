from dash import Input, Output
from src.dashboard.pages.indicadores  import layout_indicadores,  register_callbacks_indicadores
from src.dashboard.pages.previsoes    import layout_previsoes,    register_callbacks_previsoes
from src.dashboard.pages.recomendador import layout_recomendador, register_callbacks_recomendador


def register_callbacks(app):
    # Routing por pathname — dcc.Location gerencia URL e dbc.NavLink gerencia active state
    @app.callback(
        Output("tab-content", "children"),
        Input("url", "pathname"),
    )
    def render_page(pathname):
        if pathname in (None, "/", "/indicadores"):
            return layout_indicadores()
        if pathname == "/previsoes":
            return layout_previsoes()
        if pathname == "/recomendador":
            return layout_recomendador()
        return layout_indicadores()

    # -------------------------------------------------------------------------
    # Callbacks de cada página
    # -------------------------------------------------------------------------
    register_callbacks_indicadores(app)
    register_callbacks_previsoes(app)
    register_callbacks_recomendador(app)
