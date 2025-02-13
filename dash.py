import streamlit as st
import geopandas as gpd
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

st.set_page_config(layout='wide')
# Função para carregar shapefile
def carregar_shapefile(caminho, calcular_percentuais=True):
    gdf = gpd.read_file(caminho)
    gdf["geometry"] = gdf["geometry"].apply(lambda geom: geom.buffer(0) if not geom.is_valid else geom)
    gdf = gdf[gdf["geometry"].notnull() & gdf["geometry"].is_valid]
    gdf_proj = gdf.to_crs("EPSG:31983")
    gdf_proj["area_calc_km2"] = gdf_proj.geometry.area / 1e6
    if "area_km2" in gdf.columns:
        gdf["area_km2"] = gdf["area_km2"].replace(0, None)
        gdf["area_km2"] = gdf["area_km2"].fillna(gdf_proj["area_calc_km2"])
    else:
        gdf["area_km2"] = gdf_proj["area_calc_km2"]
    if calcular_percentuais:
        if "alerta_km2" in gdf.columns:
            gdf["perc_alerta"] = (gdf["alerta_km2"] / gdf["area_km2"]) * 100
        else:
            gdf["perc_alerta"] = 0
        if "sigef_km2" in gdf.columns:
            gdf["perc_sigef"] = (gdf["sigef_km2"] / gdf["area_km2"]) * 100
        else:
            gdf["perc_sigef"] = 0
    else:
        gdf["perc_alerta"] = 0
        gdf["perc_sigef"] = 0
    gdf["id"] = gdf.index.astype(str)
    gdf = gdf.to_crs("EPSG:4326")
    return gdf

# Carregar dados
caminho_cnuc = os.path.join(os.path.dirname(__file__), 'cnuc.shp')
caminho_sigef = os.path.join(os.path.dirname(__file__), 'sigef.shp')
caminho_csv = os.path.join(os.path.dirname(__file__), 'CPT-PA-count.csv')

# Carregar os arquivos
gdf_cnuc = carregar_shapefile(caminho_cnuc)
gdf_sigef = carregar_shapefile(caminho_sigef, calcular_percentuais=False)
df_csv = pd.read_csv(caminho_csv)

gdf_cnuc["base"] = "cnuc"
gdf_sigef["base"] = "sigef"

# Calcular centro do mapa
limites = gdf_cnuc.total_bounds
centro = {"lat": (limites[1] + limites[3]) / 2, "lon": (limites[0] + limites[2]) / 2}

# Processar CSV
df_csv = df_csv.rename(columns={"Unnamed: 0": "Município"})
colunas_ocorrencias = ["Áreas de conflitos", "Assassinatos", "Conflitos por Terra", "Ocupações Retomadas", "Tentativas de Assassinatos", "Trabalho Escravo"]
df_csv["total_ocorrencias"] = df_csv[colunas_ocorrencias].sum(axis=1)

