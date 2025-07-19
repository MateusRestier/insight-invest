from dash import html, dcc, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import pandas as pd
from scraper_indicadores import coletar_indicadores

# ----------------------------------------------------------------------
# Layout da página "Indicadores"
# ----------------------------------------------------------------------

def layout_indicadores():
    return dbc.Container([
        html.H3("📊 Indicadores Fundamentalistas", className="mb-4"),
        html.Div([
            dcc.Input(
                id="input-ticker-ind",
                value="PETR4",
                type="text",
                placeholder="Digite o ticker",
                style={"width": "150px", "marginRight": "10px"}
            ),
            dbc.Button(
                "Carregar",
                id="btn-load-ind",
                className="btn-botaoacao"
            )
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "1rem"}),

        html.Hr(),

        dcc.Loading(
            id="loading-cards-indicadores",
            type="circle",
            children=dbc.Row(
                id="cards-indicadores",
                justify="start",
                className="g-3"
            )
        )
    ], fluid=True)


# ----------------------------------------------------------------------
# Callback da página
# ----------------------------------------------------------------------

def register_callbacks_indicadores(app):
    @app.callback(
        Output("cards-indicadores", "children"),
        Input("btn-load-ind", "n_clicks"),
        State("input-ticker-ind", "value")
    )
    def update_indicators(n_clicks, ticker):
        if not n_clicks or not ticker:
            return []

        resultado = coletar_indicadores(ticker)
        if isinstance(resultado, str):
            return dbc.Alert(resultado, color="danger", dismissable=True)

        dados, _ = resultado

        display_names = {
            'acao': 'Ação',
            'pl': 'P/L',
            'psr': 'P/Receita (PSR)',
            'pvp': 'P/VP',
            'dividend_yield': 'Dividend Yield',
            'payout': 'Payout',
            'margem_liquida': 'Margem Líquida',
            'margem_bruta': 'Margem Bruta',
            'margem_ebit': 'Margem EBIT',
            'margem_ebitda': 'Margem EBITDA',
            'ev_ebitda': 'EV/EBITDA',
            'ev_ebit': 'EV/EBIT',
            'p_ebitda': 'P/EBITDA',
            'p_ebit': 'P/EBIT',
            'p_ativo': 'P/Ativo',
            'p_cap_giro': 'P/Cap.Giro',
            'p_ativo_circ_liq': 'P/Ativo Circ.Liq',
            'vpa': 'VPA',
            'lpa': 'LPA',
            'giro_ativos': 'Giro Ativos',
            'roe': 'ROE',
            'roic': 'ROIC',
            'roa': 'ROA',
            'div_liq_patrimonio': 'Dív. Líq./Patrimônio',
            'div_liq_ebitda': 'Dív. Líq./EBITDA',
            'div_liq_ebit': 'Dív. Líq./EBIT',
            'div_bruta_patrimonio': 'Dív. Bruta/Patrimônio',
            'patrimonio_ativos': 'Patrimônio/Ativos',
            'passivos_ativos': 'Passivos/Ativos',
            'liquidez_corrente': 'Liquidez Corrente',
            'cotacao': 'Cotação (R$)',
            'variacao_12m': 'Variação 12M'
        }

        cards = []
        for nome, valor in dados.items():
            label = display_names.get(nome, nome.replace('_', ' ').title())

            if valor is None:
                display_val = "–"
            elif isinstance(valor, (int, float)):
                if nome in ['dividend_yield', 'payout', 'margem_liquida', 'margem_bruta',
                            'margem_ebit', 'margem_ebitda', 'roe', 'roic', 'roa', 'variacao_12m']:
                    display_val = f"{valor:.2f}%"
                else:
                    display_val = f"{valor:.2f}"
            else:
                display_val = str(valor)

            cards.append(
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody([
                            html.H6(label, className="card-title", style={"fontSize": "0.9rem"}),
                            html.H5(display_val, className="card-text", style={
                                "fontSize": "1.25rem", "minHeight": "2rem"
                            })
                        ]),
                        className="h-100 shadow-sm"
                    ),
                    xs=12, sm=6, md=4, lg=3, xl=2,
                    className="mb-4"
                )
            )
        return cards
