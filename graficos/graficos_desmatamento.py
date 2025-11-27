import pandas as pd
import geopandas as gpd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
import numpy as np
from utilitarios.formatacao import formatar_numero_com_pontos
from utilitarios.estilos import aplicar_layout as _apply_layout
from graficos.graficos_sobreposicoes import wrap_label


def fig_desmatamento_uc(gdf_cnuc_filtered: gpd.GeoDataFrame, gdf_alertas_filtered: gpd.GeoDataFrame) -> go.Figure:
    if gdf_cnuc_filtered.empty or gdf_alertas_filtered.empty:
        return go.Figure() 

    crs_proj = "EPSG:31983" 
    gdf_cnuc_proj = gdf_cnuc_filtered.to_crs(crs_proj)
    gdf_alertas_proj = gdf_alertas_filtered.to_crs(crs_proj)

    if not gdf_alertas_proj.empty and not gdf_cnuc_proj.empty:
        alerts_in_ucs = gpd.sjoin(gdf_alertas_proj, gdf_cnuc_proj, how="inner", predicate="intersects")
    else:
        alerts_in_ucs = gpd.GeoDataFrame()

    if alerts_in_ucs.empty:
         return go.Figure() 

    alert_area_per_uc = alerts_in_ucs.groupby('nome_uc', observed=False)['AREAHA'].sum().reset_index()
    alert_area_per_uc.columns = ['nome_uc', 'alerta_ha_total'] 
    alert_area_per_uc = alert_area_per_uc.sort_values('alerta_ha_total', ascending=False)
    alert_area_per_uc['uc_wrap'] = alert_area_per_uc['nome_uc'].apply(lambda x: wrap_label(x, 15)) 

    fig = px.bar(
        alert_area_per_uc,
        x='uc_wrap',
        y='alerta_ha_total',
        labels={"alerta_ha_total":"Área de Alertas (ha)","uc_wrap":"UC"},
        text_auto=True,
    )

    alerta_text = [formatar_numero_com_pontos(val, 0) for val in alert_area_per_uc['alerta_ha_total']]
    fig.update_traces(
        customdata=np.stack([alerta_text, alert_area_per_uc.nome_uc], axis=-1),
        hovertemplate="<b>%{customdata[1]}</b><br>Área de Alertas: %{customdata[0]} ha<extra></extra>",
        text=alerta_text, 
        textposition="outside", 
        marker_line_color="rgb(80,80,80)",
        marker_line_width=0.5,
        cliponaxis=False
    )

    max_val = alert_area_per_uc["alerta_ha_total"].max()
    fig.update_xaxes(tickangle=0, tickfont=dict(size=9), title_text="")
    fig.update_yaxes(title_text="Área (ha)", tickfont=dict(size=9), range=[0, max_val * 1.2])
    fig.update_layout(height=450, margin=dict(l=80, r=80, t=100, b=80), showlegend=False) 
    fig = _apply_layout(fig, titulo="Área de Alertas (Desmatamento) por UC", tamanho_titulo=16)
    return fig


