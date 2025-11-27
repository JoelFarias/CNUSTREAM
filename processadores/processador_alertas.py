"""
Processador de Alertas de Desmatamento
Responsável pelo carregamento e processamento de dados de alertas
"""

import geopandas as gpd
import pandas as pd
import streamlit as st

def normalizar_estado(sigla):
    """Normaliza sigla de estado para nome completo"""
    mapa_estados = {
        'AC': 'Acre', 'ACRE': 'Acre',
        'AL': 'Alagoas', 'ALAGOAS': 'Alagoas',
        'AP': 'Amapá', 'AMAPÁ': 'Amapá',
        'AM': 'Amazonas', 'AMAZONAS': 'Amazonas',
        'BA': 'Bahia', 'BAHIA': 'Bahia',
        'CE': 'Ceará', 'CEARÁ': 'Ceará',
        'DF': 'Distrito Federal', 'DISTRITO FEDERAL': 'Distrito Federal',
        'ES': 'Espírito Santo', 'ESPÍRITO SANTO': 'Espírito Santo',
        'GO': 'Goiás', 'GOIÁS': 'Goiás',
        'MA': 'Maranhão', 'MARANHÃO': 'Maranhão',
        'MT': 'Mato Grosso', 'MATO GROSSO': 'Mato Grosso',
        'MS': 'Mato Grosso do Sul', 'MATO GROSSO DO SUL': 'Mato Grosso do Sul',
        'MG': 'Minas Gerais', 'MINAS GERAIS': 'Minas Gerais',
        'PA': 'Pará', 'PARÁ': 'Pará',
        'PB': 'Paraíba', 'PARAÍBA': 'Paraíba',
        'PR': 'Paraná', 'PARANÁ': 'Paraná',
        'PE': 'Pernambuco', 'PERNAMBUCO': 'Pernambuco',
        'PI': 'Piauí', 'PIAUÍ': 'Piauí',
        'RJ': 'Rio de Janeiro', 'RIO DE JANEIRO': 'Rio de Janeiro',
        'RN': 'Rio Grande do Norte', 'RIO GRANDE DO NORTE': 'Rio Grande do Norte',
        'RS': 'Rio Grande do Sul', 'RIO GRANDE DO SUL': 'Rio Grande do Sul',
        'RO': 'Rondônia', 'RONDÔNIA': 'Rondônia',
        'RR': 'Roraima', 'RORAIMA': 'Roraima',
        'SC': 'Santa Catarina', 'SANTA CATARINA': 'Santa Catarina',
        'SP': 'São Paulo', 'SÃO PAULO': 'São Paulo',
        'SE': 'Sergipe', 'SERGIPE': 'Sergipe',
        'TO': 'Tocantins', 'TOCANTINS': 'Tocantins'
    }
    if pd.isna(sigla):
        return None
    sigla_upper = str(sigla).strip().upper()
    return mapa_estados.get(sigla_upper, None)


def carregar_alerta_shapefile(caminho, tipo_origem):
    """
    Carrega um shapefile de alertas otimizado para Streamlit Cloud.
    Simplifica geometrias e reduz uso de memória.
    
    Args:
        caminho: Caminho para o arquivo shapefile
        tipo_origem: Identificador da origem dos dados (ex: 'Pará', 'Estados', 'TI')
    
    Returns:
        GeoDataFrame com alertas padronizados
    """
    try:
        # Verificar se arquivo existe
        import os
        if not os.path.exists(caminho):
            st.warning(f"⚠️ Arquivo não encontrado: {caminho}")
            return gpd.GeoDataFrame()
        
        # Carregar shapefile
        gdf = gpd.read_file(caminho)
        
        if gdf.empty:
            st.warning(f"⚠️ Arquivo vazio: {caminho}")
            return gpd.GeoDataFrame()
        
        # Simplificar geometrias ANTES de processar (reduz 50-70% da memória)
        gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.001, preserve_topology=True)
        
        # Ajustar CRS para padrão WGS84 (EPSG:4326)
        if gdf.crs is None:
            gdf = gdf.set_crs('EPSG:4674', allow_override=True)
        
        # Converter para EPSG:4326
        try:
            if gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs('EPSG:4326')
        except:
            gdf = gdf.to_crs('EPSG:4326')
        
        # Resetar índice
        gdf = gdf.reset_index(drop=True)
        
        # Validar geometrias
        gdf = gdf[gdf['geometry'].notnull() & gdf['geometry'].is_valid].copy()
        
        # Resetar índice novamente após filtragem
        gdf = gdf.reset_index(drop=True)
        
        # Mapear colunas para padrão (case-insensitive)
        rename_map = {}
        for col in gdf.columns:
            col_upper = col.upper()
            if col_upper in ['ESTADO', 'UF', 'STATE']:
                rename_map[col] = 'ESTADO'
            elif col_upper in ['MUNICIPIO', 'CITY']:
                rename_map[col] = 'MUNICIPIO'
            elif col_upper in ['AREAHA', 'AREA', 'ALERTHA']:
                rename_map[col] = 'AREAHA'
            elif col_upper in ['ANODETEC', 'ANO', 'DETECTYEAR']:
                rename_map[col] = 'ANODETEC'
            elif col_upper in ['DATADETEC', 'DATA', 'DETECTAT']:
                rename_map[col] = 'DATADETEC'
            elif col_upper in ['BIOME', 'BIOMA']:
                rename_map[col] = 'BIOMA'
            elif col_upper in ['CODEALERTA', 'ALERTCODE', 'ALERTID']:
                rename_map[col] = 'CODEALERTA'
        
        gdf = gdf.rename(columns=rename_map)
        
        # Processar coluna ESTADO
        if 'ESTADO' in gdf.columns:
            gdf['ESTADO'] = gdf['ESTADO'].apply(normalizar_estado)
            gdf = gdf[gdf['ESTADO'].notna()].copy()
            # Resetar índice após filtragem por ESTADO
            gdf = gdf.reset_index(drop=True)
        else:
            st.error(f"❌ Erro: Arquivo {caminho} não possui coluna de ESTADO")
            return gpd.GeoDataFrame()
        
        # Garantir colunas essenciais existem
        for col in ['MUNICIPIO', 'AREAHA', 'ANODETEC', 'DATADETEC', 'CODEALERTA', 'BIOMA']:
            if col not in gdf.columns:
                gdf[col] = None
        
        # Otimizar tipos de dados para economizar memória
        if 'AREAHA' in gdf.columns:
            gdf['AREAHA'] = pd.to_numeric(gdf['AREAHA'], errors='coerce').fillna(0).astype('float32')
        if 'ANODETEC' in gdf.columns:
            gdf['ANODETEC'] = pd.to_numeric(gdf['ANODETEC'], errors='coerce').fillna(0).astype('int16')
        
        # Adicionar identificador de origem
        gdf['origem'] = tipo_origem
        
        # Garantir ID único
        if 'id_alerta' not in gdf.columns:
            # Simplesmente criar IDs baseados no tipo de origem e índice
            gdf['id_alerta'] = [f"{tipo_origem}_{i}" for i in range(len(gdf))]
        
        return gdf
        
    except Exception as e:
        st.error(f"❌ Erro ao carregar {caminho}: {str(e)}")
        import traceback
        st.error(f"Detalhes: {traceback.format_exc()}")
        return gpd.GeoDataFrame()


