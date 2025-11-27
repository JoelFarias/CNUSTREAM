import os
import numpy as np
import pandas as pd
import geopandas as gpd
import streamlit as st
from sqlalchemy import create_engine
import requests
from shapely import wkt

# Configuração PostgreSQL (local)
DB_CONFIG = {
    'host': 'db.rjnzsfvxqvygkyusmsan.supabase.co',
    'port': 5432,
    'database': 'postgres',
    'user': 'postgres',
    'password': 'jB5kgYN6DZF6pdRm'
}

# Supabase REST API (fallback para IPv6/Cloud)
SUPABASE_URL = 'https://rjnzsfvxqvygkyusmsan.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJqbnpzZnZ4cXZ5Z2t5dXNtc2FuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzI1NTY3NDAsImV4cCI6MjA0ODEzMjc0MH0.D3AvXN-zvPcGdH1HNLzQSh3qTYFEcAARUbHOg73s0o4'

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
    Carrega dados do CAR - tenta PostgreSQL, fallback para REST API.
    """
    # Tentar PostgreSQL primeiro
    try:
        engine = create_engine(
            f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@"
            f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}",
            connect_args={'connect_timeout': 3}
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
        
        gdf = gpd.read_postgis(query, engine, geom_col='geometry')
        
        if not gdf.empty:
            if gdf.crs is None:
                gdf.set_crs("EPSG:4674", inplace=True)
            gdf = gdf.to_crs("EPSG:4326")
            gdf["geometry"] = gdf["geometry"].apply(
                lambda geom: geom.buffer(0) if geom and not geom.is_valid else geom
            )
            gdf = gdf[gdf["geometry"].notnull() & gdf["geometry"].is_valid]
            gdf['invadindo'] = 'CAR'
            if 'num_area' in gdf.columns:
                gdf['num_area'] = pd.to_numeric(gdf['num_area'], errors='coerce').fillna(0)
            if 'id' in gdf.columns:
                gdf = gdf.rename(columns={'id': 'id_car'})
            return gdf
    except:
        pass
    
    # Fallback: REST API
    try:
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Prefer': 'return=representation'
        }
        
        response = requests.get(
            f'{SUPABASE_URL}/rest/v1/Resultado_CAR_Final',
            headers=headers,
            params={'select': 'id,municipio,cod_estado,num_area,geom'},
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            if data:
                df = pd.DataFrame(data)
                df['geometry'] = df['geom'].apply(lambda x: wkt.loads(x) if isinstance(x, str) else x)
                gdf = gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:4674')
                gdf = gdf.drop(columns=['geom'], errors='ignore')
                gdf = gdf.to_crs('EPSG:4326')
                gdf['invadindo'] = 'CAR'
                if 'num_area' in gdf.columns:
                    gdf['num_area'] = pd.to_numeric(gdf['num_area'], errors='coerce').fillna(0)
                if 'id' in gdf.columns:
                    gdf = gdf.rename(columns={'id': 'id_car'})
                return gdf
    except:
        pass
    
    return gpd.GeoDataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def carregar_alertas_postgres() -> gpd.GeoDataFrame:
    """
    Carrega alertas - tenta PostgreSQL, fallback para REST API.
    """
    # Tentar PostgreSQL primeiro
    try:
        engine = create_engine(
            f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@"
            f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}",
            connect_args={'connect_timeout': 3}
        )
        
        query = """
            SELECT 
                *,
                geom as geometry
            FROM extensions."Alertas_Estados_Restantes"
        """
        
        gdf = gpd.read_postgis(query, engine, geom_col='geometry')
        
        if not gdf.empty:
            if gdf.crs is None:
                gdf.set_crs("EPSG:4674", inplace=True)
            if gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs("EPSG:4326")
            gdf["geometry"] = gdf["geometry"].apply(
                lambda geom: geom.buffer(0) if geom and not geom.is_valid else geom
            )
            gdf = gdf[gdf["geometry"].notnull() & gdf["geometry"].is_valid]
            if 'AREAHA' in gdf.columns:
                gdf['AREAHA'] = pd.to_numeric(gdf['AREAHA'], errors='coerce').fillna(0)
            if 'ANODETEC' in gdf.columns:
                gdf['ANODETEC'] = pd.to_numeric(gdf['ANODETEC'], errors='coerce')
            gdf['origem'] = 'PostgreSQL - Estados Restantes'
            return gdf
    except:
        pass
    
    # Fallback: REST API
    try:
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Prefer': 'return=representation'
        }
        
        response = requests.get(
            f'{SUPABASE_URL}/rest/v1/Alertas_Estados_Restantes',
            headers=headers,
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            if data:
                df = pd.DataFrame(data)
                df['geometry'] = df['geom'].apply(lambda x: wkt.loads(x) if isinstance(x, str) else x)
                gdf = gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:4674')
                gdf = gdf.drop(columns=['geom'], errors='ignore')
                gdf = gdf.to_crs('EPSG:4326')
                if 'AREAHA' in gdf.columns:
                    gdf['AREAHA'] = pd.to_numeric(gdf['AREAHA'], errors='coerce').fillna(0)
                if 'ANODETEC' in gdf.columns:
                    gdf['ANODETEC'] = pd.to_numeric(gdf['ANODETEC'], errors='coerce')
                gdf['origem'] = 'PostgreSQL - Estados Restantes'
                return gdf
    except:
        pass
    
    return gpd.GeoDataFrame()