def fig_desmatamento_temporal(gdf_alertas_filtered: gpd.GeoDataFrame) -> go.Figure:
    if gdf_alertas_filtered.empty or 'DATADETEC' not in gdf_alertas_filtered.columns:
        fig = go.Figure()
        fig.update_layout(title="Evolução Temporal de Alertas (Desmatamento)", xaxis_title="Data", yaxis_title="Área (ha)")
        return _apply_layout(fig, titulo="Evolução Temporal de Alertas (Desmatamento)", tamanho_titulo=16)

    gdf_alertas_filtered['DATADETEC'] = pd.to_datetime(gdf_alertas_filtered['DATADETEC'], errors='coerce')
    gdf_alertas_filtered['AREAHA'] = pd.to_numeric(gdf_alertas_filtered['AREAHA'], errors='coerce')
    df_valid_dates = gdf_alertas_filtered.dropna(subset=['DATADETEC', 'AREAHA'])

    if df_valid_dates.empty:
         fig = go.Figure()
         fig.update_layout(title="Evolução Temporal de Alertas (Desmatamento)", xaxis_title="Data", yaxis_title="Área (ha)")
         return _apply_layout(fig, titulo="Evolução Temporal de Alertas (Desmatamento)", tamanho_titulo=16)

    df_monthly = df_valid_dates.set_index('DATADETEC').resample('ME')['AREAHA'].sum().reset_index()
    df_monthly['DATADETEC'] = df_monthly['DATADETEC'].dt.to_period('M').astype(str)

    fig = px.line(df_monthly, x='DATADETEC', y='AREAHA', labels={"AREAHA":"Área (ha)","DATADETEC":"Mês/Ano"}, markers=True, text='AREAHA')
    area_text = [formatar_numero_com_pontos(val, 0) for val in df_monthly['AREAHA']]
    fig.update_traces(
        mode='lines+markers+text',
        textposition='top center',
        text=area_text,
        hovertemplate="Mês/Ano: %{x}<br>Área de Alertas: %{text} ha<extra></extra>",
        customdata=area_text
    )

    fig.update_xaxes(title_text="Mês/Ano", tickangle=45)
    fig.update_yaxes(title_text="Área (ha)")
    fig.update_layout(height=400)
    fig = _apply_layout(fig, titulo="Evolução Mensal de Alertas (Desmatamento)", tamanho_titulo=16)
    return fig


def fig_desmatamento_municipio(gdf_alertas_filtered: gpd.GeoDataFrame) -> go.Figure:
    df = gdf_alertas_filtered.sort_values('AREAHA', ascending=False)
    if df.empty:
        return go.Figure()

    area_text = [formatar_numero_com_pontos(val, 0) for val in df['AREAHA']]
    fig = px.bar(df, x='AREAHA', y='MUNICIPIO', orientation='h', text='AREAHA', labels={'AREAHA': 'Área (ha)', 'MUNICIPIO': ''})
    fig = _apply_layout(fig, titulo="Desmatamento por Município")
    fig.update_layout(yaxis=dict(autorange="reversed"), xaxis=dict(tickformat='~s'), margin=dict(l=80, r=100, t=50, b=20))
    fig.update_traces(
        text=area_text,
        textposition='outside',
        cliponaxis=False,
        marker_line_color='rgb(80,80,80)',
        marker_line_width=0.5,
        hovertemplate='<b>%{y}</b><br>Área: %{text} ha<extra></extra>',
        customdata=area_text
    )
    return fig


