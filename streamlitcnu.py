import streamlit as st
import geopandas as gpd
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import unicodedata

df_cpt = pd.DataFrame()

st.set_page_config(page_title="Dashboard", layout="wide")

@st.cache_data
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

gdf_cnuc = carregar_shapefile(r"C:\Users\joelc\Documents\Estágio\entrega-PA\entrega-PA\áreas-selecionadas\cnuc\cnuc.shp")
gdf_sigef = carregar_shapefile(r"C:\Users\joelc\Documents\Estágio\entrega-PA\entrega-PA\áreas-selecionadas\sigef\sigef.shp", calcular_percentuais=False)
gdf_cnuc["base"] = "cnuc"
gdf_sigef["base"] = "sigef"
gdf_sigef = gdf_sigef.rename(columns={"id": "id_sigef"})
limites = gdf_cnuc.total_bounds
centro = {"lat": (limites[1] + limites[3]) / 2, "lon": (limites[0] + limites[2]) / 2}

@st.cache_data
def load_csv(caminho):
    df = pd.read_csv(caminho)
    df = df.rename(columns={"Unnamed: 0": "Município"})
    colunas_ocorrencias = ["Áreas de conflitos", "Assassinatos", "Conflitos por Terra", "Ocupações Retomadas", "Tentativas de Assassinatos", "Trabalho Escravo"]
    df["total_ocorrencias"] = df[colunas_ocorrencias].sum(axis=1)
    return df

df_csv = load_csv(r"C:\Users\joelc\Documents\Estágio\cnu\CPT-PA-count.csv")

@st.cache_data
def carregar_dados_cpt(arquivo_excel):
    xls = pd.ExcelFile(arquivo_excel)
    dados = []
    
    def normalizar_nome_municipio(nome):
        nome = ''.join(c for c in unicodedata.normalize('NFD', str(nome).lower()) 
                     if not unicodedata.combining(c))
        correcoes = {
            'sao felix do xingu': 'São Félix do Xingu',
            'matupa': 'Matupá',
            'senador jose porfirio': 'Senador José Porfírio',
            'cumaru do norte': 'Cumaru do Norte'
        }
        return correcoes.get(nome.strip(), nome.strip().title())

    for aba in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=aba, header=0).dropna(how='all')
        
        if aba == 'Ameaçados' and not df.empty:
            dados.append({
                'Tipo': 'Ameaçados',
                'Famílias': df['Famílias'].sum(),
                'Área_ha': df['Área'].sum(),
                'Casas_Destruídas': df['Casas Destruídas'].sum()
            })
            
        elif aba == 'Áreas em Conflito' and not df.empty:
            df['Município'] = df['mun'].apply(
                lambda x: [normalizar_nome_municipio(m) for m in str(x).split(',')]
            )
            df = df.explode('Município')
            conflitos = df.groupby('Município').size().reset_index(name='Contagem')
            
            dados.append({
                'Tipo': 'Áreas em Conflito',
                'Municípios_Únicos': df['Município'].nunique(),
                'Famílias_Risco': df['Famílias'].sum(),
                'Conflitos_Por_Municipio': conflitos.to_dict('records')
            })
            
        elif aba == 'Assassinatos' and not df.empty:
            dados.append({
                'Tipo': 'Assassinatos',
                'Vítimas_Totais': df['Vítimas'].sum(),
                'Ano_Último_Caso': df['Data'].dt.year.max()
            })
            
        elif aba == 'Ocupações Retomadas' and not df.empty:
            dados.append({
                'Tipo': 'Ocupações Retomadas',
                'Área_Total_ha': df['Área'].sum(),
                'Média_Famílias': df['Famílias'].mean()
            })

    return pd.DataFrame(dados).reset_index(drop=True)


