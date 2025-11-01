import pandas as pd
import geopandas as gpd
import plotly.graph_objects as go
from utilitarios.formatacao import formatar_numero_com_pontos


def graficos_inpe(data_frame_entrada: pd.DataFrame, ano_selecionado_str: str, gdf_cnuc_raw: gpd.GeoDataFrame = None) -> dict[str, go.Figure]:
    df = data_frame_entrada.copy()
    
    if 'municipio' in df.columns and 'mun_corrigido' not in df.columns:
        df['mun_corrigido'] = df['municipio']
    
    def create_placeholder_fig(title_message: str) -> go.Figure:
        fig = go.Figure()
        fig.update_layout(
            title=title_message,
            xaxis_visible=False,
            yaxis_visible=False,
            annotations=[dict(text="Não há dados suficientes para exibir este gráfico.", showarrow=False, xref="paper", yref="paper", x=0.5, y=0.5)]
        )
        return fig

    base_error_title = f"Período: {ano_selecionado_str}"

    if df.empty:
        return {
            'temporal': create_placeholder_fig(f"Evolução Temporal ({base_error_title})"),
            'top_risco': create_placeholder_fig(f"Top Risco ({base_error_title})"),
            'top_precip': create_placeholder_fig(f"Top Precipitação ({base_error_title})"),
            'mapa': create_placeholder_fig(f"Mapa de Focos ({base_error_title})")
        }

    fig_temp = create_placeholder_fig(f"Evolução Temporal do Risco de Fogo ({ano_selecionado_str})")
    if 'DataHora' in df.columns and 'RiscoFogo' in df.columns:
        df_temp_indexed = df.set_index('DataHora')
        df_risco_valido_temp = df_temp_indexed[df_temp_indexed['RiscoFogo'].between(0, 1)]
        if not df_risco_valido_temp.empty:
            monthly_risco = df_risco_valido_temp['RiscoFogo'].resample('ME').mean().reset_index()
            monthly_risco['RiscoFogo'] = monthly_risco['RiscoFogo'].fillna(0)

            if not monthly_risco.empty:
                fig_temp = go.Figure()
                fig_temp.add_trace(go.Scatter(
                    x=monthly_risco['DataHora'].dt.to_period('M').astype(str),
                    y=monthly_risco['RiscoFogo'],
                    name='Risco de Fogo Mensal',
                    mode='lines+markers+text',
                    marker=dict(size=8, color='#FF4136', line=dict(width=1, color='#444')),
                    line=dict(width=2, color='#FF4136'),
                    text=[f'{v:.2f}'.replace('.', ',') for v in monthly_risco['RiscoFogo']],
                    textposition='top center'
                ))
                fig_temp.update_layout(
                    title_text=f'Evolução Mensal do Risco de Fogo ({ano_selecionado_str})',
                    xaxis_title='Mês',
                    yaxis_title='Risco Médio de Fogo',
                    height=400,
                    margin=dict(l=60, r=80, t=80, b=40),
                    showlegend=True,
                    hovermode='x unified'
                )

    fig_risco = create_placeholder_fig(f"Top Municípios - Risco de Fogo ({ano_selecionado_str})")
    if 'mun_corrigido' in df.columns and 'RiscoFogo' in df.columns:
        df_risco_valido = df[df['RiscoFogo'].between(0, 1)]
        if not df_risco_valido.empty:
            top_risco_data = df_risco_valido.groupby('mun_corrigido', observed=False)['RiscoFogo'].mean().nlargest(10).sort_values()
            if not top_risco_data.empty:
                risco_text = [f"{v:.2f}".replace('.', ',') for v in top_risco_data.values]
                fig_risco = go.Figure(go.Bar(
                    y=top_risco_data.index,
                    x=top_risco_data.values,
                    orientation='h',
                    marker_color='#FF8C7A',
                    text=risco_text,
                    textposition='outside',
                    hovertemplate='<b>%{y}</b><br>Risco Médio: %{text}<extra></extra>',
                    customdata=risco_text
                ))
                fig_risco.update_layout(
                    title_text=f'Top Municípios por Risco Médio de Fogo ({ano_selecionado_str})',
                    xaxis_title='Risco Médio de Fogo',
                    yaxis_title='Município',
                    height=400,
                    margin=dict(l=100, r=80, t=50, b=40)
                )

    fig_precip = create_placeholder_fig(f"Top Municípios - Precipitação Média ({ano_selecionado_str})")
    if 'mun_corrigido' in df.columns and 'Precipitacao' in df.columns:
        df_precip_valida = df[df['Precipitacao'] >= 0]
        if not df_precip_valida.empty:
            top_precip_data = df_precip_valida.groupby('mun_corrigido', observed=False)['Precipitacao'].mean().nlargest(10).sort_values()
            if not top_precip_data.empty:
                precip_text = [f"{formatar_numero_com_pontos(v, 2)} mm" for v in top_precip_data.values]
                fig_precip = go.Figure(go.Bar(
                    y=top_precip_data.index,
                    x=top_precip_data.values,
                    orientation='h',
                    marker_color='#B3D9FF',
                    text=precip_text,
                    textposition='outside',
                    hovertemplate='<b>%{y}</b><br>Precipitação Média: %{text}<extra></extra>',
                    customdata=precip_text
                ))
                fig_precip.update_layout(
                    title_text=f'Top Municípios por Precipitação Média ({ano_selecionado_str})',
                    xaxis_title='Precipitação Média (mm)',
                    yaxis_title='Município',
                    height=400,
                    margin=dict(l=100, r=120, t=50, b=40)
                )

    fig_map = create_placeholder_fig(f"Mapa de Distribuição dos Focos de Calor ({ano_selecionado_str})")
    map_required_cols = ['Latitude', 'Longitude', 'RiscoFogo', 'mun_corrigido', 'DataHora']
    if all(col in df.columns for col in map_required_cols):
        df_map_plot = df[map_required_cols + (['Precipitacao'] if 'Precipitacao' in df.columns else [])].copy()
        df_map_plot.dropna(subset=['Latitude', 'Longitude', 'RiscoFogo', 'mun_corrigido'], inplace=True)
        df_map_plot = df_map_plot[df_map_plot['RiscoFogo'].between(0, 1)]
        if 'Precipitacao' in df_map_plot.columns:
             df_map_plot = df_map_plot[df_map_plot['Precipitacao'] >= 0]
        else:
            df_map_plot['Precipitacao'] = 0

        if not df_map_plot.empty:
            sample_size = 50000
            if len(df_map_plot) > sample_size:
                df_map_plot_sampled = df_map_plot.sample(sample_size, random_state=1)
            else:
                df_map_plot_sampled = df_map_plot

            if not df_map_plot_sampled.empty:
                centro_map = {
                    'lat': df_map_plot_sampled['Latitude'].mean(),
                    'lon': df_map_plot_sampled['Longitude'].mean()
                }
                lat_range = df_map_plot_sampled['Latitude'].max() - df_map_plot_sampled['Latitude'].min()
                lon_range = df_map_plot_sampled['Longitude'].max() - df_map_plot_sampled['Longitude'].min()
                max_range = max(lat_range, lon_range, 0.01)

                zoom_level = 3.5
                if max_range < 1: zoom_level = 7
                elif max_range < 5: zoom_level = 5
                elif max_range < 10: zoom_level = 4
                fig_map = go.Figure()
                if gdf_cnuc_raw is not None and not gdf_cnuc_raw.empty:
                    gdf_cnuc_geo = gdf_cnuc_raw.to_crs("EPSG:4326")
                    
                    for idx, row in gdf_cnuc_geo.iterrows():
                        if row.geometry and hasattr(row.geometry, 'exterior'):
                            if row.geometry.geom_type == 'Polygon':
                                coords = list(row.geometry.exterior.coords)
                                lons, lats = zip(*coords)
                                
                                fig_map.add_trace(go.Scattermapbox(
                                    lon=lons,
                                    lat=lats,
                                    mode='lines',
                                    fill='toself',
                                    fillcolor='rgba(34,139,34,0.2)',
                                    line=dict(color='rgba(34,139,34,0.8)', width=1),
                                    name='Unidades de Conservação',
                                    showlegend=False,  
                                    hovertemplate=f"<b>{row.get('nome_uc', 'UC')}</b><extra></extra>",
                                    text=row.get('nome_uc', 'UC')
                                ))
                        elif row.geometry and row.geometry.geom_type == 'MultiPolygon':
                            for poly in row.geometry.geoms:
                                coords = list(poly.exterior.coords)
                                lons, lats = zip(*coords)
                                
                                fig_map.add_trace(go.Scattermapbox(
                                    lon=lons,
                                    lat=lats,
                                    mode='lines',
                                    fill='toself',
                                    fillcolor='rgba(34,139,34,0.2)',
                                    line=dict(color='rgba(34,139,34,0.8)', width=1),
                                    name='Unidades de Conservação',
                                    showlegend=False,
                                    hovertemplate=f"<b>{row.get('nome_uc', 'UC')}</b><extra></extra>",
                                    text=row.get('nome_uc', 'UC')
                                ))

                fig_map.add_trace(go.Scattermapbox(
                    lat=df_map_plot_sampled['Latitude'],
                    lon=df_map_plot_sampled['Longitude'],
                    mode='markers',
                    marker=dict(
                        size=df_map_plot_sampled['Precipitacao'] / 10 + 3,  
                        color=df_map_plot_sampled['RiscoFogo'],
                        colorscale='YlOrRd',
                        showscale=False,  
                        sizemin=3,
                        opacity=0.7
                    ),
                    text=df_map_plot_sampled['mun_corrigido'],
                    hovertemplate=(
                        "<b>%{text}</b><br>" +
                        "Risco de Fogo: %{marker.color:.2f}<br>" +
                        "Precipitação: %{marker.size:.1f} mm<br>" +
                        "<extra></extra>"
                    ),
                    name='Focos de Calor',
                    showlegend=False 
                ))

                fig_map.update_layout(
                    title_text=f'Mapa de Distribuição dos Focos de Calor ({ano_selecionado_str})',
                    mapbox=dict(
                        style='open-street-map',
                        zoom=zoom_level,
                        center=centro_map
                    ),
                    margin=dict(l=0, r=0, t=40, b=0),
                    showlegend=False 
                )

    return {
        'temporal': fig_temp,
        'top_risco': fig_risco,
        'top_precip': fig_precip,
        'mapa': fig_map
    }
