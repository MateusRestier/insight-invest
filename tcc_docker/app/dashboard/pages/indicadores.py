from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import numpy as np

from scraper_indicadores import coletar_indicadores
from db_connection import get_connection


# ----------------------------------------------------------------------
# Layout da página "Indicadores"
# ----------------------------------------------------------------------
def layout_indicadores():
    return dbc.Container(
        [
            # ------------------------------------------------------------------
            html.H3("📊 Indicadores Fundamentalistas", className="mb-4"),

            # ------------------------- GRÁFICOS --------------------------------
            dbc.Row(
                [
                    dbc.Col(
                        html.H5(
                            "🔻 Top 10 ações com maior Dividend Yield "
                            "(PL e ROE positivos)",
                            className="mb-2",
                        ),
                        md=6,
                    ),
                    dbc.Col(
                        html.H5(
                            "🔻 Top 10 ações com maior desconto segundo Graham "
                            "(PL e ROE positivos)",
                            className="mb-2",
                        ),
                        md=6,
                    ),
                ]
            ),
            dbc.Row(
                [
                    dbc.Col(dcc.Graph(id="grafico-top-dy"), md=6),
                    dbc.Col(dcc.Graph(id="grafico-top-graham"), md=6),
                ]
            ),

            dbc.Row(
                [
                    dbc.Col(
                        html.H5(
                            "🔺 Top 10 ações com maior ROE (PL e LPA positivos)",
                            className="mt-4 mb-2",
                        ),
                        md=12,
                    ),
                    dbc.Col(dcc.Graph(id="grafico-top-roe"), md=6),
                ],
                className="mt-2",
            ),

            html.Hr(className="mt-4 mb-4"),

            # --------------------- SUBTÍTULO + INPUT ---------------------------
            dbc.Row(
                dbc.Col(
                    html.H5(
                        "✔ Escolha um ticker para ver detalhes:",
                        className="mb-2",
                    ),
                    md=12,
                ),
                className="mb-1",
            ),
            dbc.Row(
                dbc.Col(
                    dbc.InputGroup(
                        [
                            dbc.InputGroupText("Ticker"),
                            dbc.Input(
                                id="input-ticker-ind",
                                value="PETR4",
                                type="text",
                                placeholder="PETR4",
                                style={"width": "120px"},
                            ),
                            dbc.Button(
                                "Carregar",
                                id="btn-load-ind",
                                className="btn-botaoacao",
                                n_clicks=0,
                            ),
                        ],
                        className="w-100",
                    ),
                    md=6,
                ),
                className="g-2 mb-4",
            ),

            # ------------------------- CARDS -----------------------------------
            dcc.Loading(
                id="loading-cards-indicadores",
                type="circle",
                children=dbc.Row(
                    id="cards-indicadores",
                    justify="start",
                    className="g-3 mb-4",
                ),
            ),
        ],
        fluid=True,
        style={"padding": "0 1rem"},
    )


