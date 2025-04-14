import os
import requests
import psycopg2
from bs4 import BeautifulSoup
from datetime import date

# 1) Conexão com PostgreSQL
def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "stocks"),
        user=os.getenv("DB_USER", "user"),
        password=os.getenv("DB_PASS", "password"),
        port=os.getenv("DB_PORT", "5432")
    )

# 2) Extrai valor de indicador com nome aproximado
def get_valor_indicador(soup, nome_indicador):
    spans = soup.find_all('span')
    for span in spans:
        if nome_indicador.upper() in span.get_text(strip=True).upper():
            parent = span.find_parent('div', class_='cell')
            if parent:
                valor_span = parent.find('div', class_='value').find('span')
                if valor_span:
                    texto = valor_span.text.strip().replace('%', '').replace('.', '').replace(',', '.')
                    try:
                        return float(texto)
                    except ValueError:
                        return None
    return None

# 3) Cotação da ação
def get_cotacao(soup):
    try:
        card = soup.find("div", class_="_card cotacao")
        valor_span = card.find("span", class_="value")
        valor = valor_span.text.strip().replace("R$", "").replace(".", "").replace(",", ".")
        return float(valor)
    except Exception:
        return None

# 4) Variação dos últimos 12 meses
def get_variacao_12m(soup):
    try:
        card = soup.find("div", class_="_card pl")
        valor_span = card.find("span")
        valor = valor_span.text.strip().replace("%", "").replace(".", "").replace(",", ".")
        return float(valor)
    except Exception:
        return None

# 5) Coleta todos os dados da ação
def coletar_indicadores(acao):
    url = f"https://investidor10.com.br/acoes/{acao.lower()}/"
    print(f"\n📥 Coletando dados da ação: {acao}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    }

    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"❌ Erro ao acessar {url} (status {resp.status_code})")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    indicadores_map = {
        "P/L": "pl",
        "P/RECEITA (PSR)": "psr",
        "P/VP": "pvp",
        "DIVIDEND YIELD": "dividend_yield",
        "PAYOUT": "payout",
        "MARGEM LÍQUIDA": "margem_liquida",
        "MARGEM BRUTA": "margem_bruta",
        "MARGEM EBIT": "margem_ebit",
        "MARGEM EBITDA": "margem_ebitda",
        "EV/EBITDA": "ev_ebitda",
        "EV/EBIT": "ev_ebit",
        "P/EBITDA": "p_ebitda",
        "P/EBIT": "p_ebit",
        "P/ATIVO": "p_ativo",
        "P/CAP.GIRO": "p_cap_giro",
        "P/ATIVO CIRC LIQ": "p_ativo_circ_liq",
        "VPA": "vpa",
        "LPA": "lpa",
        "GIRO ATIVOS": "giro_ativos",
        "ROE": "roe",
        "ROIC": "roic",
        "ROA": "roa",
        "DÍVIDA LÍQUIDA / PATRIMÔNIO": "div_liq_patrimonio",
        "DÍVIDA LÍQUIDA / EBITDA": "div_liq_ebitda",
        "DÍVIDA LÍQUIDA / EBIT": "div_liq_ebit",
        "DÍVIDA BRUTA / PATRIMÔNIO": "div_bruta_patrimonio",
        "PATRIMÔNIO / ATIVOS": "patrimonio_ativos",
        "PASSIVOS / ATIVOS": "passivos_ativos",
        "LIQUIDEZ CORRENTE": "liquidez_corrente"
    }

    dados = {"acao": acao}
    for nome_site, nome_coluna in indicadores_map.items():
        valor = get_valor_indicador(soup, nome_site)
        dados[nome_coluna] = valor

    # Adiciona cotação e variação
    dados["cotacao"] = get_cotacao(soup)
    dados["variacao_12m"] = get_variacao_12m(soup)

    print("📊 Dados coletados:")
    for k, v in dados.items():
        print(f"{k}: {v}")

    return dados

# 6) Insere ou atualiza no banco
def salvar_no_banco(dados):
    dados["data_coleta"] = date.today()

    colunas = ", ".join(dados.keys())
    placeholders = ", ".join(["%s"] * len(dados))
    valores = list(dados.values())

    update_exprs = [f"{col} = EXCLUDED.{col}" for col in dados if col not in ["acao", "data_coleta"]]
    update_sql = ", ".join(update_exprs)

    sql = f"""
    INSERT INTO indicadores_fundamentalistas ({colunas})
    VALUES ({placeholders})
    ON CONFLICT (acao, data_coleta) DO UPDATE SET
    {update_sql}
    """

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(sql, valores)
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Inserido/atualizado no banco com sucesso.\n")
    except Exception as e:
        print("❌ Erro ao inserir no banco:", e)

# 7) Função principal
def main():
    acoes = [
        "PETR4", "VALE3", "ITUB4", "BBDC4", "B3SA3", "ABEV3", "BBAS3", "BRFS3", "LREN3", "EGIE3",
        "JBSS3", "WEGE3", "RENT3", "GGBR4", "HAPV3", "CSAN3", "BRKM5", "MRVE3", "CPLE6", "RAIL3",
        "CMIG4", "ASAI3", "PRIO3", "EMBR3", "HYPE3", "ELET3", "ELET6", "ENBR3", "PETZ3", "ALPA4",
        "TIMS3", "AZUL4", "GOLL4", "NTCO3", "CVCB3", "DXCO3", "MGLU3", "CIEL3", "COGN3", "YDUQ3",
        "CRFB3", "BRML3", "SOMA3", "TOTS3", "LWSA3", "SUZB3", "KLBN11", "RAIZ4", "QUAL3", "SMTO3"
    ]
    for acao in acoes:
        dados = coletar_indicadores(acao)
        if dados:
            salvar_no_banco(dados)

# Executa
if __name__ == "__main__":
    main()