def criar_figura(ids_selecionados, invadindo_opcao):
    fig = px.choropleth_mapbox(
        gdf_cnuc,
        geojson=gdf_cnuc.__geo_interface__,
        locations="id",
        color_discrete_sequence=["#DDDDDD"],
        hover_data=["nome_uc", "municipio", "perc_alerta", "perc_sigef", "alerta_km2", "sigef_km2", "area_km2"],
        mapbox_style="open-street-map",
        center=centro,
        zoom=4,
        opacity=0.7
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
            zoom=4,
            opacity=0.8
        )
        for trace in fig_sel.data:
            fig.add_trace(trace)
    
    if invadindo_opcao is not None:
        gdf_sigef_filtrado = gdf_sigef if invadindo_opcao.lower() == "todos" else gdf_sigef[gdf_sigef["invadindo"].str.strip().str.lower() == invadindo_opcao.strip().lower()]
        trace_sigef = go.Choroplethmapbox(
            geojson=gdf_sigef_filtrado.__geo_interface__,
            locations=gdf_sigef_filtrado["id_sigef"],
            z=[1] * len(gdf_sigef_filtrado),
            colorscale=[[0, "#FF4136"], [1, "#FF4136"]],
            marker_opacity=0.5,
            marker_line_width=1,
            showlegend=False,
            showscale=False
        )
        fig.add_trace(trace_sigef)
    
    cidades = df_csv["Município"].unique()
    cores_paleta = px.colors.qualitative.Pastel
    color_map = {cidade: cores_paleta[i % len(cores_paleta)] for i, cidade in enumerate(cidades)}
    
    for cidade in cidades:
        df_cidade = df_csv[df_csv["Município"] == cidade]
        base_size = list(df_cidade["total_ocorrencias"] * 10)
        outline_size = [s + 4 for s in base_size]
        
        trace_cpt_outline = go.Scattermapbox(
            lat=df_cidade["Latitude"],
            lon=df_cidade["Longitude"],
            mode="markers",
            marker=dict(size=outline_size, color="black", sizemode="area", opacity=0.8),
            hoverinfo="none",
            showlegend=False
        )
        
        trace_cpt = go.Scattermapbox(
            lat=df_cidade["Latitude"],
            lon=df_cidade["Longitude"],
            mode="markers",
            marker=dict(size=base_size, color=color_map[cidade], sizemode="area"),
            text=df_cidade.apply(lambda linha: f"Município: {linha['Município']}<br>Áreas de conflitos: {linha['Áreas de conflitos']}<br>Assassinatos: {linha['Assassinatos']}", axis=1),
            hoverinfo="text",
            name=f"Ocorrências - {cidade}",
            showlegend=True
        )

        fig.add_trace(trace_cpt_outline)
        fig.add_trace(trace_cpt)
    
        fig.update_layout(
            margin={"r":0,"t":0,"l":0,"b":0},
            legend=dict(
                bgcolor="rgba(255,255,255,0.8)",
                bordercolor="#CCC",
                borderwidth=1,
                font=dict(size=10)
            ),
            height=800  
        )
    return fig

def criar_graficos_cpt(df):
    figs = []
    
    if 'Ameaçados' in df['Tipo'].values:
        df_ameaca = df[df['Tipo'] == 'Ameaçados']
        fig = px.bar(
            df_ameaca,
            x='Tipo',
            y=['Famílias', 'Área_ha', 'Casas_Destruídas'],
            title='Distribuição de Ameaças',
            labels={'value': 'Quantidade', 'variable': 'Categoria'},
            barmode='group'
        )
        figs.append(fig)
    
    if 'Áreas em Conflito' in df['Tipo'].values:
        df_conflito = df[df['Tipo'] == 'Áreas em Conflito']
        fig = px.scatter(
            df_conflito,
            x='Municípios_Únicos',
            y='Total_Conflitos',
            size='Famílias_Risco',
            title='Relação Conflitos vs Municípios',
            color='Total_Conflitos'
        )
        figs.append(fig)
    
    return figs

def criar_cards(ids_selecionados, invadindo_opcao):
    try:
        ucs_selecionadas = gdf_cnuc[gdf_cnuc["id"].isin(ids_selecionados)] if ids_selecionados else gdf_cnuc.copy()
        
        if ucs_selecionadas.empty:
            return (0.0, 0.0, 0, 0, 0)

        crs_proj = "EPSG:31983"
        ucs_proj = ucs_selecionadas.to_crs(crs_proj)
        sigef_proj = gdf_sigef.to_crs(crs_proj)

        if invadindo_opcao and invadindo_opcao.lower() != "todos":
            mascara = sigef_proj["invadindo"].str.strip().str.lower() == invadindo_opcao.strip().lower()
            sigef_filtrado = sigef_proj[mascara].copy()
        else:
            sigef_filtrado = sigef_proj.copy()

        sobreposicao = gpd.overlay(
            ucs_proj,
            sigef_filtrado,
            how='intersection',
            keep_geom_type=False,
            make_valid=True
        )
        sobreposicao['area_sobreposta'] = sobreposicao.geometry.area / 1e6
        total_sigef = sobreposicao['area_sobreposta'].sum()
        total_area_ucs = ucs_proj.geometry.area.sum() / 1e6
        total_alerta = ucs_selecionadas["alerta_km2"].sum()

        perc_alerta = (total_alerta / total_area_ucs * 100) if total_area_ucs > 0 else 0
        perc_sigef = (total_sigef / total_area_ucs * 100) if total_area_ucs > 0 else 0

        municipios = set()
        for munic in ucs_selecionadas["municipio"]:
            partes = str(munic).replace(';', ',').split(',')
            for parte in partes:
                if parte.strip():
                    municipios.add(parte.strip().title())

        return (
            round(perc_alerta, 1),
            round(perc_sigef, 1),
            len(municipios),
            int(ucs_selecionadas["c_alertas"].sum()),
            int(sobreposicao.shape[0])
        ) 

    except Exception as e:
        st.error(f"Erro crítico: {str(e)}")
        return (0.0, 0.0, 0, 0, 0)
    
