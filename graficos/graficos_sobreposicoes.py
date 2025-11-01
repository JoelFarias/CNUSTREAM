import textwrap
import pandas as pd
import geopandas as gpd
import plotly.graph_objects as go
from utilitarios.formatacao import formatar_numero_com_pontos
from utilitarios.estilos import aplicar_layout

def wrap_label(name, width=30):
    if pd.isna(name):
        return ""
    return "<br>".join(textwrap.wrap(str(name), width))

def fig_sobreposicoes(gdf_cnuc_ha_filtered):
    gdf = gdf_cnuc_ha_filtered.copy().sort_values("area_ha", ascending=False)
    if gdf.empty:
        return go.Figure()

    gdf["uc_short"] = gdf["nome_uc"].apply(lambda x: wrap_label(x, 15))
    
    fig = go.Figure()
    
    alerta_text = [formatar_numero_com_pontos(val, 0) for val in gdf["alerta_ha"]]
    sigef_text = [formatar_numero_com_pontos(val, 0) for val in gdf["sigef_ha"]]
    area_text = [formatar_numero_com_pontos(val, 0) for val in gdf["area_ha"]]
    
    fig.add_trace(go.Bar(
        name='Alertas',
        x=gdf["uc_short"],
        y=gdf["alerta_ha"],
        marker_color='#99CD85',
        text=alerta_text,
        textposition='inside',
        hovertemplate='<b>%{x}</b><br>Alertas: %{text} ha<extra></extra>',
        customdata=alerta_text
    ))
    
    fig.add_trace(go.Bar(
        name='CARs',
        x=gdf["uc_short"],
        y=gdf["sigef_ha"],
        marker_color='#CFE0BC',
        text=sigef_text,
        textposition='inside',
        hovertemplate='<b>%{x}</b><br>CARs: %{text} ha<extra></extra>',
        customdata=sigef_text
    ))
    
    fig.add_trace(go.Bar(
        name='UCs',
        x=gdf["uc_short"],
        y=gdf["area_ha"],
        marker_color='#7FA653',
        text=area_text,
        textposition='inside',
        hovertemplate='<b>%{x}</b><br>UCs: %{text} ha<extra></extra>',
        customdata=area_text
    ))
    
    fig.update_layout(
        barmode='stack',
        height=400,
        xaxis=dict(tickangle=0, tickfont=dict(size=9), title_text=""),
        yaxis=dict(title_text="Área (ha)", tickfont=dict(size=9), tickformat='~s')
    )
    
    return aplicar_layout(fig, titulo="Áreas por UC", tamanho_titulo=16)

def fig_contagens_uc(gdf_cnuc_filtered: gpd.GeoDataFrame) -> go.Figure:
    gdf = gdf_cnuc_filtered.copy()
    if gdf.empty:
        return go.Figure()
    gdf["total_counts"] = gdf.get("c_alertas", 0) + gdf.get("c_sigef", 0)
    gdf = gdf.sort_values("total_counts", ascending=False)
    
    gdf["uc_wrap"] = gdf["nome_uc"].apply(lambda x: wrap_label(x, 15))
    
    alertas_text = [formatar_numero_com_pontos(val, 0) for val in gdf.get("c_alertas", 0)]
    sigef_text = [formatar_numero_com_pontos(val, 0) for val in gdf.get("c_sigef", 0)]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        name='Alertas',
        x=gdf["uc_wrap"],
        y=gdf.get("c_alertas", 0),
        marker_color='#99CD85',
        text=alertas_text,
        textposition='inside',
        hovertemplate='<b>%{x}</b><br>Alertas: %{text}<extra></extra>',
        customdata=alertas_text
    ))
    
    fig.add_trace(go.Bar(
        name='CARs',
        x=gdf["uc_wrap"],
        y=gdf.get("c_sigef", 0),
        marker_color='#63783D',
        text=sigef_text,
        textposition='inside',
        hovertemplate='<b>%{x}</b><br>CARs: %{text}<extra></extra>',
        customdata=sigef_text
    ))
    
    fig.update_layout(
        barmode='stack',
        height=400,
        xaxis=dict(tickangle=0, tickfont=dict(size=9), title_text=""),
        yaxis=dict(title_text="Contagens", tickfont=dict(size=9), tickformat='~s')
    )
    
    return aplicar_layout(fig, titulo="Contagens por UC", tamanho_titulo=16)

def fig_car_por_uc_donut(gdf_cnuc_ha_filtered: gpd.GeoDataFrame, nome_uc: str, modo_valor: str = "percent") -> go.Figure:
    gdf_cnuc_ha = gdf_cnuc_ha_filtered.copy()
    if gdf_cnuc_ha.empty:
         return go.Figure()

    if nome_uc == "Todas":
        area_total = gdf_cnuc_ha["area_ha"].sum()
        area_car = gdf_cnuc_ha["sigef_ha"].sum()
    else:
        row = gdf_cnuc_ha[gdf_cnuc_ha["nome_uc"] == nome_uc]
        if row.empty:
            return go.Figure() 
            
        area_total = row["area_ha"].values[0]
        area_car = row["sigef_ha"].values[0]

    area_total = float(area_total) if area_total and not pd.isna(area_total) else 0.0
    area_car = float(area_car) if area_car and not pd.isna(area_car) else 0.0
    
    percentual = (area_car / area_total) * 100 if area_total > 0 else 0
    
    if area_car <= area_total:
        area_livre = area_total - area_car
        labels = ["Área CAR", "Área Livre"]
        values = [area_car, area_livre]
        colors = ["#2ca02c", "#d9d9d9"]
    else:
        area_livre = 0
        labels = ["Área CAR"]
        values = [100]
        colors = ["#2ca02c"]
    
    area_total_fmt = formatar_numero_com_pontos(area_total, 0)
    area_car_fmt = formatar_numero_com_pontos(area_car, 0)
    percentual_fmt = f"{percentual:.1f}%".replace('.', ',')
    
    if modo_valor == "percent":
        textinfo = "label+percent"
        center_text = f"UC: {area_total_fmt} ha<br>CAR: {area_car_fmt} ha<br>({percentual_fmt})"
    else:
        textinfo = "label+value"
        center_text = f"UC: {area_total_fmt} ha<br>CAR: {area_car_fmt} ha"
        
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.6,
        marker_colors=colors,
        textinfo=textinfo,
        hoverinfo="label+value"
    )])
    fig.update_layout(
        title_text=f"Ocupação do CAR em: {nome_uc}",
        annotations=[dict(text=center_text, x=0.5, y=0.5, font_size=14, showarrow=False)],
        height=400
    )
    return aplicar_layout(fig, titulo=f"Ocupação do CAR em: {nome_uc}", tamanho_titulo=16)
