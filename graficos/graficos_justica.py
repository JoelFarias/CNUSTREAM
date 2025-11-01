import pandas as pd
import geopandas as gpd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from shapely.geometry import Point
from utilitarios.formatacao import formatar_numero_com_pontos
from utilitarios.estilos import aplicar_layout as _apply_layout


def fig_justica(df_proc: pd.DataFrame) -> dict:
    figs = {'mun': None, 'class': None, 'ass': None, 'org': None, 'temp': None}
    
    try:
        if df_proc.empty:
            return figs
        
        if 'municipio' in df_proc.columns:
            top_municipios = df_proc['municipio'].value_counts().head(10).sort_values(ascending=True)
            if not top_municipios.empty:
                municipios_text = [formatar_numero_com_pontos(val, 0) for val in top_municipios.values]
                fig_mun = go.Figure()
                fig_mun.add_trace(go.Bar(
                    x=top_municipios.values,
                    y=top_municipios.index,
                    orientation='h',
                    text=municipios_text,
                    textposition='auto',
                    marker_color='lightblue',
                    hovertemplate='<b>%{y}</b><br>Processos: %{text}<extra></extra>'
                ))
                fig_mun.update_layout(
                    title="Top 10 Municípios por Número de Processos",
                    xaxis_title="Número de Processos",
                    yaxis_title="Município",
                    height=400,
                    margin=dict(l=120, r=80, t=50, b=40)
                )
                figs['mun'] = _apply_layout(fig_mun, "Top 10 Municípios")
        
        if 'classe' in df_proc.columns:
            top_classes = df_proc['classe'].value_counts().head(10).sort_values(ascending=True)
            if not top_classes.empty:
                classes_text = [formatar_numero_com_pontos(val, 0) for val in top_classes.values]
                fig_class = go.Figure()
                fig_class.add_trace(go.Bar(
                    x=top_classes.values,
                    y=top_classes.index,
                    orientation='h',
                    text=classes_text,
                    textposition='auto',
                    marker_color='lightgreen',
                    hovertemplate='<b>%{y}</b><br>Processos: %{text}<extra></extra>'
                ))
                fig_class.update_layout(
                    title="Top 10 Classes Processuais",
                    xaxis_title="Número de Processos",
                    yaxis_title="Classe",
                    height=400,
                    margin=dict(l=150, r=80, t=50, b=40)
                )
                figs['class'] = _apply_layout(fig_class, "Top 10 Classes")
        
        if 'assuntos' in df_proc.columns:
            top_assuntos = df_proc['assuntos'].value_counts().head(10).sort_values(ascending=True)
            if not top_assuntos.empty:
                assuntos_text = [formatar_numero_com_pontos(val, 0) for val in top_assuntos.values]
                fig_ass = go.Figure()
                fig_ass.add_trace(go.Bar(
                    x=top_assuntos.values,
                    y=top_assuntos.index,
                    orientation='h',
                    text=assuntos_text,
                    textposition='auto',
                    marker_color='orange',
                    hovertemplate='<b>%{y}</b><br>Processos: %{text}<extra></extra>'
                ))
                fig_ass.update_layout(
                    title="Top 10 Assuntos",
                    xaxis_title="Número de Processos",
                    yaxis_title="Assunto",
                    height=400,
                    margin=dict(l=180, r=80, t=50, b=40)
                )
                figs['ass'] = _apply_layout(fig_ass, "Top 10 Assuntos")
        
        if 'orgao_julgador' in df_proc.columns:
            top_orgaos = df_proc['orgao_julgador'].value_counts().head(10).sort_values(ascending=True)
            if not top_orgaos.empty:
                orgaos_text = [formatar_numero_com_pontos(val, 0) for val in top_orgaos.values]
                fig_org = go.Figure()
                fig_org.add_trace(go.Bar(
                    x=top_orgaos.values,
                    y=top_orgaos.index,
                    orientation='h',
                    text=orgaos_text,
                    textposition='auto',
                    marker_color='purple',
                    hovertemplate='<b>%{y}</b><br>Processos: %{text}<extra></extra>'
                ))
                fig_org.update_layout(
                    title="Top 10 Órgãos Julgadores",
                    xaxis_title="Número de Processos",
                    yaxis_title="Órgão",
                    height=400,
                    margin=dict(l=200, r=80, t=50, b=40)
                )
                figs['org'] = _apply_layout(fig_org, "Top 10 Órgãos")
        
        if 'data_ajuizamento' in df_proc.columns:
            df_proc['data_ajuizamento'] = pd.to_datetime(df_proc['data_ajuizamento'], errors='coerce')
            df_validas = df_proc.dropna(subset=['data_ajuizamento'])
            if not df_validas.empty:
                df_temporal = df_validas.set_index('data_ajuizamento').resample('M').size().reset_index()
                df_temporal.columns = ['data', 'quantidade']
                
                if not df_temporal.empty:
                    fig_temp = px.line(
                        df_temporal,
                        x='data',
                        y='quantidade',
                        title='Evolução Temporal dos Processos',
                        markers=True
                    )
                    fig_temp.update_layout(
                        xaxis_title="Data",
                        yaxis_title="Número de Processos"
                    )
                    figs['temp'] = _apply_layout(fig_temp, "Evolução Temporal")
        
    except Exception as e:
        st.warning(f"Erro ao criar gráficos de justiça: {e}")
    
    return figs


def fig_focos_calor_por_uc(df_focos: pd.DataFrame, gdf_cnuc: gpd.GeoDataFrame) -> go.Figure:
    try:
        if df_focos.empty or gdf_cnuc.empty:
            return go.Figure()
        
        df_valid = df_focos.dropna(subset=['Latitude', 'Longitude']).copy()
        if df_valid.empty:
            return go.Figure()
        
        geometry = [Point(lon, lat) for lon, lat in zip(df_valid['Longitude'], df_valid['Latitude'])]
        gdf_focos = gpd.GeoDataFrame(df_valid, geometry=geometry, crs="EPSG:4326")
        
        crs_proj = "EPSG:31983"
        gdf_focos_proj = gdf_focos.to_crs(crs_proj)
        gdf_cnuc_proj = gdf_cnuc.to_crs(crs_proj)
        
        focos_in_ucs = gpd.sjoin(gdf_focos_proj, gdf_cnuc_proj, how="inner", predicate="intersects")
        
        if focos_in_ucs.empty:
            return go.Figure()
        
        focos_por_uc = focos_in_ucs.groupby('nome_uc', observed=False).size().reset_index(name='quantidade_focos')
        focos_por_uc = focos_por_uc.sort_values('quantidade_focos', ascending=False).head(10)
        
        if focos_por_uc.empty:
            return go.Figure()
        
        focos_por_uc = focos_por_uc.sort_values('quantidade_focos', ascending=True)
        
        focos_text = [formatar_numero_com_pontos(val, 0) for val in focos_por_uc['quantidade_focos']]
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=focos_por_uc['quantidade_focos'],
            y=focos_por_uc['nome_uc'],
            orientation='h',
            text=focos_text,
            textposition='auto',
            marker_color='red',
            hovertemplate='<b>%{y}</b><br>Focos: %{text}<extra></extra>'
        ))
        
        fig.update_layout(
            title="Top 10 UCs com Mais Focos de Calor",
            xaxis_title="Quantidade de Focos",
            yaxis_title="Unidade de Conservação",
            height=500,
            margin=dict(l=150, r=80, t=50, b=40)
        )
        
        return _apply_layout(fig, "Focos de Calor por UC")
        
    except Exception as e:
        st.warning(f"Erro ao criar gráfico de focos por UC: {e}")
        return go.Figure()
