import os
import numpy as np
import pandas as pd
import geopandas as gpd
import streamlit as st
from sqlalchemy import create_engine

# Configuração PostgreSQL para CAR e Alertas
# Usar pooler IPv6 para compatibilidade com Streamlit Cloud
DB_CONFIG = {
    'host': 'db.rjnzsfvxqvygkyusmsan.supabase.co',
    'port': 6543,  # Porta do pooler (transaction mode)
    'database': 'postgres',
    'user': 'postgres.rjnzsfvxqvygkyusmsan',  # Formato com projeto
    'password': 'jB5kgYN6DZF6pdRm'
}

@st.cache_data
def carregar_shapefile_cloud_seguro(caminho: str, calcular_percentuais: bool = True, colunas: list[str] = None) -> gpd.GeoDataFrame:
    try:
        if not os.path.exists(caminho):
            st.error(f"❌ Arquivo não encontrado: {caminho}")
            return gpd.GeoDataFrame()
        
        gdf = gpd.read_file(caminho)
        
        # Definir CRS se ausente (naive geometries)
        if gdf.crs is None:
            gdf = gdf.set_crs('EPSG:4674', allow_override=True)
        
        if gdf.empty:
            st.warning(f"⚠️ Shapefile vazio: {caminho}")
            return gpd.GeoDataFrame()
        
        gdf["geometry"] = gdf["geometry"].apply(lambda geom: geom.buffer(0) if geom and not geom.is_valid else geom)
        gdf = gdf[gdf["geometry"].notnull() & gdf["geometry"].is_valid]
        
        area_km2_calculada = False
        if "area_km2" not in gdf.columns:
            try:
                gdf_proj = gdf.to_crs("EPSG:31983")
                gdf["area_km2"] = gdf_proj.geometry.area / 1e6
                area_km2_calculada = True
            except Exception as e:
                st.warning(f"Erro ao calcular área: {e}")
        
        if colunas:
            colunas_com_geometry = list(set(colunas + ['geometry']))
            if area_km2_calculada and 'area_km2' not in colunas_com_geometry:
                colunas_com_geometry.append('area_km2')
            colunas_disponiveis = [col for col in colunas_com_geometry if col in gdf.columns]
            if colunas_disponiveis:
                colunas_disponiveis = [col for col in colunas_disponiveis if col != 'geometry'] + ['geometry']
                gdf = gdf[colunas_disponiveis]
        
        if calcular_percentuais and "area_km2" in gdf.columns:
            gdf["perc_alerta"] = (gdf.get("alerta_km2", 0) / gdf["area_km2"]) * 100
            gdf["perc_sigef"] = (gdf.get("sigef_km2", 0) / gdf["area_km2"]) * 100
            gdf["perc_alerta"] = gdf["perc_alerta"].replace([np.inf, -np.inf], np.nan).fillna(0)
            gdf["perc_sigef"] = gdf["perc_sigef"].replace([np.inf, -np.inf], np.nan).fillna(0)
        else:
            if "perc_alerta" not in gdf.columns:
                gdf["perc_alerta"] = 0
            if "perc_sigef" not in gdf.columns:
                gdf["perc_sigef"] = 0
        
        gdf["id"] = gdf.index.astype(str)
        
        for col in gdf.columns:
            if gdf[col].dtype == 'float64':
                gdf[col] = pd.to_numeric(gdf[col], downcast='float', errors='ignore')
            elif gdf[col].dtype == 'int64':
                gdf[col] = pd.to_numeric(gdf[col], downcast='integer', errors='ignore')
            elif gdf[col].dtype == 'object':
                if gdf[col].nunique() / len(gdf) < 0.5:
                    gdf[col] = gdf[col].astype('category')
        
        return gdf.to_crs("EPSG:4326")
        
    except Exception as e:
        st.error(f"❌ Erro ao carregar {caminho}: {str(e)}")
        return gpd.GeoDataFrame()

