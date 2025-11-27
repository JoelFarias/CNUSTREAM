import pandas as pd
import streamlit as st

def limpar_texto(texto):
    if pd.isna(texto):
        return ""
    return str(texto).strip().title()

def limpar_dados_estado(valor_estado):
    if pd.isna(valor_estado):
        return None
    
    estado_str = str(valor_estado).strip().upper()
    
    if estado_str in ['UF', 'NAN', 'NONE', 'NULL', '']:
        return None
    
    if estado_str.isdigit():
        return None
    
    if any(char.isdigit() for char in estado_str):
        return None
    
    if not all(char.isalpha() or char.isspace() for char in estado_str):
        return None
    
    if len(estado_str.replace(' ', '')) < 2:
        return None
    
    siglas_para_estados = {
        'AC': 'Acre', 'AL': 'Alagoas', 'AP': 'Amapá', 'AM': 'Amazonas',
        'BA': 'Bahia', 'CE': 'Ceará', 'DF': 'Distrito Federal',
        'ES': 'Espírito Santo', 'GO': 'Goiás', 'MA': 'Maranhão',
        'MT': 'Mato Grosso', 'MS': 'Mato Grosso do Sul', 'MG': 'Minas Gerais',
        'PA': 'Pará', 'PB': 'Paraíba', 'PR': 'Paraná', 'PE': 'Pernambuco',
        'PI': 'Piauí', 'RJ': 'Rio de Janeiro', 'RN': 'Rio Grande do Norte',
        'RS': 'Rio Grande do Sul', 'RO': 'Rondônia', 'RR': 'Roraima',
        'SC': 'Santa Catarina', 'SP': 'São Paulo', 'SE': 'Sergipe', 'TO': 'Tocantins'
    }
    
    if estado_str in siglas_para_estados:
        return siglas_para_estados[estado_str]
    
    nomes_estados = list(siglas_para_estados.values())
    
    correcoes = {
        'PARA': 'Pará', 'CEARA': 'Ceará', 'ESPIRITO SANTO': 'Espírito Santo',
        'GOIAS': 'Goiás', 'MARANHAO': 'Maranhão', 'PARAIBA': 'Paraíba',
        'PARANA': 'Paraná', 'PIAUI': 'Piauí', 'RONDONIA': 'Rondônia',
        'SAO PAULO': 'São Paulo',
        'Para': 'Pará', 'Ceara': 'Ceará', 'Espirito Santo': 'Espírito Santo',
        'Goias': 'Goiás', 'Maranhao': 'Maranhão', 'Paraiba': 'Paraíba',
        'Parana': 'Paraná', 'Piaui': 'Piauí', 'Rondonia': 'Rondônia',
        'Sao Paulo': 'São Paulo'
    }
    
    if estado_str in correcoes:
        return correcoes[estado_str]
    
    estado_title = estado_str.title()
    if estado_title in correcoes:
        return correcoes[estado_title]
    
    for nome_valido in nomes_estados:
        if estado_str == nome_valido.upper() or estado_str.replace(' ', '') == nome_valido.upper().replace(' ', ''):
            return nome_valido
        if estado_title == nome_valido or estado_title.replace(' ', '') == nome_valido.replace(' ', ''):
            return nome_valido
    
    return None

def encontrar_coluna_valida(df: pd.DataFrame, colunas_possiveis: list) -> str:
    for col in colunas_possiveis:
        if col in df.columns:
            return col
    
    colunas_df_lower = {col.lower(): col for col in df.columns}
    for col in colunas_possiveis:
        if col.lower() in colunas_df_lower:
            return colunas_df_lower[col.lower()]
    
    for col in colunas_possiveis:
        for coluna_df in df.columns:
            if col.lower() in coluna_df.lower() or coluna_df.lower() in col.lower():
                return coluna_df
    
    return None