def render_cards(perc_alerta, perc_sigef, total_unidades, contagem_alerta, contagem_sigef):
    col1, col2, col3, col4, col5 = st.columns(5, gap="small")
    
    card_html_template = """
    <div style="
        background: rgba(255,255,255,0.9);
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;">
        <div style="font-size: 0.9rem; color: #6FA8DC;">{titulo}</div>
        <div style="font-size: 1.2rem; font-weight: bold; color: #2F5496;">{valor}</div>
        <div style="font-size: 0.7rem; color: #666;">{descricao}</div>
    </div>
    """
    
    with col1:
        st.markdown(
            card_html_template.format(
                titulo="Alertas / Ext. Ter.",
                valor=f"{perc_alerta:.1f}%",
                descricao="Área de alertas sobre extensão territorial"
            ),
            unsafe_allow_html=True
        )
    
    with col2:
        st.markdown(
            card_html_template.format(
                titulo="CARs / Ext. Ter.", 
                valor=f"{perc_sigef:.1f}%",
                descricao="CARs sobre extensão territorial"
            ),
            unsafe_allow_html=True
        )
    
    with col3:
        st.markdown(
            card_html_template.format(
                titulo="Municípios Abrangidos",
                valor=f"{total_unidades}",
                descricao="Total de municípios na análise"
            ),
            unsafe_allow_html=True
        )

    with col4:
        st.markdown(
            card_html_template.format(
                titulo="Alertas",
                valor=f"{contagem_alerta}",
                descricao="Total de registros de alertas"
            ),
            unsafe_allow_html=True
        )

    with col5:
        st.markdown(
            card_html_template.format(
                titulo="CARs",
                valor=f"{contagem_sigef}",
                descricao="Cadastros Ambientais Rurais"
            ),
            unsafe_allow_html=True
        )

common_layout = {
    "plot_bgcolor": "rgba(0,0,0,0)",
    "paper_bgcolor": "rgba(0,0,0,0)",
    "font": {"family": "Arial", "size": 12},
    "margin": {"t": 40, "b": 20},
    "hoverlabel": {"bgcolor": "white", "font_size": 12}
}

gdf_cnuc_ha = gdf_cnuc.copy()
gdf_cnuc_ha['alerta_ha'] = gdf_cnuc_ha['alerta_km2'] * 100
gdf_cnuc_ha['sigef_ha'] = gdf_cnuc_ha['sigef_km2'] * 100
gdf_cnuc_ha['area_ha']   = gdf_cnuc_ha['area_km2'] * 100

bar_fig = px.bar(
    gdf_cnuc_ha,
    x='nome_uc',
    y=['alerta_ha', 'sigef_ha', 'area_ha'],
    labels={'value': "Área (ha)", "nome_uc": "Nome UC"},
    color_discrete_map={
        "alerta_ha": 'rgb(251,180,174)', 
        "sigef_ha": 'rgb(179,205,227)', 
        "area_ha": 'rgb(204,235,197)'
    },
    barmode='stack',
    text_auto=True
)

for trace in bar_fig.data:
    trace.texttemplate = '%{y:.0f} ha'
    trace.textposition = 'inside'
    trace.hovertemplate = (
        "<b>%{x}</b><br>" +
        trace.name + ": %{y:,.0f}" +
        "<extra></extra>"
    )