@st.cache_resource(show_spinner="Carregando todos os alertas...")
def carregar_todos_alertas():
    """
    Carrega todos os arquivos de alertas dos shapefiles locais e combina em um único GeoDataFrame.
    Usa cache_resource para dados estáticos.
    
    Returns:
        GeoDataFrame com todos os alertas combinados
    """
    import os
    
    # Carregar cada arquivo separadamente (APENAS SHAPEFILES LOCAIS)
    gdf_para = carregar_alerta_shapefile("alertas.shp", "Pará")
    gdf_estados = carregar_alerta_shapefile("Filtrado/Alertas_Estados_Restantes.shp", "Estados")
    gdf_ti = carregar_alerta_shapefile("Filtrado/Alertas_Outros.shp", "TI")
    
    # Combinar todos os dataframes
    lista_gdfs = [gdf_para, gdf_estados, gdf_ti]
    lista_gdfs = [gdf for gdf in lista_gdfs if not gdf.empty]
    
    if not lista_gdfs:
        st.error("❌ Nenhum arquivo de alertas foi carregado com sucesso!")
        return gpd.GeoDataFrame()
    
    # Limpar cada GeoDataFrame individualmente antes de concatenar
    lista_gdfs_limpos = []
    for gdf in lista_gdfs:
        # Resetar índice de linhas
        gdf = gdf.reset_index(drop=True)
        
        # Remover colunas duplicadas (manter a primeira ocorrência)
        gdf = gdf.loc[:, ~gdf.columns.duplicated()]
        
        lista_gdfs_limpos.append(gdf)
    
    # Concatenar usando método mais robusto
    gdf_combinado = gpd.GeoDataFrame(pd.concat(lista_gdfs_limpos, ignore_index=True, sort=False))
    
    # Recriar IDs únicos após combinação para evitar duplicatas
    gdf_combinado['id_alerta'] = [f"alerta_{i}" for i in range(len(gdf_combinado))]
    
    return gdf_combinado


def filtrar_alertas_por_estado(gdf_alertas, estado):
    """
    Filtra alertas por estado
    
    Args:
        gdf_alertas: GeoDataFrame com alertas
        estado: Nome do estado para filtrar
    
    Returns:
        GeoDataFrame filtrado
    """
    if gdf_alertas.empty or 'ESTADO' not in gdf_alertas.columns:
        return gpd.GeoDataFrame()
    
    return gdf_alertas[gdf_alertas['ESTADO'] == estado].copy()


def filtrar_alertas_por_ano(gdf_alertas, ano):
    """
    Filtra alertas por ano de detecção
    
    Args:
        gdf_alertas: GeoDataFrame com alertas
        ano: Ano para filtrar (ou 'Todos')
    
    Returns:
        GeoDataFrame filtrado
    """
    if gdf_alertas.empty:
        return gpd.GeoDataFrame()
    
    if ano == 'Todos':
        return gdf_alertas.copy()
    
    if 'ANODETEC' not in gdf_alertas.columns:
        return gdf_alertas.copy()
    
    return gdf_alertas[gdf_alertas['ANODETEC'] == ano].copy()
