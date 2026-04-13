import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import requests
from bs4 import BeautifulSoup
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.core.db_connection import get_connection

# ETAPA 1: FUNÇÕES PARA EXTRAIR INDICADORES E DADOS DA PÁGINA

def get_valor_indicador(soup, nome_indicador):
    """
    Extrai valores numéricos de indicadores (ex.: P/L, ROE etc.) a partir
    de <span> que contenham o nome do indicador. 
    """
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

def get_cotacao(soup):
    """
    Extrai a cotação (R$) da ação do card com class="_card cotacao".
    """
    try:
        card = soup.find("div", class_="_card cotacao")
        valor_span = card.find("span", class_="value")
        valor = valor_span.text.strip().replace("R$", "").replace(".", "").replace(",", ".")
        return float(valor)
    except Exception:
        return None

def get_variacao_12m(soup):
    """
    Extrai a variação nos últimos 12 meses do card com class="_card pl".
    """
    try:
        card = soup.find("div", class_="_card pl")
        body = card.find("div", class_="_card-body")
        valor_span = body.find("span")
        valor = valor_span.text.strip().replace("%", "").replace(".", "").replace(",", ".")
        return float(valor)
    except Exception as e:
        print(f"❌ Erro ao extrair variação 12M: {e}")
        return None

def coletar_indicadores(acao):
    """
    Faz requisição ao site, extrai todos os indicadores mapeados,
    além da cotação e variação 12M. Retorna um dicionário com os
    dados e uma string de log formatado.
    """
    url = f"https://investidor10.com.br/acoes/{acao.lower()}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    }

    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            return f"❌ {acao} - erro ao acessar site (status {resp.status_code})"

        soup = BeautifulSoup(resp.text, "html.parser")

        # Mapa de indicadores: nome na página → nome da coluna no dicionário
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

        # Cria dicionário base
        dados = {"acao": acao}

        # Extrai todos os indicadores mapeados
        for nome_site, nome_coluna in indicadores_map.items():
            dados[nome_coluna] = get_valor_indicador(soup, nome_site)

        # Extrai cotação e variação
        dados["cotacao"] = get_cotacao(soup)
        dados["variacao_12m"] = get_variacao_12m(soup)

        # Monta um log organizado para exibição
        linhas = [f"\n📊 Dados coletados: {acao}"]
        for k, v in dados.items():
            linhas.append(f"{k}: {v}")
        log_final = "\n".join(linhas)

        return dados, log_final

    except Exception as e:
        return f"❌ {acao} - erro inesperado: {e}"

# ETAPA 2: SALVAR NO BANCO DE DADOS

def salvar_no_banco(dados):
    """
    Insere (ou atualiza via ON CONFLICT) os dados extraídos na tabela
    indicadores_fundamentalistas, adicionando a data de coleta.
    """
    dados["data_coleta"] = date.today()

    colunas = ", ".join(dados.keys())
    placeholders = ", ".join(["%s"] * len(dados))
    valores = list(dados.values())

    # Monta expressões para UPDATE de todos os campos que não são PK
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

# ETAPA 3: LÓGICA PARA PROCESSAR CADA AÇÃO E RODAR EM PARALELO

def processar_acao(acao):
    """
    Função que coleta os indicadores da ação, mostra o log,
    e salva no banco.
    """
    resultado = coletar_indicadores(acao)
    # Se for uma tuple, veio (dados, log). Se for string, é erro.
    if isinstance(resultado, tuple):
        dados, log = resultado
        print(log)
        salvar_no_banco(dados)
    else:
        print(resultado)  # mensagem de erro como string

# ETAPA 4: MAIN PARA EXECUÇÃO COM THREADPOOL

def main():
    """
    Ponto de entrada do script. Define a lista de ações, configura
    o máximo de threads e executa tudo em paralelo.
    """
    acoes = [
        "PETR4", "VALE3", "ITUB4", "BBDC4", "B3SA3", "ABEV3", "BBAS3", "BRFS3", "LREN3", "EGIE3",
        "JBSS3", "WEGE3", "RENT3", "GGBR4", "HAPV3", "CSAN3", "BRKM5", "MRVE3", "CPLE6", "RAIL3",
        "CMIG4", "ASAI3", "PRIO3", "EMBR3", "HYPE3", "ELET3", "ELET6", "ENBR3", "PETZ3", "ALPA4",
        "TIMS3", "AZUL4", "GOLL4", "NTCO3", "CVCB3", "DXCO3", "MGLU3", "CIEL3", "COGN3", "YDUQ3",
        "CRFB3", "BRML3", "SOMA3", "TOTS3", "LWSA3", "SUZB3", "KLBN11", "RAIZ4", "QUAL3", "SMTO3",
        "BPAC11", "CPFE3", "CYRE3", "MULT3", "EQTL3", "SLCE3", "VIVT3", "NEOE3", "MOVI3", "BEEF3",
        "ARZZ3", "CASH3", "TRPL4", "RRRP3", "VAMO3", "RANI3", "PARD3", "RECV3",
        "MEAL3", "TEND3", "MRFG3", "MDIA3", "TASA4", "GMAT3", "GFSA3", "BPAN4", "CEAB3",
        "DIRR3", "ENGI11", "GRND3", "IRBR3", "SEQL3", "UNIP6", "USIM5", "BRSR6", "SLED4", "STBP3",
        "CEPE5", "CBEE3", "MTSA4", "EZTC3", "AVLL3", "IGTI11", "BRPR3", "IGTA3", "TUPY3", "CGAS5",
        "FRAS3", "AERI3", "BLAU3", "LJQQ3", "LOGG3", "OFSA3", "ORVR3", "PNVL3",
        "POSI3", "POMO4", "PTBL3", "RAPT4", "SAPR4", "SBSP3", "TAEE11", "TGMA3", "TRIS3",
        "VIVA3", "VLID3", "WIZC3", "BRAP4", "BMIN3", "JHSF3", "EVEN3", "GUAR3", "HETA4", "VULC3",
        "MTRE3", "BMOB3", "ENAT3", "OIBR3", "CEGR3", "BALM4", "SMLS3", "SHOW3", "MODL11", "CBAV3",
        "ITSA4", "SANB11", "BBSE3", "RDOR3", "CXSE3", "PSSA3", "CEEB3", "TFCO4", "MRSA3B",
        "ALUP11", "UGPA3", "VBBR3", "ENEV3", "ISAE4", "EQPA3", "REDE3"
    ]

    max_workers = max(1, os.cpu_count() - 1)
    print(f"\n🚀 Iniciando scraping paralelo com {max_workers} threads...\n")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(processar_acao, acao) for acao in acoes]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print("❌ Erro em uma thread:", e)


if __name__ == "__main__":
    main()
