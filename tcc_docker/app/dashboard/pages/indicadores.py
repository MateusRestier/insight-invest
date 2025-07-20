from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import numpy as np
from dash import dash_table

from db_connection import get_connection


# ----------------------------------------------------------------------
# Layout da página "Indicadores"
# ----------------------------------------------------------------------
def layout_indicadores():
    return dbc.Container(
        [
            html.H3("📊 Indicadores Fundamentalistas", className="mb-4"),

            # ----------------------- SELECT + GRÁFICO ----------------------
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Select(
                            id="metric-picker",
                            value="graham",
                            options=[
                                {"label": "Top 10 ações com maior desconto segundo Graham (PL e ROE positivos)", "value": "graham"},
                                {"label": "Top 10 ações com maior Dividend Yield (PL e ROE positivos)", "value": "dividend_yield"},
                                {"label": "Top 10 ações com maior ROE (PL e LPA positivos)", "value": "roe"},
                                {"label": "Top 10 ações com cotação mais alta", "value": "cotacao"},
                                {"label": "Top 10 ações com maior Margem Líquida (%)", "value": "margem_liquida"},
                                {"label": "Top 10 ações com menor Dívida Líq./Patrimônio", "value": "div_liq_patrimonio"},
                            ],
                            className="mb-3 dropdown-dark",
                            style={
                                "color": "#e0e0e0",
                                "backgroundColor": "#1e1e2f",
                                "borderColor": "#444"
                            }
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

            # ----------------------- TABELA DE PREVISÃO VS REAL ----------------------
            dbc.Row(
                [
                    dbc.Col(html.H5("📈 Comparação Preço Previsto x Real", className="mt-5 mb-2"), width=12)
                ]
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dash_table.DataTable(
                            id="table-previsto-real",
                            page_size=10,
                            style_table={"overflowX": "auto"},
                            style_header={
                                "backgroundColor": "#333",
                                "color": "#e0e0e0",
                                "fontWeight": "bold"
                            },
                            style_cell={
                                "backgroundColor": "#1e1e2f",
                                "color": "#e0e0e0",
                                "textAlign": "center",
                                "padding": "5px"
                            },
                            style_data_conditional=[
                                {
                                    "if": {"state": "selected"},
                                    "backgroundColor": "#5561ff",
                                    "color": "#ffffff"
                                }
                            ],
                        ),
                        width=12
                    )
                ]
            ),
        ],
        fluid=True,
        style={"padding": "0 1rem"},
    )


# ----------------------------------------------------------------------
# Callbacks da página "Indicadores"
# ----------------------------------------------------------------------
def register_callbacks_indicadores(app):
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
                    WHERE data_coleta = (
                        SELECT MAX(data_coleta) FROM indicadores_fundamentalistas
                    )
                      AND lpa > 0 AND vpa > 0 AND cotacao > 0
                      AND pl >= 0 AND roe >= 0;
                """
                df = pd.read_sql(query, conn)
                df[ ["lpa","vpa","cotacao"] ] = df[["lpa","vpa","cotacao"]].apply(pd.to_numeric, errors="coerce")
                df = df.dropna(subset=["lpa","vpa","cotacao"])
                df["valor_graham"] = np.sqrt(22.5 * df["lpa"] * df["vpa"])
                df["metrica"] = df["valor_graham"] - df["cotacao"]
                df = df[df["metrica"]>0].sort_values("metrica", ascending=False).head(10)
            else:
                coluna = metrico
                extra = ""
                if metrico=="dividend_yield": extra = "AND pl>=0 AND roe>=0"
                if metrico=="roe": extra = "AND pl>=0 AND lpa>0"
                query = f"""
                    SELECT acao, {coluna} AS metrica
                    FROM indicadores_fundamentalistas
                    WHERE data_coleta = (
                        SELECT MAX(data_coleta) FROM indicadores_fundamentalistas
                    ) AND {coluna} IS NOT NULL {extra}
                """
                df = pd.read_sql(query, conn)
                df["metrica"] = pd.to_numeric(df["metrica"], errors="coerce")
                df = df.dropna(subset=["metrica"])
                if metrico=="div_liq_patrimonio":
                    tmp = df.sort_values("metrica",ascending=True).head(10)
                    df = tmp.sort_values("metrica",ascending=False)
                else:
                    df = df.sort_values("metrica",ascending=False).head(10)

            conn.close()
            if df.empty:
                return px.bar(title="Sem dados para este ranking no momento")

            labels={
                "graham":"Desconto vs. Valor Graham","dividend_yield":"Dividend Yield (%)",
                "roe":"ROE (%)","cotacao":"Cotação (R$)","margem_liquida":"Margem Líquida (%)",
                "div_liq_patrimonio":"Dív. Líq./Patrimônio"
            }
            label_y = labels.get(metrico, metrico)

            fig = px.bar(
                df, x="acao", y="metrica", text="metrica",
                labels={"acao":"Ação","metrica":label_y},
                category_orders={"acao":df["acao"].tolist()}
            )
            fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
            fig.update_layout(
                margin=dict(l=24,r=24,t=40,b=24),
                plot_bgcolor="#1e1e2f",paper_bgcolor="#1e1e2f",
                font=dict(color="#e0e0e0")
            )
            return fig
        except Exception as e:
            return px.bar(title=f"Erro ao gerar gráfico: {e}")

    @app.callback(
        Output("table-previsto-real", "data"),
        Output("table-previsto-real", "columns"),
        Input("metric-picker", "value")  # atualiza sempre que o usuário troca métrica
    )
    def update_table(_):
        conn = get_connection()
        query = """
            SELECT
                r.acao,
                r.data_calculo,
                r.data_previsao,
                r.preco_previsto,
                i.cotacao AS preco_real,
                CASE
                    WHEN i.cotacao IS NOT NULL AND i.cotacao <> 0 THEN
                        ROUND((r.preco_previsto - i.cotacao) / i.cotacao * 100, 4)
                    ELSE NULL
                END AS erro_pct
            FROM resultados_precos r
            LEFT JOIN indicadores_fundamentalistas i
              ON r.acao = i.acao
             AND r.data_previsao = i.data_coleta
            ORDER BY r.data_calculo, r.acao;
        """
        df2 = pd.read_sql(query, conn)
        conn.close()
        data = df2.to_dict('records')
        columns = [
            {"name": col.replace("_", " ").title(), "id": col}
            for col in df2.columns
        ]
        return data, columns