def fig_desmatamento_mapa_pontos(gdf_alertas_filtered: gpd.GeoDataFrame) -> go.Figure:
    if gdf_alertas_filtered.empty or 'AREAHA' not in gdf_alertas_filtered.columns or 'geometry' not in gdf_alertas_filtered.columns:
        fig = go.Figure()
        fig.update_layout(title="Mapa de Alertas (Desmatamento)")
        return _apply_layout(fig, titulo="Mapa de Alertas (Desmatamento)", tamanho_titulo=16)

    gdf_alertas_filtered['AREAHA'] = pd.to_numeric(gdf_alertas_filtered['AREAHA'], errors='coerce')

    try:
        gdf_proj = gdf_alertas_filtered.to_crs("EPSG:31983").copy()
        centroids_proj = gdf_proj.geometry.centroid
        centroids_geo = centroids_proj.to_crs("EPSG:4326")
        gdf_map = gdf_alertas_filtered.to_crs("EPSG:4326").copy()
        gdf_map['Latitude'] = centroids_geo.y
        gdf_map['Longitude'] = centroids_geo.x
    except Exception as e:
        st.warning(f"Erro ao calcular centroides: {e}")
        fig = go.Figure()
        fig.update_layout(title="Mapa de Alertas (Desmatamento)")
        return _apply_layout(fig, titulo="Mapa de Alertas (Desmatamento)", tamanho_titulo=16)

    gdf_map = gdf_map.dropna(subset=['Latitude', 'Longitude'])
    if gdf_map.empty:
        fig = go.Figure()
        fig.update_layout(title="Mapa de Alertas (Desmatamento)")
        return _apply_layout(fig, titulo="Mapa de Alertas (Desmatamento)", tamanho_titulo=16)

    minx, miny, maxx, maxy = gdf_map.total_bounds
    center = {'lat': (miny + maxy) / 2, 'lon': (minx + maxx) / 2}
    span_lat = maxy - miny
    lon_range = maxx - minx
    max_range = max(span_lat, lon_range, 0.01)

    zoom_level = 3.5
    if max_range < 0.1: zoom_level = 10
    elif max_range < 0.5: zoom_level = 8
    elif max_range < 1: zoom_level = 7
    elif max_range < 5: zoom_level = 5
    elif max_range < 10: zoom_level = 4
    elif max_range < 20: zoom_level = 3.5
    zoom_level = int(round(zoom_level))

    sample_size = 50000
    if len(gdf_map) > sample_size:
        gdf_map_plot = gdf_map.sample(sample_size, random_state=1)
    else:
        gdf_map_plot = gdf_map

    # Garantir que AREAHA não tem NaN (substituir por 0.01 para visualização)
    if 'AREAHA' in gdf_map_plot.columns:
        gdf_map_plot['AREAHA'] = pd.to_numeric(gdf_map_plot['AREAHA'], errors='coerce').fillna(0.01)
        # Remover valores zero ou negativos
        gdf_map_plot = gdf_map_plot[gdf_map_plot['AREAHA'] > 0]

    if gdf_map_plot.empty:
        fig = go.Figure()
        fig.update_layout(title="Mapa de Alertas (Desmatamento)")
        return _apply_layout(fig, titulo="Mapa de Alertas (Desmatamento)", tamanho_titulo=16)

    hover_name_col = None
    for col_candidate in ['CODEALERTA', 'id_alerta', 'MUNICIPIO']:
        if col_candidate in gdf_map_plot.columns:
            hover_name_col = col_candidate
            break
    
    hover_data_config = {
        'AREAHA': ':.2f ha',
        'Latitude': False,
        'Longitude': False
    }
    
    optional_hover_cols = ['MUNICIPIO', 'DATADETEC', 'ESTADO', 'BIOMA', 'VPRESSAO', 'ANODETEC']
    for col in optional_hover_cols:
        if col in gdf_map_plot.columns and col != hover_name_col:
            hover_data_config[col] = True

    scatter_map_kwargs = {
        'data_frame': gdf_map_plot,
        'lat': 'Latitude',
        'lon': 'Longitude',
        'size': 'AREAHA',
        'color': 'AREAHA',
        'color_continuous_scale': "Reds",
        'range_color': (0, gdf_map_plot['AREAHA'].quantile(0.95)),
        'hover_data': hover_data_config,
        'size_max': 15,
        'zoom': zoom_level,
        'center': center,
        'opacity': 0.7,
        'map_style': 'open-street-map'
    }
    
    if hover_name_col:
        scatter_map_kwargs['hover_name'] = hover_name_col

    fig = px.scatter_map(**scatter_map_kwargs)

    fig.update_traces(showlegend=False)
    fig.update_coloraxes(showscale=False)
    fig.update_layout(
        mapbox=dict(style='open-street-map', zoom=zoom_level, center=center),
        margin={"r":0,"t":0,"l":0,"b":0},
        hovermode='closest',
        showlegend=False
    )
    fig.update_mapboxes(style='open-street-map')
    return _apply_layout(fig, titulo="Mapa de Alertas (Desmatamento)", tamanho_titulo=16)
