from dash import html, dcc, Input, Output, State, no_update
import dash_bootstrap_components as dbc
from scraper_indicadores import coletar_indicadores
from recomendador_acoes import recomendar_acao

# -----------------------------------------------------------------------------
# Layout e callbacks para a página "Recomendador de Ações"
# -----------------------------------------------------------------------------

def layout_recomendador():
    return dbc.Row([
        dbc.Col([
            # Card de recomendação
            dbc.Card([
                dbc.CardHeader("📝 Recomendador de Ações"),
                dbc.CardBody([
                    html.Div([
                        dcc.Input(
                            id="input-ticker-rec",
                            value="ITUB4",
                            type="text",
                            placeholder="Ex: ITUB4",
                            style={"width": "150px", "margin-right": "10px"}
                        ),
                        dbc.Button(
                            "Recomendar",
                            id="btn-recommend",
                            color="warning"
                        )
                    ], className="mb-3"),
                    html.Pre(
                        id="recomendation-output",
                        style={"whiteSpace": "pre-wrap", "wordBreak": "break-all"}
                    )
                ])
            ], className="shadow-sm mb-4"),

            # Seção de Indicadores da Ação Selecionada
            html.H5("🪄 Indicadores da Ação Selecionada:", className="mb-2"),
            dcc.Loading(
                id="loading-cards-rec",
                type="circle",
                children=dbc.Row(
                    id="cards-indicadores-rec",
                    justify="start",
                    className="g-3 mb-4",
                )
            )
        ], width=12)
    ])


def register_callbacks_recomendador(app):
    @app.callback(
        Output("cards-indicadores-rec", "children"),
        Input("btn-recommend", "n_clicks"),
        State("input-ticker-rec", "value"),
    )
    def update_indicators(n_clicks, ticker):
        if not n_clicks or not ticker:
            return []

        resultado = coletar_indicadores(ticker)
        if isinstance(resultado, str):
            return dbc.Alert(resultado, color="danger", dismissable=True)

        dados, _ = resultado

        display_names = {
            "acao": "Ação",
            "pl": "P/L",
            "psr": "P/SR",
            "pvp": "P/VP",
            "dy": "Dividend Yield",
            "payout": "Payout",
            "margem_liquida": "Margem Líquida",
            "margem_bruta": "Margem Bruta",
            "margem_ebit": "Margem EBIT",
            "margem_ebitda": "Margem EBITDA",
            "valor_firma_ebit": "EV/EBIT",
            "valor_firma_ebitda": "EV/EBITDA",
            "lpa": "LPA",
            "vpa": "VPA",
            "giro_ativos": "Giro Ativos",
            "roe": "ROE",
            "roic": "ROIC",
            "roa": "ROA",
            "div_liq_patrimonio": "Dív. Líq./Patrimônio",
            "div_liq_ebitda": "Dív. Líq./EBITDA",
            "div_liq_ebit": "Dív. Líq./EBIT",
            "div_bruta_patrimonio": "Dív. Bruta/Patrimônio",
            "patrimonio_ativos": "Patrimônio/Ativos",
            "passivos_ativos": "Passivos/Ativos",
            "liquidez_corrente": "Liquidez Corrente",
            "cotacao": "Cotação (R$)",
            "variacao_12m": "Variação 12 M",
        }

        percent_keys = {
            "dy",
            "payout",
            "margem_liquida",
            "margem_bruta",
            "margem_ebit",
            "margem_ebitda",
            "roe",
            "roic",
            "roa",
            "variacao_12m",
        }

        cards = []
        for nome, valor in dados.items():
            label = display_names.get(nome, nome.replace("_", " ").title())

            if valor is None:
                display_val = "–"
            elif isinstance(valor, (int, float)):
                if nome in percent_keys:
                    display_val = f"{valor:.2f}%"
                else:
                    display_val = f"{valor:.2f}"
            else:
                display_val = str(valor)

            cards.append(
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody([
                            html.H6(
                                label,
                                className="card-title",
                                style={"fontSize": "0.9rem"},
                            ),
                            html.H5(
                                display_val,
                                className="card-text",
                                style={
                                    "fontSize": "1.25rem",
                                    "minHeight": "2rem",
                                    "textAlign": "center",
                                },
                            ),
                        ]),
                        className="h-100 shadow-sm",
                    ),
                    xs=12,
                    sm=6,
                    md=4,
                    lg=3,
                    xl=2,
                    className="mb-4",
                )
            )

        return cards

    @app.callback(
        Output("recomendation-output", "children"),
        Input("btn-recommend", "n_clicks"),
        State("input-ticker-rec", "value"),
    )
    def update_recommend(n_clicks, ticker):
        if not n_clicks:
            return no_update

        from io import StringIO
        import sys

        buffer = StringIO()
        old_stdout = sys.stdout
        sys.stdout = buffer

        recomendar_acao(ticker)

        sys.stdout = old_stdout
        return buffer.getvalue()