def processar_dados_cpt_por_municipios(dados_cpt: dict) -> dict:
    try:
        dados_municipios = {}
        dados_temporais = []
        dados_detalhados = {}
        
        config_tabelas = {
            'areas_conflito': {
                'municipio_col': ['municipio', 'Municipio', 'MUNICIPIO', 'município', 'Município'],
                'ano_col': ['ano', 'Ano', 'ano_referencia', 'data', 'Data', 'year'],
                'valor_col': ['area', 'Area', 'AREA', 'hectares', 'ha', 'tamanho'],
                'tipo': 'Areas_Conflito'
            },
            'assassinatos': {
                'municipio_col': ['municipio', 'Municipio', 'MUNICIPIO', 'município', 'Município'],
                'ano_col': ['ano', 'Ano', 'ano_referencia', 'data', 'Data', 'year'],
                'valor_col': ['assassinatos', 'quantidade', 'qtd', 'total', 'vitimas', 'mortos'],
                'tipo': 'Assassinatos'
            },
            'conflitos': {
                'municipio_col': ['municipio', 'Municipio', 'MUNICIPIO', 'município', 'Município'],
                'ano_col': ['ano', 'Ano', 'ano_referencia', 'data', 'Data', 'year'],
                'valor_col': ['familias', 'Familias', 'total_familias', 'familias_envolvidas', 'pessoas'],
                'tipo': 'Conflitos_Terra'
            },
            'trabalho_escravo': {
                'municipio_col': ['municipio', 'Municipio', 'MUNICIPIO', 'município', 'Município', 'nome_municipio', 'cidade'],
                'ano_col': ['ano', 'Ano', 'ANO', 'ano_referencia', 'data', 'Data', 'year', 'anodetec', 'periodo'],
                'valor_col': ['trabalhadores', 'quantidade', 'total', 'pessoas', 'vitimas', 'libertados', 'qtd_pessoas', 'numero'],
                'tipo': 'Trabalho_Escravo'
            }
        }
        
        for chave_tabela, config in config_tabelas.items():
            if chave_tabela not in dados_cpt or dados_cpt[chave_tabela].empty:
                dados_detalhados[chave_tabela] = pd.DataFrame()
                continue
                
            df = dados_cpt[chave_tabela].copy()
            dados_detalhados[chave_tabela] = df
            
            col_municipio = encontrar_coluna_valida(df, config['municipio_col'])
            col_ano = encontrar_coluna_valida(df, config['ano_col'])
            
            if not col_municipio or not col_ano:
                st.warning(f"Colunas não encontradas para {chave_tabela}: município={col_municipio}, ano={col_ano}")
                continue
        
            df[col_municipio] = df[col_municipio].astype(str).str.strip().str.title()
            df = df[df[col_municipio].notna() & 
                   (df[col_municipio] != 'Nan') & 
                   (df[col_municipio] != 'None') & 
                   (df[col_municipio] != '') & 
                   (df[col_municipio] != 'Null') &
                   (df[col_municipio] != 'Na') &
                   (df[col_municipio].str.len() > 2)]
            
            colunas_estado = ['estado', 'Estado', 'ESTADO', 'uf', 'UF', 'sigla_uf', 'unidade_federacao']
            coluna_estado_encontrada = None
            for col_estado in colunas_estado:
                if col_estado in df.columns:
                    coluna_estado_encontrada = col_estado
                    break
            
            if coluna_estado_encontrada:
                df[coluna_estado_encontrada] = df[coluna_estado_encontrada].apply(limpar_dados_estado)
                df = df[df[coluna_estado_encontrada].notna()]
            
            df[col_ano] = pd.to_numeric(df[col_ano], errors='coerce')
            df = df[df[col_ano].notna() & (df[col_ano] > 1980) & (df[col_ano] < 2030)]
            
            if df.empty:
                continue
            
            if chave_tabela == 'conflitos':
                resumo_municipio = df.groupby(col_municipio, observed=False).agg({
                    col_ano: ['count', 'min', 'max']
                }).reset_index()
                resumo_municipio.columns = [col_municipio, 'total_ocorrencias', 'ano_min', 'ano_max']
                
                col_familias = encontrar_coluna_valida(df, config['valor_col'])
                if col_familias:
                    df[col_familias] = pd.to_numeric(df[col_familias], errors='coerce')
                    resumo_familias = df.groupby(col_municipio, observed=False)[col_familias].sum().reset_index()
                    resumo_municipio = resumo_municipio.merge(resumo_familias, on=col_municipio, how='left')
                    resumo_municipio[col_familias] = resumo_municipio[col_familias].fillna(0)
                else:
                    resumo_municipio['familias_afetadas'] = 0
                    
            elif chave_tabela in ['assassinatos', 'trabalho_escravo']:
                col_valor = encontrar_coluna_valida(df, config['valor_col'])
                if col_valor:
                    df[col_valor] = pd.to_numeric(df[col_valor], errors='coerce').fillna(1)
                    resumo_municipio = df.groupby(col_municipio, observed=False).agg({
                        col_ano: ['count', 'min', 'max'],
                        col_valor: 'sum'
                    }).reset_index()
                    resumo_municipio.columns = [col_municipio, 'total_ocorrencias', 'ano_min', 'ano_max', 'valor_total']
                else:
                    resumo_municipio = df.groupby(col_municipio, observed=False).agg({
                        col_ano: ['count', 'min', 'max']
                    }).reset_index()
                    resumo_municipio.columns = [col_municipio, 'total_ocorrencias', 'ano_min', 'ano_max']
            else:
                resumo_municipio = df.groupby(col_municipio, observed=False).agg({
                    col_ano: ['count', 'min', 'max']
                }).reset_index()
                resumo_municipio.columns = [col_municipio, 'total_ocorrencias', 'ano_min', 'ano_max']
            
            for _, linha in resumo_municipio.iterrows():
                municipio = linha[col_municipio]
                
                if pd.isna(municipio) or str(municipio).strip() == '' or str(municipio).strip().lower() in ['nan', 'none', 'null', 'na']:
                    continue
                
                municipio = str(municipio).strip().title()
                
                if municipio not in dados_municipios:
                    dados_municipios[municipio] = {
                        'Município': municipio,
                        'Areas_Conflito': 0,
                        'Assassinatos': 0,
                        'Conflitos_Terra': 0,
                        'Trabalho_Escravo': 0,
                        'Total_Ocorrencias': 0,
                        'Total_Familias': 0
                    }
                
                if chave_tabela in ['assassinatos', 'trabalho_escravo'] and 'valor_total' in resumo_municipio.columns:
                    valor_usar = int(linha['valor_total']) if pd.notna(linha['valor_total']) else int(linha['total_ocorrencias'])
                else:
                    valor_usar = int(linha['total_ocorrencias'])
                
                dados_municipios[municipio][config['tipo']] = valor_usar
                dados_municipios[municipio]['Total_Ocorrencias'] += valor_usar
                
                if chave_tabela == 'conflitos':
                    col_familias = encontrar_coluna_valida(df, config['valor_col'])
                    if col_familias and col_familias in resumo_municipio.columns:
                        familias = linha[col_familias] if pd.notna(linha[col_familias]) else 0
                        dados_municipios[municipio]['Total_Familias'] += int(familias)
            
            resumo_temporal = df.groupby(col_ano, observed=False).size().reset_index()
            resumo_temporal.columns = ['ano', 'quantidade']
            resumo_temporal['tipo'] = config['tipo'].replace('_', ' ')
            dados_temporais.append(resumo_temporal)
        
        df_temporal = pd.concat(dados_temporais, ignore_index=True) if dados_temporais else pd.DataFrame()
        df_municipios = pd.DataFrame(list(dados_municipios.values()))
        
        if not df_municipios.empty:
            df_municipios = df_municipios.sort_values('Total_Ocorrencias', ascending=False)
        
        return {
            'municipios_summary': df_municipios,
            'temporal_data': df_temporal,
            'detailed_data': dados_detalhados,
            'total_municipios': len(df_municipios),
            'total_ocorrencias': df_municipios['Total_Ocorrencias'].sum() if not df_municipios.empty else 0
        }
        
    except Exception as e:
        st.error(f"Erro ao processar dados CPT: {str(e)}")
        return {
            'municipios_summary': pd.DataFrame(),
            'temporal_data': pd.DataFrame(),
            'detailed_data': {},
            'total_municipios': 0,
            'total_ocorrencias': 0
        }
