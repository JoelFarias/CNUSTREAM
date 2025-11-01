import os
import numpy as np
import pandas as pd
import geopandas as gpd
import streamlit as st

@st.cache_data
def carregar_shapefile_cloud_seguro(caminho: str, calcular_percentuais: bool = True, colunas: list[str] = None) -> gpd.GeoDataFrame:
    try:
        if not os.path.exists(caminho):
            st.error(f"❌ Arquivo não encontrado: {caminho}")
            return gpd.GeoDataFrame()
        
        gdf = gpd.read_file(caminho)
        
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
    
    if 'ha_total' not in gdf2.columns and 'area_km2' in gdf2.columns:
        gdf2['ha_total'] = gdf2.get('area_km2', 0) * 100
        gdf2['ha_total'] = pd.to_numeric(gdf2['ha_total'], downcast='float', errors='coerce')
    
    for col in ['alerta_ha', 'sigef_ha', 'area_ha']:
         if col in gdf2.columns and gdf2[col].dtype == 'float64':
            gdf2[col] = pd.to_numeric(gdf2[col], downcast='float', errors='ignore')
         elif col in gdf2.columns and gdf2[col].dtype == 'int64':
            gdf2[col] = pd.to_numeric(gdf2[col], downcast='integer', errors='ignore')

    return gdf2
