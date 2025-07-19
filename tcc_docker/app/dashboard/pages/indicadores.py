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
            html.H3("📊 Indicadores Fundamentalistas", className="mb-4"),

            # ----------------------- DROPDOWN + GRÁFICO ----------------------
            dbc.Row(
                [
                    dbc.Col(
                        dcc.Dropdown(
                            id="metric-picker",
                            value="graham",
                            clearable=False,
                            options=[
                                {
                                    "label": "Top 10 ações com maior desconto segundo Graham "
                                             "(PL e ROE positivos)",
                                    "value": "graham",
                                },
                                {
                                    "label": "Top 10 ações com maior Dividend Yield "
                                             "(PL e ROE positivos)",
                                    "value": "dividend_yield",
                                },
                                {
                                    "label": "Top 10 ações com maior ROE "
                                             "(PL e LPA positivos)",
                                    "value": "roe",
                                },
                                {
                                    "label": "Top 10 ações com cotação mais alta",
                                    "value": "cotacao",
                                },
                                {
                                    "label": "Top 10 ações com maior Margem Líquida (%)",
                                    "value": "margem_liquida",
                                },
                                {
                                    "label": "Top 10 ações com menor Dívida Líq./Patrimônio",
                                    "value": "div_liq_patrimonio",
                                },
                            ],
                            className="mb-3",
                        ),
                        md=8,
                    )
                ]
            ),
            dbc.Row(
                [
                    dbc.Col(dcc.Graph(id="grafico-top-metric"), md=8),
                ]
            ),

            html.Hr(className="mt-4 mb-4"),

            # --------------------- SUBTÍTULO + INPUT ---------------------------
            dbc.Row(
                dbc.Col(
                    html.H5("🪄 Escolha um ticker para ver detalhes:", className="mb-2"),
                    md=12,
                )
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
    # ------------------------------------------------------------------ #
    # 1. Cards detalhados de um ticker ----------------------------------
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

        dados, _ = resultado

        display_names = {
            "acao": "Ação",
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

    # ------------------------------------------------------------------ #
    # 2. Gráfico dinâmico (dropdown) ------------------------------------
    @app.callback(
        Output("grafico-top-metric", "figure"),
        Input("metric-picker", "value"),
    )
    def plotar_top_10(metrico):
        try:
            conn = get_connection()

            if metrico == "graham":
                query = """
                    SELECT acao, lpa, vpa, cotacao, pl, roe
                    FROM indicadores_fundamentalistas
                    WHERE data_coleta = (SELECT MAX(data_coleta)
                                         FROM indicadores_fundamentalistas)
                      AND lpa > 0 AND vpa > 0 AND cotacao > 0
                      AND pl >= 0 AND roe >= 0;
                """
                df = pd.read_sql(query, conn)
                conn.close()

                df[["lpa", "vpa", "cotacao"]] = df[["lpa", "vpa", "cotacao"]].apply(
                    pd.to_numeric, errors="coerce"
                )
                df = df.dropna(subset=["lpa", "vpa", "cotacao"])
                df["valor_graham"] = np.sqrt(22.5 * df["lpa"] * df["vpa"])
                df["metrica"] = df["valor_graham"] - df["cotacao"]
                df = df[df["metrica"] > 0].sort_values("metrica", ascending=False).head(10)
                label_y = "Desconto vs. Valor Graham"
                ascending = False

            else:
                coluna = metrico
                extra_filters = ""
                if metrico == "dividend_yield":
                    extra_filters = "AND pl >= 0 AND roe >= 0"
                if metrico == "roe":
                    extra_filters = "AND pl >= 0 AND lpa > 0"

                query = f"""
                    SELECT acao, {coluna} AS metrica
                    FROM indicadores_fundamentalistas
                    WHERE data_coleta = (SELECT MAX(data_coleta)
                                         FROM indicadores_fundamentalistas)
                      AND {coluna} IS NOT NULL
                      {extra_filters}
                """
                df = pd.read_sql(query, conn)
                conn.close()

                df["metrica"] = pd.to_numeric(df["metrica"], errors="coerce")
                df = df.dropna(subset=["metrica"])

                if metrico == "div_liq_patrimonio":
                    ascending = True  # queremos as MENORES dívidas
                else:
                    ascending = False

                df = df.sort_values("metrica", ascending=ascending).head(10)

                # rótulo do eixo x
                mapping = {
                    "dividend_yield": "Dividend Yield (%)",
                    "roe": "ROE (%)",
                    "cotacao": "Cotação (R$)",
                    "margem_liquida": "Margem Líquida (%)",
                    "div_liq_patrimonio": "Dív. Líq./Patrimônio",
                }
                label_y = mapping.get(metrico, coluna)

            if df.empty:
                return px.bar(title="Sem dados para este ranking no momento")

            fig = px.bar(
                df if metrico != "div_liq_patrimonio" else df.iloc[::-1],  # invertido p/ barra h
                x="metrica",
                y="acao",
                orientation="h",
                text="metrica",
                labels={"metrica": label_y, "acao": "Ação"},
            )
            fmt = ".2f" if metrico not in {"dividend_yield", "roe", "margem_liquida"} else ".2f"
            if metrico in {"dividend_yield", "roe", "margem_liquida"}:
                fmt = ".2f"  # mostra %
            fig.update_traces(texttemplate=f"%{{text:{fmt}}}", textposition="outside")
            fig.update_layout(
                margin=dict(l=24, r=24, t=40, b=24),
                yaxis=dict(autorange="reversed"),
                plot_bgcolor="#1e1e2f",
                paper_bgcolor="#1e1e2f",
                font=dict(color="#e0e0e0"),
            )
            return fig
        except Exception as e:
            return px.bar(title=f"Erro ao gerar gráfico: {e}")
