import streamlit as st
import pandas as pd
from typing import List, Tuple, Optional
from sqlalchemy import text
from processadores.processador_dados import ProcessadorDados
from processadores.gerenciador_bd import GerenciadorBancoDados
from configuracoes.config import CONFIGURACAO_BD

@st.cache_data(ttl=3600, show_spinner=False, max_entries=1)
def obter_anos_disponiveis() -> List[int]:
    processador = ProcessadorDados()
    return processador.obter_anos_disponiveis()

@st.cache_data(ttl=7200, show_spinner=False, max_entries=1)
def obter_estatisticas_resumo() -> dict:
    try:
        processador = ProcessadorDados()
        engine = processador.gerenciador_bd.obter_engine()
        if not engine:
            return {}
        consulta_stats = text(f"""
            SELECT 
                COUNT(*) as total_registros,
                COUNT(DISTINCT municipio) as total_municipios,
                AVG(riscofogo) as risco_medio,
                AVG(precipitacao) as precip_media,
                MIN(datahora) as data_inicio,
                MAX(datahora) as data_fim
            FROM "{CONFIGURACAO_BD['schema']}"."{CONFIGURACAO_BD['table']}"
            WHERE riscofogo BETWEEN 0 AND 1
            AND precipitacao >= 0
            AND diasemchuva >= 0
            AND latitude BETWEEN -15 AND 5
            AND longitude BETWEEN -60 AND -45
        """)
        
        with engine.connect() as conn:
            resultado = conn.execute(consulta_stats).fetchone()
            
            if resultado:
                return {
                    'total_registros': resultado[0] or 0,
                    'total_municipios': resultado[1] or 0,
                    'risco_medio': resultado[2] or 0,
                    'precip_media': resultado[3] or 0,
                    'data_inicio': resultado[4],
                    'data_fim': resultado[5]
                }
        return {}
    except Exception:
        return {}

def obter_dados_cache_otimizado(ano: Optional[int] = None) -> Optional[pd.DataFrame]:
    processador = ProcessadorDados()
    consulta_original = processador._construir_consulta_base
    
    def consulta_otimizada():
        return f"""
            SELECT
                datahora,
                riscofogo,
                precipitacao,
                municipio,
                diasemchuva,
                latitude,
                longitude
            FROM "{CONFIGURACAO_BD['schema']}"."{CONFIGURACAO_BD['table']}"
        """
    
    processador._construir_consulta_base = consulta_otimizada
    
    try:
        df_completo = processador.carregar_dados_inpe(ano)
        
        if df_completo is None or df_completo.empty:
            return pd.DataFrame()
        
        if 'municipio' in df_completo.columns and 'mun_corrigido' not in df_completo.columns:
            df_completo['mun_corrigido'] = df_completo['municipio']
        
        if len(df_completo) > 50000:
            col_grupo = 'mun_corrigido' if 'mun_corrigido' in df_completo.columns else 'municipio'
            df_amostra = df_completo.groupby(col_grupo, group_keys=False).apply(
                lambda x: x.sample(min(len(x), max(10, len(x) // 10)), random_state=42)
                if len(x) > 10 else x
            ).reset_index(drop=True)
            
            return df_amostra
        else:
            return df_completo
            
    except Exception as e:
        print(f"Erro no carregamento otimizado: {e}")
        return pd.DataFrame()
    finally:
        processador._construir_consulta_base = consulta_original

def inicializar_dados() -> Tuple[List[str], pd.DataFrame]:
    try:
        stats = obter_estatisticas_resumo()
        
        if stats and stats.get('total_registros', 0) > 0:
            if stats.get('data_inicio') and stats.get('data_fim'):
                ano_inicio = stats['data_inicio'].year if hasattr(stats['data_inicio'], 'year') else 2020
                ano_fim = stats['data_fim'].year if hasattr(stats['data_fim'], 'year') else 2024
                anos = list(range(ano_inicio, ano_fim + 1))
            else:
                anos = obter_anos_disponiveis()
        else:
            anos = obter_anos_disponiveis()
        
        opcoes_ano = ["Todos os Anos"] + [str(ano) for ano in anos]
        df_base = obter_dados_cache_otimizado(None)
        
        return opcoes_ano, df_base if df_base is not None else pd.DataFrame()
    except Exception as e:
        print(f"Erro na inicialização: {e}")
        return ["Todos os Anos"], pd.DataFrame()

def obter_dados_ano(opcao_ano: str, df_base: pd.DataFrame) -> pd.DataFrame:
    if opcao_ano == "Todos os Anos":
        return df_base if not df_base.empty else pd.DataFrame()
    else:
        try:
            ano = int(opcao_ano)
            if df_base.empty:
                return obter_dados_cache_otimizado(ano)
            else:
                dados_ano = df_base[df_base['DataHora'].dt.year == ano].copy()
                if dados_ano.empty:
                    return obter_dados_cache_otimizado(ano)
                return dados_ano
        except (ValueError, KeyError):
            return pd.DataFrame()
