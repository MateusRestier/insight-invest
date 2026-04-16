from dash import Input, Output
from src.dashboard.pages.indicadores  import register_callbacks_indicadores
from src.dashboard.pages.previsoes    import register_callbacks_previsoes
from src.dashboard.pages.recomendador import register_callbacks_recomendador


def register_callbacks(app):
    # -------------------------------------------------------------------------
    # Active state da navbar baseado no hash da URL
    # Roda no cliente — zero round-trip ao servidor
    # -------------------------------------------------------------------------
    app.clientside_callback(
        """
        function(hash) {
            var isInd  = !hash || hash === '#section-indicadores';
            var isPrev = hash === '#section-previsoes';
            var isRec  = hash === '#section-recomendador';
            return [isInd, isPrev, isRec];
        }
        """,
        Output("nav-indicadores",  "active"),
        Output("nav-previsoes",    "active"),
        Output("nav-recomendador", "active"),
        Input("url", "hash"),
    )

    # -------------------------------------------------------------------------
    # Callbacks de cada seção
    # -------------------------------------------------------------------------
    register_callbacks_indicadores(app)
    register_callbacks_previsoes(app)
    register_callbacks_recomendador(app)
