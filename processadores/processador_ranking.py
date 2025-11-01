import gc
import pandas as pd
from typing import List, Tuple
from configuracoes.config import TAMANHO_CHUNK

class ProcessadorRanking:
    
    @staticmethod
    def _processar_agregacao_chunk(chunk: pd.DataFrame, tema: str) -> pd.DataFrame:
        chunk_limpo = chunk.dropna(subset=['mun_corrigido']).copy()
        
        configs_agregacao = {
            "Maior Risco de Fogo": {
                'RiscoFogo': ['mean', 'max', 'count'],
                'DataHora': ['min', 'max']
            },
            "Maior Precipitação (evento)": {
                'Precipitacao': ['mean', 'max', 'sum', 'count'],
                'DataHora': ['min', 'max']
            },
            "Máx. Dias Sem Chuva": {
                'DiaSemChuva': ['mean', 'max', 'count'],
                'DataHora': ['min', 'max']
            }
        }
        
        if tema in configs_agregacao:
            return chunk_limpo.groupby('mun_corrigido', observed=True).agg(configs_agregacao[tema])
        
        return pd.DataFrame()
    
    @staticmethod
    def _combinar_resultados_chunks(resultados: List[pd.DataFrame], tema: str) -> pd.DataFrame:
        if not resultados:
            return pd.DataFrame()
        
        configs_combinacao = {
            "Maior Risco de Fogo": {
                ('RiscoFogo', 'mean'): 'mean',
                ('RiscoFogo', 'max'): 'max',
                ('RiscoFogo', 'count'): 'sum',
                ('DataHora', 'min'): 'min',
                ('DataHora', 'max'): 'max'
            },
            "Maior Precipitação (evento)": {
                ('Precipitacao', 'mean'): 'mean',
                ('Precipitacao', 'max'): 'max',
                ('Precipitacao', 'sum'): 'sum',
                ('Precipitacao', 'count'): 'sum',
                ('DataHora', 'min'): 'min',
                ('DataHora', 'max'): 'max'
            },
            "Máx. Dias Sem Chuva": {
                ('DiaSemChuva', 'mean'): 'mean',
                ('DiaSemChuva', 'max'): 'max',
                ('DiaSemChuva', 'count'): 'sum',
                ('DataHora', 'min'): 'min',
                ('DataHora', 'max'): 'max'
            }
        }
        
        if tema in configs_combinacao:
            return pd.concat(resultados).groupby(level=0, observed=True).agg(configs_combinacao[tema])
        
        return pd.DataFrame()
    
    @staticmethod
    def _formatar_resultado_ranking(df_agregado: pd.DataFrame, tema: str) -> Tuple[pd.DataFrame, str]:
        if df_agregado.empty:
            return pd.DataFrame(), ''
        
        formatadores = {
            "Maior Risco de Fogo": (
                ProcessadorRanking._formatar_ranking_risco_fogo,
                'Risco Médio'
            ),
            "Maior Precipitação (evento)": (
                ProcessadorRanking._formatar_ranking_precipitacao,
                'Precipitação Máxima (mm)'
            ),
            "Máx. Dias Sem Chuva": (
                ProcessadorRanking._formatar_ranking_dias_secos,
                'Máx. Dias Sem Chuva'
            )
        }
        
        if tema in formatadores:
            funcao_formatadora, nome_coluna = formatadores[tema]
            df_rank = funcao_formatadora(df_agregado)
            
            if not df_rank.empty:
                df_rank.insert(0, 'Posição', range(1, len(df_rank) + 1))
            
            return df_rank, nome_coluna
        
        return pd.DataFrame(), ''
    
    @staticmethod
    def _formatar_ranking_risco_fogo(df_agregado: pd.DataFrame) -> pd.DataFrame:
        df_agregado = df_agregado.round(4)
        df_rank = df_agregado.nlargest(20, ('RiscoFogo', 'mean')).reset_index()
        
        df_rank.columns = ['Município', 'Risco Médio', 'Risco Máximo', 'Nº Registros', 
                           'Primeira Ocorrência', 'Última Ocorrência']
        
        df_rank['Primeira Ocorrência'] = pd.to_datetime(df_rank['Primeira Ocorrência']).dt.strftime('%d/%m/%Y')
        df_rank['Última Ocorrência'] = pd.to_datetime(df_rank['Última Ocorrência']).dt.strftime('%d/%m/%Y')
        
        return df_rank
    
    @staticmethod
    def _formatar_ranking_precipitacao(df_agregado: pd.DataFrame) -> pd.DataFrame:
        df_agregado = df_agregado.round(2)
        df_rank = df_agregado.nlargest(20, ('Precipitacao', 'max')).reset_index()
        
        df_rank.columns = ['Município', 'Precipitação Máxima (mm)', 'Precipitação Média (mm)',
                           'Precipitação Total (mm)', 'Nº Registros', 'Primeira Ocorrência', 
                           'Última Ocorrência']
        
        df_rank['Primeira Ocorrência'] = pd.to_datetime(df_rank['Primeira Ocorrência']).dt.strftime('%d/%m/%Y')
        df_rank['Última Ocorrência'] = pd.to_datetime(df_rank['Última Ocorrência']).dt.strftime('%d/%m/%Y')
        
        return df_rank
    
    @staticmethod
    def _formatar_ranking_dias_secos(df_agregado: pd.DataFrame) -> pd.DataFrame:
        df_agregado = df_agregado.round(1)
        df_rank = df_agregado.nlargest(20, ('DiaSemChuva', 'max')).reset_index()
        
        df_rank.columns = ['Município', 'Máx. Dias Sem Chuva', 'Média Dias Sem Chuva',
                           'Nº Registros', 'Primeira Ocorrência', 'Última Ocorrência']
        
        df_rank['Primeira Ocorrência'] = pd.to_datetime(df_rank['Primeira Ocorrência']).dt.strftime('%d/%m/%Y')
        df_rank['Última Ocorrência'] = pd.to_datetime(df_rank['Última Ocorrência']).dt.strftime('%d/%m/%Y')
        
        return df_rank
    
    def processar_ranking(self, df: pd.DataFrame, tema: str, periodo: str) -> Tuple[pd.DataFrame, str]:
        if df is None or df.empty:
            return pd.DataFrame(), ''
        
        try:
            if len(df) > TAMANHO_CHUNK:
                chunks = [df[i:i + TAMANHO_CHUNK] for i in range(0, len(df), TAMANHO_CHUNK)]
                resultados = []
                
                for chunk in chunks:
                    resultado_chunk = self._processar_agregacao_chunk(chunk, tema)
                    if not resultado_chunk.empty:
                        resultados.append(resultado_chunk)
                    
                    del chunk
                    gc.collect()
                
                df_agregado = self._combinar_resultados_chunks(resultados, tema)
                del resultados
                gc.collect()
            else:
                df_agregado = self._processar_agregacao_chunk(df, tema)
            
            df_rank, col_ordem = self._formatar_resultado_ranking(df_agregado, tema)
            
            del df_agregado
            gc.collect()
            
            return df_rank, col_ordem
            
        except Exception:
            return pd.DataFrame(), ''