@st.cache_data
def carregar_shapefile(caminho: str, calcular_percentuais: bool = True, colunas: list[str] = None) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(caminho)
    
    # Definir CRS se ausente (naive geometries)
    if gdf.crs is None:
        gdf = gdf.set_crs('EPSG:4674', allow_override=True)
    
    if colunas:
        colunas_com_geometry = list(set(colunas + ['geometry']))
        colunas_disponiveis = [col for col in colunas_com_geometry if col in gdf.columns]
        if colunas_disponiveis:
            colunas_disponiveis = [col for col in colunas_disponiveis if col != 'geometry'] + ['geometry']
            gdf = gdf[colunas_disponiveis]
    
    gdf["geometry"] = gdf["geometry"].apply(lambda geom: geom.buffer(0) if geom and not geom.is_valid else geom)
    gdf = gdf[gdf["geometry"].notnull() & gdf["geometry"].is_valid]
    
    if "area_km2" in gdf.columns or calcular_percentuais:
        try:
            gdf_proj = gdf.to_crs("EPSG:31983")
            gdf["area_km2"] = gdf_proj.geometry.area / 1e6
        except Exception as e:
            st.warning(f"Erro ao calcular área: {e}")

    if calcular_percentuais and "area_km2" in gdf.columns:
        gdf["perc_alerta"] = (gdf.get("alerta_km2", 0) / gdf["area_km2"]) * 100
        gdf["perc_sigef"] = (gdf.get("sigef_km2", 0) / gdf["area_km2"]) * 100
        gdf["perc_alerta"] = gdf["perc_alerta"].replace([np.inf, -np.inf], np.nan).fillna(0)
        gdf["perc_sigef"] = gdf["perc_sigef"].replace([np.inf, -np.inf], np.nan).fillna(0)
    else:
        if "perc_alerta" not in gdf.columns:
            gdf["perc_alerta"] = 0
        if "perc_sigef" not in gdf.columns:
            gdf["perc_sigef"] = 0

    gdf["id"] = gdf.index.astype(str)

    for col in gdf.columns:
        if gdf[col].dtype == 'float64':
            gdf[col] = pd.to_numeric(gdf[col], downcast='float', errors='ignore')
        elif gdf[col].dtype == 'int64':
            gdf[col] = pd.to_numeric(gdf[col], downcast='integer', errors='ignore')
        elif gdf[col].dtype == 'object':
            if gdf[col].nunique() / len(gdf) < 0.5:
                gdf[col] = gdf[col].astype('category')

    return gdf.to_crs("EPSG:4326")

