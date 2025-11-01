import streamlit as st
import pandas as pd
import geopandas as gpd
import gc


@st.cache_data(ttl=3600, show_spinner=False, max_entries=1)
def processar_dados_desmatamento(_gdf_alertas, ano_selecionado):
    if ano_selecionado != 'Todos':
        gdf_filtrado = _gdf_alertas[_gdf_alertas['ANODETEC'] == ano_selecionado].copy()
    else:
        gdf_filtrado = _gdf_alertas.copy()
    
    if 'AREAHA' in gdf_filtrado.columns:
        gdf_filtrado['AREAHA'] = pd.to_numeric(gdf_filtrado['AREAHA'], errors='coerce')

    gc.collect()
    return gdf_filtrado


@st.cache_data(ttl=3600, show_spinner=False, max_entries=1)
def calcular_ranking_municipios_desmatamento(_gdf_alertas):
    required_ranking_cols = ['ESTADO', 'MUNICIPIO', 'AREAHA', 'ANODETEC', 'BIOMA', 'VPRESSAO']
    if not all(col in _gdf_alertas.columns for col in required_ranking_cols):
        return pd.DataFrame()
    
    _gdf_alertas['AREAHA'] = pd.to_numeric(_gdf_alertas['AREAHA'], errors='coerce')
    
    ranking_municipios = _gdf_alertas.groupby(['ESTADO', 'MUNICIPIO'], observed=False).agg({
        'AREAHA': ['sum', 'count', 'mean'],
        'ANODETEC': ['min', 'max'],
        'BIOMA': lambda x: x.mode().iloc[0] if not x.empty and x.mode().size > 0 else 'N/A',
        'VPRESSAO': lambda x: x.mode().iloc[0] if not x.empty and x.mode().size > 0 else 'N/A'
    }).round(2)
    
    ranking_municipios.columns = ['Área Total (ha)', 'Qtd Alertas', 'Área Média (ha)',
                                  'Ano Min', 'Ano Max', 'Bioma Principal', 'Vetor Pressão']
    
    ranking_municipios = ranking_municipios.reset_index()
    ranking_municipios = ranking_municipios.sort_values('Área Total (ha)', ascending=False)
    ranking_municipios.insert(0, 'Posição', range(1, len(ranking_municipios) + 1))
    
    return ranking_municipios


@st.cache_data(ttl=3600, show_spinner=False, max_entries=3)
def obter_anos_disponiveis_desmatamento(_gdf_alertas):
    if _gdf_alertas.empty or 'ANODETEC' not in _gdf_alertas.columns:
        return ['Todos']
    return ['Todos'] + sorted(_gdf_alertas['ANODETEC'].dropna().unique().tolist())


@st.cache_data(ttl=3600, show_spinner=False, max_entries=1)
def preprocessar_dados_desmatamento_temporal(_gdf_alertas):
    if _gdf_alertas.empty:
        return pd.DataFrame()
    
    temporal_data = _gdf_alertas.copy()
    if 'AREAHA' in temporal_data.columns:
        temporal_data['AREAHA'] = pd.to_numeric(temporal_data['AREAHA'], errors='coerce')
    
    gc.collect()
    return temporal_data


@st.cache_data(ttl=3600, show_spinner=False, max_entries=1)
def calcular_bounds_desmatamento(_gdf_alertas):
    if _gdf_alertas.empty:
        return None
    
    try:
        minx, miny, maxx, maxy = _gdf_alertas.total_bounds
        return {'lat': (miny + maxy) / 2, 'lon': (minx + maxx) / 2, 'bounds': (minx, miny, maxx, maxy)}
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False, max_entries=1)
def processar_intersecao_uc_desmatamento(_gdf_cnuc, _gdf_alertas):
    if _gdf_cnuc.empty or _gdf_alertas.empty:
        return pd.DataFrame()
    
    try:
        crs_proj = "EPSG:31983"
        gdf_cnuc_proj = _gdf_cnuc.to_crs(crs_proj)
        gdf_alertas_proj = _gdf_alertas.to_crs(crs_proj)
        
        alerts_in_ucs = gpd.sjoin(gdf_alertas_proj, gdf_cnuc_proj, how="inner", predicate="intersects")
        
        if alerts_in_ucs.empty:
            return pd.DataFrame()
        
        alert_area_per_uc = alerts_in_ucs.groupby('nome_uc', observed=False)['AREAHA'].sum().reset_index()
        alert_area_per_uc.columns = ['nome_uc', 'alerta_ha_total']
        alert_area_per_uc = alert_area_per_uc.sort_values('alerta_ha_total', ascending=False)
        del gdf_cnuc_proj, gdf_alertas_proj, alerts_in_ucs
        gc.collect()
        
        return alert_area_per_uc
    except Exception:
        return pd.DataFrame()