bar_fig.update_yaxes(tickformat=",")
bar_fig.update_layout(
    **common_layout,
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

contagens_fig = px.bar(
    gdf_cnuc,
    x='nome_uc',
    y=['c_alertas', 'c_sigef'],
    labels={'value': "Contagens", "nome_uc": "Nome UC"},
    color_discrete_map={
        "c_alertas": 'rgb(251,180,174)', 
        "c_sigef": 'rgb(179,205,227)'
    },
    barmode='stack'
)

for trace in contagens_fig.data:
    trace.texttemplate = '%{y:.0f}'
    trace.textposition = 'inside'
    trace.hovertemplate = (
        "<b>%{x}</b><br>" +
        trace.name + ": %{y:,.0f}" +
        "<extra></extra>"
    )

contagens_fig.update_yaxes(tickformat=",")
contagens_fig.update_layout(
    **common_layout,
    hovermode="x unified",
    showlegend=False
)

st.header("Análise de Conflitos em Áreas Protegidas e Territórios Tradicionais")
st.caption("Monitoramento integrado de sobreposições em Unidades de Conservação, Terras Indígenas e Territórios Quilombolas")
st.divider()

with st.sidebar:
    st.header("Filtros")
    opcoes_invadindo = ["Selecione", "Todos"] + sorted(gdf_sigef["invadindo"].str.strip().unique().tolist())
    invadindo_opcao = st.selectbox("Área de sobreposição:", opcoes_invadindo, help="Selecione o tipo de área sobreposta para análise")
    st.info("ℹ️ Use os filtros para explorar diferentes cenários de sobreposição territorial.")

if invadindo_opcao == "Selecione":
    invadindo_opcao = None

if invadindo_opcao is None or invadindo_opcao.lower() == "todos":
    ids_selecionados = []
else:
    gdf_sigef_filtrado = gdf_sigef[gdf_sigef["invadindo"].str.strip().str.lower() == invadindo_opcao.strip().lower()]
    gdf_cnuc_filtrado = gpd.sjoin(gdf_cnuc, gdf_sigef_filtrado, how="inner", predicate="intersects")
    ids_selecionados = gdf_cnuc_filtrado["id"].unique().tolist()

fig = criar_figura(ids_selecionados, invadindo_opcao)
perc_alerta, perc_sigef, total_unidades, contagem_alerta, contagem_sigef = criar_cards(ids_selecionados, invadindo_opcao)

col1, col2 = st.columns([8, 4], gap="large")

with col1:
    st.plotly_chart(fig, use_container_width=True, height=700)
    render_cards(perc_alerta, perc_sigef, total_unidades, contagem_alerta, contagem_sigef)

with col2:
    tab1, tab2 = st.tabs(["Sobreposições", "Ocupações Retomadas"])
    
    with tab1:
        st.plotly_chart(bar_fig, use_container_width=True)
        st.plotly_chart(contagens_fig, use_container_width=True)
    
    with tab2:
        lollipop_fig = px.bar(
            df_csv.sort_values('Áreas de conflitos', ascending=False),
            x='Áreas de conflitos',
            y='Município',
            orientation='h',
            color='Município',
            color_discrete_sequence=px.colors.qualitative.Pastel1
        )
        lollipop_fig.update_traces(marker=dict(line=dict(width=1, color='DarkSlateGrey')))
        lollipop_fig.update_layout(**common_layout, showlegend=False)
        st.plotly_chart(lollipop_fig, use_container_width=True)


# with tab4:
#     st.header("Indicadores Sociais")
#     
#     try:
#         df_cpt = "C:/Users/joelc/Documents/Estágio/entrega-PA/entrega-PA/áreas-selecionadas/CPTF-PA.xlsx"
# 
#         if not df_cpt.empty:
#             figuras = criar_graficos_cpt(df_cpt)
#             for figura in figuras:
#                 st.plotly_chart(figura, use_container_width=True)
#         else:
#             st.warning("Nenhum dado encontrado no arquivo CPT")
#             
#     except Exception as e:
#         st.error(f"Falha ao carregar dados CPT: {str(e)}")
#         df_cpt = pd.DataFrame()
#     
#     with tab1:
#         st.plotly_chart(bar_fig, use_container_width=True)
#         st.plotly_chart(contagens_fig, use_container_width=True)
#     
#     with tab2:
#         lollipop_fig = px.bar(
#             df_csv.sort_values('Áreas de conflitos', ascending=False),
#             x='Áreas de conflitos',
#             y='Município',
#             orientation='h',
#             color='Município',
#             color_discrete_sequence=px.colors.qualitative.Pastel1
#         )
#         lollipop_fig.update_traces(marker=dict(line=dict(width=1, color='DarkSlateGrey')))
#         lollipop_fig.update_layout(**common_layout, showlegend=False)
#         st.plotly_chart(lollipop_fig, use_container_width=True)


st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background: #f5f7fa;
}
[data-testid="stHeader"] {
    background: rgba(0,116,217,0.1);
}
[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid #e1e4e8;
}
</style>
""", unsafe_allow_html=True)