def preparar_hectares(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf2 = gdf.copy()
    gdf2['alerta_ha'] = gdf2.get('alerta_km2', 0) * 100
    gdf2['sigef_ha']  = gdf2.get('sigef_km2', 0)  * 100
    gdf2['area_ha']   = gdf2.get('area_km2', 0)   * 100
    
    # Se area_ha está zerado mas ha_total existe, use ha_total
    if 'ha_total' in gdf2.columns:
        mask_zero = (gdf2['area_ha'] == 0) | (gdf2['area_ha'].isna())
        gdf2.loc[mask_zero, 'area_ha'] = pd.to_numeric(gdf2.loc[mask_zero, 'ha_total'], errors='coerce').fillna(0)
    
    # Se num_area existe e area_ha ainda está zerado, use num_area
    if 'num_area' in gdf2.columns:
        mask_zero = (gdf2['area_ha'] == 0) | (gdf2['area_ha'].isna())
        gdf2.loc[mask_zero, 'area_ha'] = pd.to_numeric(gdf2.loc[mask_zero, 'num_area'], errors='coerce').fillna(0)
    
    # Garantir que area_ha seja numérico
    gdf2['area_ha'] = pd.to_numeric(gdf2['area_ha'], errors='coerce').fillna(0)
    gdf2['alerta_ha'] = pd.to_numeric(gdf2['alerta_ha'], errors='coerce').fillna(0)
    gdf2['sigef_ha'] = pd.to_numeric(gdf2['sigef_ha'], errors='coerce').fillna(0)
    
    if 'ha_total' not in gdf2.columns and 'area_km2' in gdf2.columns:
        gdf2['ha_total'] = gdf2.get('area_km2', 0) * 100
        gdf2['ha_total'] = pd.to_numeric(gdf2['ha_total'], downcast='float', errors='coerce')
    
    for col in ['alerta_ha', 'sigef_ha', 'area_ha']:
         if col in gdf2.columns and gdf2[col].dtype == 'float64':
            gdf2[col] = pd.to_numeric(gdf2[col], downcast='float', errors='ignore')
         elif col in gdf2.columns and gdf2[col].dtype == 'int64':
            gdf2[col] = pd.to_numeric(gdf2[col], downcast='integer', errors='ignore')

    return gdf2

@st.cache_data(ttl=3600, show_spinner=False)
def carregar_car_postgres() -> gpd.GeoDataFrame:
    """
    Carrega dados do CAR do PostgreSQL (todos os estados).
    Retorna GeoDataFrame com mesma estrutura do sigef.shp para compatibilidade.
    """
    try:
        # Debug: mostrar configuração
        st.info(f"🔍 Tentando conectar PostgreSQL: {DB_CONFIG['host']}:{DB_CONFIG['port']} como {DB_CONFIG['user']}")
        
        engine = create_engine(
            f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@"
            f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}",
            connect_args={'connect_timeout': 10}
        )
        
        query = """
            SELECT 
                id,
                municipio,
                cod_estado,
                num_area,
                geom as geometry
            FROM extensions."Resultado_CAR_Final"
        """
        
        st.info("📊 Executando query...")
        gdf = gpd.read_postgis(query, engine, geom_col='geometry')
        st.success(f"✅ CAR carregado: {len(gdf)} registros")
        
        if gdf.empty:
            st.warning("⚠️ Nenhum dado CAR encontrado no PostgreSQL")
            return gpd.GeoDataFrame()
        
        # Converter CRS
        if gdf.crs is None:
            gdf.set_crs("EPSG:4674", inplace=True)
        gdf = gdf.to_crs("EPSG:4326")
        
        # Validar geometrias
        gdf["geometry"] = gdf["geometry"].apply(
            lambda geom: geom.buffer(0) if geom and not geom.is_valid else geom
        )
        gdf = gdf[gdf["geometry"].notnull() & gdf["geometry"].is_valid]
        
        # Adicionar coluna 'invadindo' = 'CAR' (compatibilidade com sigef.shp)
        gdf['invadindo'] = 'CAR'
        
        # Converter num_area para numérico
        if 'num_area' in gdf.columns:
            gdf['num_area'] = pd.to_numeric(gdf['num_area'], errors='coerce').fillna(0)
        
        # Renomear id para evitar conflito
        if 'id' in gdf.columns:
            gdf = gdf.rename(columns={'id': 'id_car'})
        
        return gdf
        
    except Exception as e:
        st.error(f"❌ Erro PostgreSQL CAR: {type(e).__name__}: {str(e)}")
        return gpd.GeoDataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def carregar_alertas_postgres() -> gpd.GeoDataFrame:
    """
    Carrega dados de alertas de desmatamento do PostgreSQL.
    Tabela: Alertas_Estados_Restantes no mesmo schema/base do CAR.
    """
    try:
        st.info(f"🔍 Tentando conectar PostgreSQL Alertas: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        
        engine = create_engine(
            f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@"
            f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}",
            connect_args={'connect_timeout': 10}
        )
        
        query = """
            SELECT 
                *,
                geom as geometry
            FROM extensions."Alertas_Estados_Restantes"
        """
        
        st.info("📊 Executando query alertas...")
        gdf = gpd.read_postgis(query, engine, geom_col='geometry')
        st.success(f"✅ Alertas carregados: {len(gdf)} registros")
        
        if gdf.empty:
            st.warning("⚠️ Nenhum dado de alertas encontrado no PostgreSQL")
            return gpd.GeoDataFrame()
        
        # Converter CRS para EPSG:4326 (WGS 84)
        if gdf.crs is None:
            gdf.set_crs("EPSG:4674", inplace=True)
        
        if gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs("EPSG:4326")
        
        # Validar geometrias
        gdf["geometry"] = gdf["geometry"].apply(
            lambda geom: geom.buffer(0) if geom and not geom.is_valid else geom
        )
        gdf = gdf[gdf["geometry"].notnull() & gdf["geometry"].is_valid]
        
        # Normalizar colunas importantes
        if 'AREAHA' in gdf.columns:
            gdf['AREAHA'] = pd.to_numeric(gdf['AREAHA'], errors='coerce').fillna(0)
        
        if 'ANODETEC' in gdf.columns:
            gdf['ANODETEC'] = pd.to_numeric(gdf['ANODETEC'], errors='coerce')
        
        # Adicionar coluna de origem para rastreabilidade
        gdf['origem'] = 'PostgreSQL - Estados Restantes'
        
        return gdf
        
    except Exception as e:
        st.error(f"❌ Erro PostgreSQL Alertas: {type(e).__name__}: {str(e)}")
        return gpd.GeoDataFrame()