# Função para criar o mapa
def criar_figura(ids_selecionados=None, invadindo_opcao=None):
    fig = px.choropleth_mapbox(
        gdf_cnuc,
        geojson=gdf_cnuc.__geo_interface__,
        locations="id",
        color_discrete_sequence=["#DDDDDD"],
        hover_data=["nome_uc", "municipio", "perc_alerta", "perc_sigef", "alerta_km2", "sigef_km2", "area_km2"],
        mapbox_style="open-street-map",
        center=centro,
        zoom=4,
        opacity=0.7,
        title="Porcentagem de Área Sobreposta por Alertas e SIGEF"
    )
    if ids_selecionados:
        gdf_sel = gdf_cnuc[gdf_cnuc["id"].isin(ids_selecionados)]
        fig_sel = px.choropleth_mapbox(
            gdf_sel,
            geojson=gdf_cnuc.__geo_interface__,
            locations="id",
            color_discrete_sequence=["#0074D9"],
            hover_data=["nome_uc", "municipio", "perc_alerta", "perc_sigef", "alerta_km2", "sigef_km2", "area_km2"],
            mapbox_style="open-street-map",
            center=centro,
            zoom=10,
            opacity=0.6,
        )
        for trace in fig_sel.data:
            fig.add_trace(trace)
    if invadindo_opcao is not None:
        if invadindo_opcao.lower() == "todos":
            gdf_sigef_filtrado = gdf_sigef
        else:
            gdf_sigef_filtrado = gdf_sigef[gdf_sigef["invadindo"].str.strip().str.lower() == invadindo_opcao.strip().lower()]
        trace_sigef = go.Choroplethmapbox(
            geojson=gdf_sigef_filtrado.__geo_interface__,
            locations=gdf_sigef_filtrado["id"],
            z=[1] * len(gdf_sigef_filtrado),
            colorscale=[[0, "#FF4136"], [1, "#FF4136"]],
            marker_opacity=0.5,
            marker_line_width=1,
            name="SIGEF",
            showlegend=True,
            showscale=False
        )
        fig.add_trace(trace_sigef)
    if "Município" in df_csv.columns:
        cidades = df_csv["Município"].unique()
        cores_paleta = px.colors.qualitative.Pastel
        color_map = {cidade: cores_paleta[i % len(cores_paleta)] for i, cidade in enumerate(cidades)}
        for cidade in cidades:
            df_cidade = df_csv[df_csv["Município"] == cidade]
            base_size = list(df_cidade["total_ocorrencias"] * 3)
            outline_size = [s + 4 for s in base_size]
            trace_cpt_outline = go.Scattermapbox(
                lat=df_cidade["Latitude"],
                lon=df_cidade["Longitude"],
                mode="markers",
                marker=dict(
                    size=outline_size,
                    color="black",
                    sizemode="area"
                ),
                hoverinfo="none",
                showlegend=False
            )
            trace_cpt = go.Scattermapbox(
                lat=df_cidade["Latitude"],
                lon=df_cidade["Longitude"],
                mode="markers",
                marker=dict(
                    size=base_size,
                    color=color_map[cidade],
                    sizemode="area"
                ),
                text=df_cidade.apply(lambda linha: (
                    f"Município: {linha['Município']}<br>"
                    f"Áreas de conflitos: {linha['Áreas de conflitos']}<br>"
                    f"Assassinatos: {linha['Assassinatos']}<br>"
                    f"Conflitos por Terra: {linha['Conflitos por Terra']}<br>"
                    f"Ocupações Retomadas: {linha['Ocupações Retomadas']}<br>"
                    f"Tentativas de Assassinatos: {linha['Tentativas de Assassinatos']}<br>"
                    f"Trabalho Escravo: {linha['Trabalho Escravo']}"
                ), axis=1),
                hoverinfo="text",
                name=f"Ocorrências - {cidade}",
                showlegend=True
            )
            fig.add_trace(trace_cpt_outline)
            fig.add_trace(trace_cpt)
    else:
        trace_cpt = go.Scattermapbox(
            lat=df_csv["Latitude"],
            lon=df_csv["Longitude"],
            mode="markers",
            marker=dict(
                size=df_csv["total_ocorrencias"] * 3,
                color="red",
                sizemode="area"
            ),
            text=df_csv.apply(lambda linha: (
                f"Áreas de conflitos: {linha['Áreas de conflitos']}<br>"
                f"Assassinatos: {linha['Assassinatos']}<br>"
                f"Conflitos por Terra: {linha['Conflitos por Terra']}<br>"
                f"Ocupações Retomadas: {linha['Ocupações Retomadas']}<br>"
                f"Tentativas de Assassinatos: {linha['Tentativas de Assassinatos']}<br>"
                f"Trabalho Escravo: {linha['Trabalho Escravo']}"
            ), axis=1),
            hoverinfo="text",
            name="Ocorrências",
            showlegend=True
        )
        fig.add_trace(trace_cpt)
    for trace in fig.data:
        if trace.type != "scattermapbox":
            trace.showlegend = False
    fig.update_layout(
        coloraxis_showscale=False,
        legend=dict(title="Legenda", x=0, y=1),
        height=700,  # Aumentar a altura do mapa
        margin={"r": 10, "t": 50, "l": 10, "b": 10},
        title_font=dict(size=22),
    )
    return fig
    
