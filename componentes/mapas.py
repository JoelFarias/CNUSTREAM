import pandas as pd
import geopandas as gpd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


def criar_figura(gdf_cnuc_filtered, gdf_sigef_filtered, df_csv_filtered, centro, ids_selecionados, invadindo_opcao):
    try:
        fig = px.choropleth_map(
            gdf_cnuc_filtered,
            geojson=gdf_cnuc_filtered.__geo_interface__,
            locations=gdf_cnuc_filtered.index,
            color=np.ones(len(gdf_cnuc_filtered)),
            color_continuous_scale=[[0, "rgba(34,139,34,0.6)"], [1, "rgba(34,139,34,0.6)"]],
            map_style="open-street-map",
            zoom=5,
            center=centro,
            opacity=0.7,
            hover_data={
                'nome_uc': True,
                'municipio': True,
                'area_km2': ':.2f',
                'alerta_km2': ':.2f',
                'sigef_km2': ':.2f'
            }
        )
        fig.update_coloraxes(showscale=False)
        fig.update_traces(
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>" +
                "Município: %{customdata[1]}<br>" +
                "Área: %{customdata[2]:.2f} km²<br>" +
                "Alertas: %{customdata[3]:.2f} km²<br>" +
                "CAR: %{customdata[4]:.2f} km²<extra></extra>"
            )
        )

        if invadindo_opcao:
            if invadindo_opcao.lower() == "todos":
                sigef_plot = gdf_sigef_filtered
            else:
                sigef_plot = gdf_sigef_filtered[
                    gdf_sigef_filtered["invadindo"].str.strip().str.lower() == invadindo_opcao.lower()
                ]
            
            if not sigef_plot.empty:
                fig_sigef = px.choropleth_map(
                    sigef_plot,
                    geojson=sigef_plot.__geo_interface__,
                    locations=sigef_plot.index,
                    color=np.ones(len(sigef_plot)),
                    color_continuous_scale=[[0, "rgba(255,140,0,0.8)"], [1, "rgba(255,140,0,0.8)"]],
                    opacity=0.8
                )
                fig_sigef.update_coloraxes(showscale=False)
                for trace in fig_sigef.data:
                    fig.add_trace(trace)

        if df_csv_filtered is not None and not df_csv_filtered.empty:
            df_plot = df_csv_filtered.dropna(subset=['Latitude', 'Longitude']).drop_duplicates(subset=['Município'])
            
            if not df_plot.empty:
                conflitos_cols = [
                    'Áreas de conflitos', 'Assassinatos', 'Conflitos por Terra',
                    'Ocupações Retomadas', 'Tentativas de Assassinatos', 'Trabalho Escravo'
                ]
                
                existing_cols = [col for col in conflitos_cols if col in df_plot.columns]
                
                if existing_cols:
                    customdata = df_plot[existing_cols]
                    hovertemplate = "<b>%{text}</b><br>"
                    for i, col in enumerate(existing_cols):
                        hovertemplate += f"{col}: %{{customdata[{i}]}}<br>"
                    hovertemplate += "<extra></extra>"
                else:
                    customdata = [[]] * len(df_plot)
                    hovertemplate = "<b>%{text}</b><extra></extra>"

                fig.add_trace(
                    go.Scattermapbox(
                        lat=df_plot['Latitude'],
                        lon=df_plot['Longitude'],
                        mode='markers+text',
                        marker=dict(
                            size=12,
                            color='red',
                            opacity=0.7,
                            symbol='circle'
                        ),
                        text=df_plot['Município'],
                        textposition="top center",
                        textfont=dict(size=10, color="black"),
                        hovertemplate=hovertemplate,
                        customdata=customdata,
                        name='Municípios'
                    )
                )

        fig.update_layout(
            mapbox=dict(
                style="open-street-map",
                zoom=5,
                center=centro
            ),
            showlegend=False,
            margin=dict(l=0, r=0, t=0, b=0),
            height=600
        )
        
        return fig

    except Exception as e:
        st.error(f"Erro ao criar mapa: {e}")
        return go.Figure()