# ----------------------------------------------------------------------
# Callbacks
# ----------------------------------------------------------------------
def register_callbacks_indicadores(app):
    # 1. Cards com indicadores detalhados --------------------------------
    @app.callback(
        Output("cards-indicadores", "children"),
        Input("btn-load-ind", "n_clicks"),
        State("input-ticker-ind", "value"),
    )
    def update_indicators(n_clicks, ticker):
        if not n_clicks or not ticker:
            return []

        resultado = coletar_indicadores(ticker)
        if isinstance(resultado, str):
            return dbc.Alert(resultado, color="danger", dismissable=True)

        dados, _ = resultado  # dict

        display_names = {
            "pl": "P/L",
            "pvp": "P/VP",
            "psr": "P/SR",
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

        cards = []
        for nome, valor in dados.items():
            label = display_names.get(nome, nome.replace("_", " ").title())

            if valor is None:
                display_val = "–"
            elif isinstance(valor, (int, float)):
                if nome in {
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
                }:
                    display_val = f"{valor:.2f}%"
                else:
                    display_val = f"{valor:.2f}"
            else:
                display_val = str(valor)

            cards.append(
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
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
                            ]
                        ),
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

    # 2. Top-10 Dividend Yield ------------------------------------------
    @app.callback(Output("grafico-top-dy", "figure"), Input("grafico-top-dy", "id"))
    def plotar_top_10_dy(_):
        try:
            conn = get_connection()
            query = """
                SELECT acao, dividend_yield
                FROM indicadores_fundamentalistas
                WHERE data_coleta = (SELECT MAX(data_coleta) FROM indicadores_fundamentalistas)
                  AND dividend_yield IS NOT NULL
                  AND pl >= 0 AND roe >= 0
                ORDER BY dividend_yield DESC
                LIMIT 10;
            """
            df = pd.read_sql(query, conn)
            conn.close()

            # Proteção contra valores não numéricos / vazios
            df["dividend_yield"] = pd.to_numeric(df["dividend_yield"], errors="coerce")
            df = df.dropna(subset=["dividend_yield"])

            if df.empty:
                return px.bar(title="Sem dados de Dividend Yield no momento")

            fig = px.bar(
                df.sort_values("dividend_yield", ascending=False),
                x="acao",
                y="dividend_yield",
                text="dividend_yield",
                labels={"dividend_yield": "Dividend Yield (%)", "acao": "Ação"},
            )
            fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
            fig.update_layout(
                margin=dict(l=24, r=24, t=40, b=24),
                plot_bgcolor="#1e1e2f",
                paper_bgcolor="#1e1e2f",
                font=dict(color="#e0e0e0"),
            )
            return fig
        except Exception as e:
            return px.bar(title=f"Erro ao carregar gráfico: {e}")

    # 3. Top-10 ROE ------------------------------------------------------
    @app.callback(Output("grafico-top-roe", "figure"), Input("grafico-top-roe", "id"))
    def plotar_top_10_roe(_):
        try:
            conn = get_connection()
            query = """
                SELECT acao, roe
                FROM indicadores_fundamentalistas
                WHERE data_coleta = (SELECT MAX(data_coleta) FROM indicadores_fundamentalistas)
                  AND roe IS NOT NULL AND pl >= 0 AND lpa > 0
                ORDER BY roe DESC
                LIMIT 10;
            """
            df = pd.read_sql(query, conn)
            conn.close()

            df["roe"] = pd.to_numeric(df["roe"], errors="coerce")
            df = df.dropna(subset=["roe"])

            if df.empty:
                return px.bar(title="Sem dados de ROE no momento")

            fig = px.bar(
                df.sort_values("roe", ascending=False),
                x="acao",
                y="roe",
                text="roe",
                labels={"roe": "ROE (%)", "acao": "Ação"},
            )
            fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
            fig.update_layout(
                margin=dict(l=24, r=24, t=40, b=24),
                plot_bgcolor="#1e1e2f",
                paper_bgcolor="#1e1e2f",
                font=dict(color="#e0e0e0"),
            )
            return fig
        except Exception as e:
            return px.bar(title=f"Erro ao carregar gráfico: {e}")

    # 4. Top-10 desconto vs. Graham --------------------------------------
    @app.callback(Output("grafico-top-graham", "figure"), Input("grafico-top-graham", "id"))
    def plotar_valor_graham(_):
        try:
            conn = get_connection()
            query = """
                SELECT acao, lpa, vpa, cotacao, pl, roe
                FROM indicadores_fundamentalistas
                WHERE data_coleta = (SELECT MAX(data_coleta) FROM indicadores_fundamentalistas)
                  AND lpa > 0 AND vpa > 0 AND cotacao > 0
                  AND pl >= 0 AND roe >= 0
            """
            df = pd.read_sql(query, conn)
            conn.close()

            df[["lpa", "vpa", "cotacao"]] = df[["lpa", "vpa", "cotacao"]].apply(
                pd.to_numeric, errors="coerce"
            )
            df = df.dropna(subset=["lpa", "vpa", "cotacao"])

            if df.empty:
                return px.bar(title="Sem dados suficientes para Graham")

            df["valor_graham"] = np.sqrt(22.5 * df["lpa"] * df["vpa"])
            df["desconto"] = df["valor_graham"] - df["cotacao"]
            df = df[df["desconto"] > 0].sort_values("desconto", ascending=False).head(10)

            fig = px.bar(
                df,
                x="desconto",
                y="acao",
                orientation="h",
                text="desconto",
                labels={
                    "desconto": "Desconto vs. Valor Graham",
                    "acao": "Ação",
                },
            )
            fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
            fig.update_layout(
                margin=dict(l=24, r=24, t=40, b=24),
                yaxis=dict(autorange="reversed"),
                plot_bgcolor="#1e1e2f",
                paper_bgcolor="#1e1e2f",
                font=dict(color="#e0e0e0"),
            )
            return fig
        except Exception as e:
            return px.bar(title=f"Erro ao calcular Graham: {e}")