st.markdown(
    """
    <style>
    .cards-container {
        display: flex;
        justify-content: space-between; /* Ajusta o espaçamento entre os cards */
        flex-wrap: nowrap; /* Impede que os cards quebrem para a próxima linha */
        overflow-x: auto; /* Adiciona scroll horizontal se necessário */
        gap: 10px; /* Espaçamento entre os cards */
    }
    .card {
        padding: 15px;
        border-radius: 10px;
        background-color: #f0f2f6; /* Cor de fundo do card */
        text-align: center;
        box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.1);
        flex: 1 1 auto; /* Faz os cards terem tamanhos flexíveis */
        min-width: 150px; /* Define um tamanho mínimo para cada card */
    }
    .card h3 {
        margin-bottom: 5px;
        font-size: 18px;
    }
    .card p {
        font-size: 24px;
        font-weight: bold;
    }
    </style>
    """,
    unsafe_allow_html=True
)

def criar_cards(ids_selecionados=None):
    filtro = gdf_cnuc[gdf_cnuc["id"].isin(ids_selecionados)] if ids_selecionados else gdf_cnuc
    total_alerta = filtro["c_alertas"].sum()
    total_sigef = filtro["c_sigef"].sum()
    total_area = filtro["area_km2"].sum()
    perc_alerta = (total_alerta / total_area * 100) if total_area else 0
    perc_sigef = (total_sigef / total_area * 100) if total_area else 0
    total_unidades = filtro.shape[0]
    contagem_alerta = filtro["c_alertas"].sum()
    contagem_sigef = filtro["c_sigef"].sum()

    st.markdown('<div class="cards-container">', unsafe_allow_html=True)

    st.markdown(f"""
    <div class="card">
        <h3>Percentual de Alerta</h3>
        <p>{perc_alerta:.2f}%</p>
    </div>
    <div class="card">
        <h3>Percentual SIGEF</h3>
        <p>{perc_sigef:.2f}%</p>
    </div>
    <div class="card">
        <h3>Total de Unidades</h3>
        <p>{total_unidades}</p>
    </div>
    <div class="card">
        <h3>Contagem Alerta</h3>
        <p>{contagem_alerta}</p>
    </div>
    <div class="card">
        <h3>Contagem SIGEF</h3>
        <p>{contagem_sigef}</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
    
# Função para obter o filtro de "invadindo"
def get_invadindo_filtro(value):
    return value

# Opções para o filtro de "invadindo"
opcoes_invadindo = ["Todos"] + sorted(gdf_sigef["invadindo"].unique().tolist())

# Criar gráficos
bar_fig = px.bar(
    gdf_cnuc,
    x='nome_uc',
    y=['alerta_km2', 'sigef_km2', 'area_km2'],
    labels={'value': "Contagens", "nome_uc": "Nome UC"},
    barmode="group",
    color_discrete_map={
        "alerta_km2": px.colors.qualitative.Pastel[0],
        "sigef_km2": px.colors.qualitative.Pastel[1],
        "area_km2": px.colors.qualitative.Pastel[2]
    }
)
bar_fig.update_layout(
    legend_title_text='Métricas',
    height=500,  # Aumentar a altura do gráfico de barras
    margin={"r": 10, "t": 50, "l": 10, "b": 10},
    title_font=dict(size=22),
    title='Contagem das Áreas de Proteção'
)

pie_fig = px.pie(
    df_csv,
    values='Áreas de conflitos',
    names='Município',
    title='Áreas de conflitos',
    color_discrete_sequence=px.colors.qualitative.Pastel,
)
pie_fig.update_traces(textposition='inside', textinfo='percent+label')
pie_fig.update_layout(
    font_size=14,
    height=500,  # Aumentar a altura do gráfico de pizza
    margin={"r": 10, "t": 50, "l": 10, "b": 10},
    title_font=dict(size=22),
)

# Título do dashboard
st.title("Dashboard de Monitoramento")
# Seleção da área no sidebar

invadindo_opcao = st.sidebar.selectbox("Selecione a área (invadindo)", opcoes_invadindo)

# Layout em duas colunas
col1, col2 = st.columns([2, 1])  # Ajuste a proporção das colunas

# Coluna 1: Mapa e cards
with col1:
    # Mostrar o mapa
    fig = criar_figura(invadindo_opcao=invadindo_opcao)
    st.plotly_chart(fig, use_container_width=True)
    # Mostrar os cards
    criar_cards()

# Coluna 2: Gráficos
with col2:
    st.plotly_chart(bar_fig, use_container_width=True)
    st.plotly_chart(pie_fig, use_container_width=True)
