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

@st.cache_resource(show_spinner="Carregando dados do CAR...")
def carregar_car_postgres() -> gpd.GeoDataFrame:
    """
    Carrega dados do CAR dos shapefiles locais (Git LFS).
    Usa cache_resource para dados estáticos que não mudam.
    """
    caminho = "Filtrado/Resultado_CAR_Final.shp"
    
    if not os.path.exists(caminho):
        st.error(f"❌ Arquivo CAR não encontrado: {caminho}")
        return gpd.GeoDataFrame()
    
    try:
        gdf = gpd.read_file(caminho)
        
        if gdf.empty:
            st.error(f"❌ Arquivo CAR vazio: {caminho}")
            return gpd.GeoDataFrame()
        
        if gdf.crs is None:
            gdf.set_crs("EPSG:4674", inplace=True)
        if gdf.crs.to_epsg() != 4326:
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
        
    except Exception as e:
        st.error(f"❌ Erro ao carregar CAR: {str(e)}")
        return gpd.GeoDataFrame()


@st.cache_resource(show_spinner="Carregando dados de alertas...")
def carregar_alertas_postgres() -> gpd.GeoDataFrame:
    """
    Carrega alertas dos shapefiles locais (Git LFS).
    Usa cache_resource para dados estáticos que não mudam.
    """
    caminho = "Filtrado/Alertas_Estados_Restantes.shp"
    
    if not os.path.exists(caminho):
        st.error(f"❌ Arquivo de alertas não encontrado: {caminho}")
        return gpd.GeoDataFrame()
    
    try:
        gdf = gpd.read_file(caminho)
        
        if gdf.empty:
            st.error(f"❌ Arquivo de alertas vazio: {caminho}")
            return gpd.GeoDataFrame()
        
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
        
        gdf['origem'] = 'Shapefile - Estados Restantes'
        
        return gdf
        
    except Exception as e:
        st.error(f"❌ Erro ao carregar alertas: {str(e)}")
        return gpd.GeoDataFrame()
