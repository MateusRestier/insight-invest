from dash import html, dcc, Input, Output, State, no_update
import dash_bootstrap_components as dbc
from scraper_indicadores import coletar_indicadores
from recomendador_acoes import recomendar_acao

# -----------------------------------------------------------------------------
# Layout e callbacks para a página "Recomendador de Ações"
# -----------------------------------------------------------------------------

def layout_recomendador():
    return dbc.Row([
        # Coluna da Esquerda: Card de Recomendação
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("📝 Recomendador de Ações"),
                # Aplicando Flexbox diretamente no CardBody
                dbc.CardBody([
                    # Div para os controles (Input e Botão)
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
                            className="btn-botaoacao"
                        )
                    ], className="mb-3"),

                    # Div que vai crescer e centralizar o conteúdo (spinner/resultado)
                    html.Div(
                        dcc.Loading(
                            id="loading-recommendation",
                            type="circle",
                            children=[
                                # Adicionando estilos para controlar o texto de saída
                                html.Pre(
                                    id="recomendation-output",
                                    style={
                                        'whiteSpace': 'pre-wrap',       # Permite a quebra de linha
                                        'wordBreak': 'break-word',      # Força a quebra de texto
                                        'textAlign': 'left',            # Alinha o texto do terminal à esquerda
                                        'width': '100%',                # Garante que o <pre> ocupe a largura toda
                                        'backgroundColor': '#2c2c3e',   # Fundo sutil para o texto
                                        'padding': '10px',              # Espaçamento interno
                                        'borderRadius': '5px'           # Bordas arredondadas
                                    }
                                )
                            ]
                        ),
                        # Classes para fazer a div crescer e centralizar seu conteúdo
                        className="flex-grow-1 d-flex justify-content-center align-items-center"
                    )
                ], className="d-flex flex-column") # Classe para tornar o body um container flex vertical
            ], className="shadow-sm mb-4 h-100"),
        ], md=5),

        # Coluna da Direita: Indicadores da Ação
        dbc.Col([
            html.H5("🪄 Indicadores da Ação Selecionada:", className="mb-2"),
            html.Div(
                dcc.Loading(
                    id="loading-cards-rec",
                    type="circle",
                    children=dbc.Row(
                        id="cards-indicadores-rec",
                        justify="start",
                        className="g-3 mb-4",
                    )
                ),
                className="flex-grow-1 d-flex justify-content-center align-items-center",
                style={"marginTop": "2.5rem"}  # Ajuste aqui para descer o spinner
            )
        ], md=7),
    ], className="align-items-stretch") # Garante que as colunas tenham a mesma altura


# A função register_callbacks_recomendador continua a mesma
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
            "acao": "Ação", "pl": "P/L", "psr": "P/SR", "pvp": "P/VP", "dy": "Dividend Yield",
            "payout": "Payout", "margem_liquida": "Margem Líquida", "margem_bruta": "Margem Bruta",
            "margem_ebit": "Margem EBIT", "margem_ebitda": "Margem EBITDA", "valor_firma_ebit": "EV/EBIT",
            "valor_firma_ebitda": "EV/EBITDA", "lpa": "LPA", "vpa": "VPA", "giro_ativos": "Giro Ativos",
            "roe": "ROE", "roic": "ROIC", "roa": "ROA", "div_liq_patrimonio": "Dív. Líq./Patrimônio",
            "div_liq_ebitda": "Dív. Líq./EBITDA", "div_liq_ebit": "Dív. Líq./EBIT",
            "div_bruta_patrimonio": "Dív. Bruta/Patrimônio", "patrimonio_ativos": "Patrimônio/Ativos",
            "passivos_ativos": "Passivos/Ativos", "liquidez_corrente": "Liquidez Corrente",
            "cotacao": "Cotação (R$)", "variacao_12m": "Variação 12 M",
        }

        percent_keys = {
            "dy", "payout", "margem_liquida", "margem_bruta", "margem_ebit",
            "margem_ebitda", "roe", "roic", "roa", "variacao_12m",
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
                                    "fontSize": "1.25rem", "minHeight": "2rem", "textAlign": "center",
                                },
                            ),
                        ]),
                        className="h-100 shadow-sm",
                    ),
                    xs=12, sm=6, md=4, lg=4, xl=3,
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