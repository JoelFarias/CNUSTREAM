import gc
import pandas as pd
import psutil
from typing import List, Optional
from sqlalchemy import text
from processadores.gerenciador_bd import GerenciadorBancoDados, limpar_memoria_se_necessario
from configuracoes.config import CONFIGURACAO_BD, TAMANHO_CHUNK, LIMITE_MEMORIA

class ProcessadorDados:
    
    def __init__(self):
        self.gerenciador_bd = GerenciadorBancoDados()
        self._filtros_base = [
            "riscofogo BETWEEN 0 AND 1",
            "precipitacao >= 0",
            "diasemchuva >= 0",
            "latitude BETWEEN -15 AND 5",
            "longitude BETWEEN -60 AND -45"
        ]
    
    def _verificar_uso_memoria(self) -> bool:
        return psutil.virtual_memory().percent < LIMITE_MEMORIA
    
    def _otimizar_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        
        colunas_float = df.select_dtypes(include=['float64']).columns
        for col in colunas_float:
            df[col] = pd.to_numeric(df[col], downcast='float', errors='coerce')
        
        colunas_int = df.select_dtypes(include=['int64']).columns
        for col in colunas_int:
            df[col] = pd.to_numeric(df[col], downcast='integer', errors='coerce')
        
        colunas_obj = df.select_dtypes(include=['object']).columns
        for col in colunas_obj:
            if col != 'DataHora' and df[col].nunique() / len(df) < 0.4:
                df[col] = df[col].astype('category')
        
        return df
    
    def _obter_contagem_linhas(self, engine, clausula_where: str) -> int:
        try:
            consulta_contagem = text(f"""
                SELECT COUNT(*) 
                FROM "{CONFIGURACAO_BD['schema']}"."{CONFIGURACAO_BD['table']}"
                WHERE {clausula_where}
            """)
            
            with engine.connect() as conn:
                resultado = conn.execute(consulta_contagem)
                return resultado.scalar() or 0
        except Exception:
            return 0
    
    def _construir_consulta_base(self) -> str:
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
    
    def _carregar_dados_em_chunks(self, engine, consulta_base: str, clausula_where: str, 
                         total_linhas: int) -> Optional[pd.DataFrame]:
        chunks = []
        
        try:
            for offset in range(0, total_linhas, TAMANHO_CHUNK):
                if not self._verificar_uso_memoria():
                    gc.collect()
                    if not self._verificar_uso_memoria():
                        break
                
                consulta_chunk = text(f"""
                    {consulta_base}
                    WHERE {clausula_where}
                    LIMIT {TAMANHO_CHUNK} OFFSET {offset}
                """)
                
                chunk_df = pd.read_sql(consulta_chunk, engine, parse_dates=['datahora'])
                chunk_df = self._otimizar_dataframe(chunk_df)
                chunks.append(chunk_df)
                
                del chunk_df
                gc.collect()
            
            if chunks:
                df = pd.concat(chunks, ignore_index=True)
                del chunks
                gc.collect()
                return df
            
        except Exception:
            pass
        
        return None
    
    def carregar_dados_inpe(self, ano: Optional[int] = None) -> Optional[pd.DataFrame]:
        engine = None
        try:
            engine = self.gerenciador_bd.obter_engine()
            if not engine:
                return None
            
            filtros = self._filtros_base.copy()
            if ano is not None:
                filtros.append(f"EXTRACT(YEAR FROM datahora) = {ano}")
            clausula_where = " AND ".join(filtros)
            
            total_linhas = self._obter_contagem_linhas(engine, clausula_where)
            if total_linhas == 0:
                return pd.DataFrame()
            
            consulta_base = self._construir_consulta_base()
            
            if total_linhas <= TAMANHO_CHUNK:
                consulta = text(f"{consulta_base} WHERE {clausula_where}")
                df = pd.read_sql(consulta, engine, parse_dates=['datahora'])
            else:
                df = self._carregar_dados_em_chunks(engine, consulta_base, clausula_where, total_linhas)
            
            if df is None or df.empty:
                return pd.DataFrame()
            
            df = df.rename(columns={
                'datahora': 'DataHora',
                'riscofogo': 'RiscoFogo',
                'precipitacao': 'Precipitacao',
                'municipio': 'mun_corrigido',
                'diasemchuva': 'DiaSemChuva',
                'latitude': 'Latitude',
                'longitude': 'Longitude'
            })
            
            df = self._otimizar_dataframe(df)
            df = df.dropna(subset=['DataHora', 'mun_corrigido'])
            
            gc.collect()
            return df
            
        except Exception:
            return None
        finally:
            if engine:
                engine.dispose()
            self.gerenciador_bd.liberar()
            limpar_memoria_se_necessario()
    
    def obter_anos_disponiveis(self) -> List[int]:
        engine = self.gerenciador_bd.obter_engine()
        if not engine:
            return []
        
        try:
            consulta = text(f"""
                SELECT DISTINCT EXTRACT(YEAR FROM datahora) AS year
                FROM "{CONFIGURACAO_BD['schema']}"."{CONFIGURACAO_BD['table']}"
                WHERE datahora IS NOT NULL
                ORDER BY year
            """)
            
            with engine.connect() as conn:
                resultado = conn.execute(consulta)
                anos = [int(row[0]) for row in resultado.fetchall() if row[0] is not None]
            
            return anos
            
        except Exception:
            return []
        finally:
            self.gerenciador_bd.liberar()
