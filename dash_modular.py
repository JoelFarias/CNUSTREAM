import warnings
import logging
import pandas as pd
import numpy as np
import geopandas as gpd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from typing import List, Optional, Tuple

from configuracoes.config import CONFIGURACAO_BD
from utilitarios.formatacao import formatar_numero_seguro, formatar_numero_com_pontos, wrap_label
from utilitarios.estilos import ESTILO_CSS, aplicar_patch_plotly, aplicar_layout
from utilitarios.shapefile import carregar_shapefile, carregar_shapefile_cloud_seguro, preparar_hectares
from utilitarios.dados_auxiliares import obter_anos_disponiveis, obter_estatisticas_resumo, inicializar_dados, obter_dados_ano

from processadores.gerenciador_bd import GerenciadorBancoDados
from processadores.processador_dados import ProcessadorDados
from processadores.processador_ranking import ProcessadorRanking
from processadores.processador_cpt import processar_dados_cpt_por_municipios
from processadores.processador_desmatamento import (
    processar_dados_desmatamento,
    calcular_ranking_municipios_desmatamento,
    obter_anos_disponiveis_desmatamento,
    preprocessar_dados_desmatamento_temporal,
    calcular_bounds_desmatamento,
    processar_intersecao_uc_desmatamento
)

from graficos.graficos_sobreposicoes import fig_sobreposicoes, fig_contagens_uc, fig_car_por_uc_donut
from graficos.graficos_inpe import graficos_inpe
from graficos.graficos_justica import fig_justica, fig_focos_calor_por_uc
from graficos.graficos_desmatamento import fig_desmatamento_uc, fig_desmatamento_temporal, fig_desmatamento_municipio, fig_desmatamento_mapa_pontos

from componentes.cards import criar_cards, render_cards, mostrar_tabela_unificada
from componentes.mapas import criar_figura

warnings.filterwarnings('ignore')
logging.getLogger().setLevel(logging.ERROR)

st.set_page_config(
    page_title="Dashboard de Conflitos Ambientais",
    page_icon="🌳",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(ESTILO_CSS, unsafe_allow_html=True)
aplicar_patch_plotly()

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    try:
        st.image("logo_cezar.jpg", width=300)
    except:
        st.warning("Logo não encontrada")

st.title("Análise de Conflitos em Áreas Protegidas e Territórios Tradicionais")
st.markdown("Monitoramento integrado de sobreposições em Unidades de Conservação, Terras Indígenas e Territórios Quilombolas")
st.markdown("---")

@st.cache_data(ttl=3600, show_spinner=False, max_entries=1)
def carregar_dados_iniciais():
    gdf_alertas_cols = ['ESTADO', 'MUNICIPIO', 'AREAHA', 'ANODETEC', 'DATADETEC', 'CODEALERTA', 'BIOMA', 'VPRESSAO', 'geometry']
    gdf_cnuc_cols = ['nome_uc', 'municipio', 'area_km2', 'alerta_km2', 'sigef_km2', 'c_alertas', 'c_sigef', 'geometry']
    gdf_sigef_cols = ['invadindo', 'municipio', 'geometry']
    df_proc_cols = ['municipio', 'data_ajuizamento', 'classe', 'assuntos', 'orgao_julgador']
    
    gdf_alertas_raw = carregar_shapefile("alertas.shp", calcular_percentuais=False, colunas=gdf_alertas_cols)
    gdf_alertas_raw = gdf_alertas_raw.rename(columns={"id":"id_alerta"})
    
    gdf_cnuc_raw = carregar_shapefile_cloud_seguro("cnuc.shp", colunas=gdf_cnuc_cols)
    gdf_cnuc_ha_raw = preparar_hectares(gdf_cnuc_raw)
    
    gdf_sigef_raw = carregar_shapefile("sigef.shp", calcular_percentuais=False, colunas=gdf_sigef_cols)
    gdf_sigef_raw = gdf_sigef_raw.rename(columns={"id":"id_sigef"})
    if 'MUNICIPIO' in gdf_sigef_raw.columns and 'municipio' not in gdf_sigef_raw.columns:
        gdf_sigef_raw = gdf_sigef_raw.rename(columns={'MUNICIPIO': 'municipio'})
    elif 'municipio' not in gdf_sigef_raw.columns:
        gdf_sigef_raw['municipio'] = None
    
    limites = gdf_cnuc_raw.total_bounds
    centro = {"lat": (limites[1] + limites[3]) / 2, "lon": (limites[0] + limites[2]) / 2}
    
    df_proc_raw = pd.read_csv("processos_tjpa_completo_atualizada_pronto.csv", sep=";", encoding="windows-1252", usecols=df_proc_cols)
    
    return gdf_alertas_raw, gdf_cnuc_ha_raw, gdf_sigef_raw, centro, df_proc_raw

try:
    gdf_alertas_raw, gdf_cnuc_raw, gdf_sigef_raw, centro, df_proc_raw = carregar_dados_iniciais()
    st.success("✅ Dados carregados com sucesso!")
except Exception as e:
    st.error(f"❌ Erro ao carregar dados: {e}")
    st.stop()

tabs = st.tabs(["Sobreposições", "CPT", "Justiça", "Queimadas", "Desmatamento"])

with tabs[0]:
    st.header("Sobreposições")
    with st.expander("ℹ️ Sobre esta seção", expanded=True):
        st.write("""
        Esta análise apresenta dados sobre sobreposições territoriais, incluindo:
        - Percentuais de alertas e CARs sobre extensão territorial
        - Distribuição por municípios
        - Áreas e contagens por Unidade de Conservação
        
        Os dados são provenientes do CNUC (Cadastro Nacional de Unidades de Conservação) e SIGEF (Sistema de Gestão Fundiária).
        """)
        st.markdown(
            "**Fonte Geral da Seção:** MMA - Ministério do Meio Ambiente. Cadastro Nacional de Unidades de Conservação. Brasília: MMA.",
            unsafe_allow_html=True
        )

    perc_alerta, perc_sigef, total_unidades, contagem_alerta, contagem_sigef = criar_cards(gdf_cnuc_raw, gdf_sigef_raw, None)
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        ucs_disponiveis = ['Todas'] + list(gdf_cnuc_raw['nome_uc'].unique()) if not gdf_cnuc_raw.empty and 'nome_uc' in gdf_cnuc_raw.columns else ['Todas']
        uc_selecionada = st.selectbox('Filtrar por UC:', ucs_disponiveis, key="filtro_uc")
    with col_f2:
        estados_disponiveis = ['Todos'] + list(gdf_alertas_raw['ESTADO'].unique()) if not gdf_alertas_raw.empty and 'ESTADO' in gdf_alertas_raw.columns else ['Todos']
        estado_selecionado = st.selectbox('Filtrar por Estado:', estados_disponiveis, key="filtro_estado")
    
    gdf_cnuc_filtrado = gdf_cnuc_raw.copy()
    gdf_alertas_filtrado_cards = gdf_alertas_raw.copy()
    
    if uc_selecionada != 'Todas':
        gdf_cnuc_filtrado = gdf_cnuc_filtrado[gdf_cnuc_filtrado['nome_uc'] == uc_selecionada]
    
    if estado_selecionado != 'Todos':
        gdf_alertas_filtrado_cards = gdf_alertas_filtrado_cards[gdf_alertas_filtrado_cards['ESTADO'] == estado_selecionado]
    
    total_ucs = len(gdf_cnuc_filtrado) if not gdf_cnuc_filtrado.empty else 0

    area_total_ucs = 0
    area_alertas_ucs = 0
    area_cars_ucs = 0
    
    if not gdf_cnuc_filtrado.empty:
        if 'ha_total' in gdf_cnuc_filtrado.columns:
            area_total_ucs = gdf_cnuc_filtrado['ha_total'].sum()
        if 'alerta_km2' in gdf_cnuc_filtrado.columns:
            area_alertas_ucs = gdf_cnuc_filtrado['alerta_km2'].sum() * 100 
        if 'sigef_km2' in gdf_cnuc_filtrado.columns:
            area_cars_ucs = gdf_cnuc_filtrado['sigef_km2'].sum() * 100  
    
    try:
        area_total_ucs = float(area_total_ucs) if pd.notna(area_total_ucs) else 0
        area_alertas_ucs = float(area_alertas_ucs) if pd.notna(area_alertas_ucs) else 0
        area_cars_ucs = float(area_cars_ucs) if pd.notna(area_cars_ucs) else 0
    except (ValueError, TypeError):
        area_total_ucs = 0
        area_alertas_ucs = 0
        area_cars_ucs = 0
    
    municipios_para = ['Altamira', 'São Félix do Xingu', 'Itaituba', 'Jacareacanga', 'Novo Progresso', 'Trairão']
    if estado_selecionado == 'PA' or estado_selecionado == 'Pará':
        total_municipios = 6  
    elif estado_selecionado == 'Todos':
        total_municipios = 6  
    else:
        total_municipios = len(gdf_alertas_filtrado_cards['MUNICIPIO'].unique()) if not gdf_alertas_filtrado_cards.empty and 'MUNICIPIO' in gdf_alertas_filtrado_cards.columns else 0
    
    alertas_municipios = len(gdf_alertas_filtrado_cards) if not gdf_alertas_filtrado_cards.empty else 0
    area_alertas_municipios = gdf_alertas_filtrado_cards['AREAHA'].sum() if not gdf_alertas_filtrado_cards.empty and 'AREAHA' in gdf_alertas_filtrado_cards.columns else 0
    cars_municipios = len(gdf_sigef_raw) if not gdf_sigef_raw.empty else 0
    
    try:
        area_alertas_municipios = float(area_alertas_municipios) if pd.notna(area_alertas_municipios) else 0
    except (ValueError, TypeError):
        area_alertas_municipios = 0
    
    card_template = """
    <div style="
        background-color:#F9F9FF;
        border:1px solid #E0E0E0;
        padding:1rem;
        border-radius:8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align:center;
        height:100px;
        display:flex;
        flex-direction:column;
        justify-content:center;">
        <h5 style="margin:0; font-size:0.9rem; color:#2F5496;">{0}</h5>
        <p style="margin:0; font-size:1.2rem; font-weight:bold; color:#2F5496;">{1}</p>
        <small style="color:#666;">{2}</small>
    </div>
    """
    
    st.markdown("### Unidades de Conservação:")
    cols_uc = st.columns(4, gap="small")
    titulos_uc = [
        ("UCs", formatar_numero_seguro(total_ucs, 0), "Total de Unidades de Conservação"),
        ("Área Total UCs (ha)", formatar_numero_seguro(area_total_ucs, 1), "Área total das UCs em hectares"),
        ("Área Alertas UCs (ha)", formatar_numero_seguro(area_alertas_ucs, 1), "Área de alertas em UCs (ha)"),
        ("Área CARs UCs (ha)", formatar_numero_seguro(area_cars_ucs, 1), "Área de CARs em UCs (ha)")
    ]
    for col, (t, v, d) in zip(cols_uc, titulos_uc):
        col.markdown(card_template.format(t, v, d), unsafe_allow_html=True)
    
    titulo_regiao = f"### {estado_selecionado if estado_selecionado != 'Todos' else 'Municípios'}:"
    st.markdown(titulo_regiao)
    cols_mun = st.columns(4, gap="small")
    titulos_mun = [
        ("Municípios", formatar_numero_seguro(total_municipios, 0), f"Municípios em {estado_selecionado if estado_selecionado != 'Todos' else 'todos os estados'}"),
        ("Alertas Totais", formatar_numero_seguro(alertas_municipios, 0), f"Alertas em {estado_selecionado if estado_selecionado != 'Todos' else 'todos os estados'}"),
        ("Área Alertas (ha)", formatar_numero_seguro(area_alertas_municipios, 1), "Área total de alertas (ha)"),
        ("CARs Totais", formatar_numero_seguro(cars_municipios, 0), f"CARs em {estado_selecionado if estado_selecionado != 'Todos' else 'todos os estados'}")
    ]
    for col, (t, v, d) in zip(cols_mun, titulos_mun):
        col.markdown(card_template.format(t, v, d), unsafe_allow_html=True)

    st.divider()

    row1_map, row1_chart1 = st.columns([3, 2], gap="large")
    with row1_map:
        opcoes_invadindo = ["Selecione", "Todos"] + sorted(gdf_sigef_raw["invadindo"].str.strip().unique().tolist())
        invadindo_opcao_temp = st.selectbox("Tipo de sobreposição:", opcoes_invadindo, index=0, help="Selecione o tipo de área sobreposta para análise")
        invadindo_opcao = None if invadindo_opcao_temp == "Selecione" else invadindo_opcao_temp
        gdf_cnuc_map = gdf_cnuc_raw.copy()
        gdf_sigef_map = gdf_sigef_raw.copy()
        ids_selecionados_map = []

        if invadindo_opcao and invadindo_opcao.lower() != "todos":
            sigef_filtered_for_sjoin = gdf_sigef_map[gdf_sigef_map["invadindo"].str.strip().str.lower() == invadindo_opcao.lower()]
            if not sigef_filtered_for_sjoin.empty:
                 gdf_cnuc_proj_sjoin = gdf_cnuc_map.to_crs(sigef_filtered_for_sjoin.crs)
                 gdf_filtrado_map = gpd.sjoin(gdf_cnuc_proj_sjoin, sigef_filtered_for_sjoin, how="inner", predicate="intersects")
                 if "id" in gdf_filtrado_map.columns:
                     ids_selecionados_map = gdf_filtrado_map["id"].unique().tolist()
                 elif "nome_uc" in gdf_filtrado_map.columns:
                     ids_selecionados_map = gdf_filtrado_map["nome_uc"].unique().tolist()
                 else:
                     ids_selecionados_map = gdf_filtrado_map.index.unique().tolist()
            else:
                 ids_selecionados_map = [] 

        st.subheader("Mapa de Unidades")
        fig_map = criar_figura(gdf_cnuc_map, gdf_sigef_map, None, centro, ids_selecionados_map, invadindo_opcao)
        fig_map.update_layout(height=300)
        st.plotly_chart(
            fig_map,
            use_container_width=True,
            config={"scrollZoom": True}
        )
        st.caption("Figura 1.1: Distribuição espacial das unidades de conservação.")
        with st.expander("Detalhes e Fonte da Figura 1.1"):
            st.write("""
            **Interpretação:**
            O mapa mostra a distribuição espacial das unidades de conservação na região, destacando as áreas com sobreposições selecionadas.

            **Observações:**
            - Áreas em destaque indicam unidades de conservação
            - Cores diferentes representam diferentes tipos de unidades
            - Sobreposições são destacadas quando selecionadas no filtro

            **Fonte:** MMA - Ministério do Meio Ambiente. *Cadastro Nacional de Unidades de Conservação*. Brasília: MMA, 2025. Disponível em: https://www.gov.br/mma/. Acesso em: maio de 2025.
            """)

        st.subheader("Proporção da Área do CAR sobre a UC")
        uc_names = ["Todas"] + sorted(gdf_cnuc_raw["nome_uc"].unique())
        nome_uc = st.selectbox("Selecione a Unidade de Conservação:", uc_names)
        modo_input = st.radio("Mostrar valores como:", ["Hectares (ha)", "% da UC"], horizontal=True)
        modo = "absoluto" if modo_input == "Hectares (ha)" else "percent"
        fig = fig_car_por_uc_donut(gdf_cnuc_raw, nome_uc, modo)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Figura 1.2: Comparação entre área do CAR e área restante da UC.")
        with st.expander("Detalhes e Fonte da Figura 1.2"):
            st.write("""
            **Interpretação:**
            Este gráfico mostra a proporção entre a área cadastrada no CAR e a área restante da Unidade de Conservação (UC).

            **Observações:**
            - A área restante é o que sobra da UC após considerar a área cadastrada no CAR
            - Pode ocorrer de o CAR ultrapassar 100% devido a sobreposições ou múltiplos cadastros em uma mesma área
            - Valores podem ser visualizados em hectares ou percentual, conforme seleção acima

            **Fonte:** MMA - Ministério do Meio Ambiente. *Cadastro Nacional de Unidades de Conservação*. Brasília: MMA, 2025. Disponível em: https://www.gov.br/mma/. Acesso em: maio de 2025.
            """)

    with row1_chart1:
        st.subheader("Áreas por UC")
        st.plotly_chart(fig_sobreposicoes(gdf_cnuc_raw), use_container_width=True, config={'displayModeBar': True})
        st.caption("Figura 1.3: Distribuição de áreas por unidade de conservação.")
        with st.expander("Detalhes e Fonte da Figura 1.3"):
            st.write("""
            **Interpretação:**
            O gráfico apresenta a área em hectares de cada unidade de conservação, permitindo comparar suas extensões territoriais.

            **Observações:**
            - Barras representam área em hectares
            - Linha tracejada indica a média
            - Ordenado por tamanho da área

            **Fonte:** MMA - Ministério do Meio Ambiente. *Cadastro Nacional de Unidades de Conservação*. Brasília: MMA, 2025. Disponível em: https://www.gov.br/mma/. Acesso em: maio de 2025.
            """)

        st.subheader("Contagens por UC")
        st.plotly_chart(fig_contagens_uc(gdf_cnuc_raw), use_container_width=True, config={'displayModeBar': True})
        st.caption("Figura 1.4: Contagem de sobreposições por unidade de conservação.")
        with st.expander("Detalhes e Fonte da Figura 1.4"):
            st.write("""
            **Interpretação:**
            O gráfico mostra o número de alertas e CARs sobrepostos a cada unidade de conservação.

            **Observações:**
            - Barras empilhadas mostram alertas e CARs
            - Linha tracejada indica média total
            - Ordenado por total de sobreposições

            **Fonte:** MMA - Ministério do Meio Ambiente. *Cadastro Nacional de Unidades de Conservação*. Brasília: MMA, 2025. Disponível em: https://www.gov.br/mma/. Acesso em: maio de 2025.
            """)

    st.markdown("""<div style="background-color: #fff; border-radius: 6px; padding: 1.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 0.5rem;">
        <h3 style="color: #1E1E1E; margin-top: 0; margin-bottom: 0.5rem;">Tabela Unificada</h3>
        <p style="color: #666; font-size: 0.95em; margin-bottom:0;">Visualização unificada dos dados de alertas e CNUC.</p>
    </div>""", unsafe_allow_html=True)
    mostrar_tabela_unificada(gdf_alertas_raw, gdf_sigef_raw, gdf_cnuc_raw)
    st.caption("Tabela 1.1: Dados consolidados por município.")
    with st.expander("Detalhes e Fonte da Tabela 1.1"):
        st.write("""
        **Interpretação:**
        A tabela apresenta os dados consolidados por município, incluindo:
        - Área de alertas em hectares
        - Área do CNUC em hectares

        **Observações:**
        - Valores em hectares
        - Totais na última linha
        - Células coloridas por tipo de dado

        **Fonte:** MMA - Ministério do Meio Ambiente. *Cadastro Nacional de Unidades de Conservação*. Brasília: MMA, 2025. Disponível em: https://www.gov.br/mma/. Acesso em: maio de 2025.
        """)
    
    st.divider()
    st.markdown("### Dados Completos")
    
    dados_tabs = st.tabs(["Alertas", "Unidades de Conservação", "SIGEF"])
    
    with dados_tabs[0]:
        st.markdown("**Dados brutos de alertas de desmatamento:**")
        if not gdf_alertas_raw.empty:
            df_alertas_display = gdf_alertas_raw.drop(columns=['geometry']) if 'geometry' in gdf_alertas_raw.columns else gdf_alertas_raw
            st.dataframe(df_alertas_display, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum dado de alertas disponível.")
    
    with dados_tabs[1]:
        st.markdown("**Dados brutos das Unidades de Conservação:**")
        if not gdf_cnuc_raw.empty:
            df_cnuc_display = gdf_cnuc_raw.drop(columns=['geometry']) if 'geometry' in gdf_cnuc_raw.columns else gdf_cnuc_raw
            st.dataframe(df_cnuc_display, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum dado de UCs disponível.")
    
    with dados_tabs[2]:
        st.markdown("**Dados brutos do SIGEF:**")
        if not gdf_sigef_raw.empty:
            df_sigef_display = gdf_sigef_raw.drop(columns=['geometry']) if 'geometry' in gdf_sigef_raw.columns else gdf_sigef_raw
            st.dataframe(df_sigef_display, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum dado do SIGEF disponível.")

with tabs[1]:
    st.header("Impacto Social - CPT")
    
    with st.expander("ℹ️ Sobre esta seção", expanded=True):
        st.write("""
        Esta análise apresenta dados consolidados sobre impactos sociais relacionados a conflitos agrários, incluindo:
        - Áreas de conflito
        - Assassinatos registrados
        - Conflitos por terra
        - Trabalho escravo
        - Famílias afetadas

        Os dados são provenientes da Comissão Pastoral da Terra (CPT) e foram consolidados a partir das bases de dados atualizadas.
        """)
        st.markdown(
            "**Fonte Geral da Seção:** CPT - Comissão Pastoral da Terra. Conflitos no Campo Brasil. Goiânia: CPT Nacional.",
            unsafe_allow_html=True
        )

    with st.spinner("Carregando dados CPT do PostgreSQL..."):
        try:
            import psycopg2
            
            conn_params = {
                'host': 'dataiesb.iesbtech.com.br',
                'database': '2312120036_Joel',
                'user': '2312120036_Joel',
                'password': '2312120036_Joel',
                'port': '5432'
            }
            
            conn = psycopg2.connect(**conn_params)
            
            cpt_data = {}
        
            tabelas_cpt = {
                'areas_conflito': '"CPT".areas_conflito',
                'assassinatos': '"CPT".assassinatos_consolidado_padronizado',
                'conflitos': '"CPT".conflitos_cpt',
                'trabalho_escravo': '"CPT".trabalho_escravo_consolidado'
            }
            
            total_carregado = 0
            
            for chave, nome_tabela in tabelas_cpt.items():
                try:
                    query = f"SELECT * FROM {nome_tabela}"
                    df_resultado = pd.read_sql_query(query, conn)
                    cpt_data[chave] = df_resultado
                    total_carregado += len(df_resultado)
                except Exception as e:
                    cpt_data[chave] = pd.DataFrame()
                    st.warning(f"⚠️ Erro ao carregar {chave}: {e}")
            
            conn.close()
            
            if total_carregado == 0:
                st.warning("⚠️ Nenhum dado CPT encontrado no esquema CPT")
                
        except ImportError:
            st.error("❌ psycopg2 não instalado. Execute: `pip install psycopg2-binary`")
            
            cpt_data = {
                'areas_conflito': pd.DataFrame(),
                'assassinatos': pd.DataFrame(), 
                'conflitos': pd.DataFrame(),
                'trabalho_escravo': pd.DataFrame()
            }
            
        except Exception as e:
            st.error(f"❌ Erro ao conectar ao PostgreSQL: {str(e)}")
            
            cpt_data = {
                'areas_conflito': pd.DataFrame(),
                'assassinatos': pd.DataFrame(), 
                'conflitos': pd.DataFrame(),
                'trabalho_escravo': pd.DataFrame()
            }
    
    def clean_state_data(estado_value):
        if pd.isna(estado_value):
            return None
        
        estado_str = str(estado_value).strip().upper()
        
        if estado_str in ['UF', 'NAN', 'NONE', 'NULL', '']:
            return None
        
        if estado_str.isdigit():
            return None
        
        if any(char.isdigit() for char in estado_str):
            return None
        
        if not all(char.isalpha() or char.isspace() for char in estado_str):
            return None
        
        if len(estado_str.replace(' ', '')) < 2:
            return None
        
        siglas_para_estados = {
            'AC': 'Acre', 'AL': 'Alagoas', 'AP': 'Amapá', 'AM': 'Amazonas',
            'BA': 'Bahia', 'CE': 'Ceará', 'DF': 'Distrito Federal',
            'ES': 'Espírito Santo', 'GO': 'Goiás', 'MA': 'Maranhão',
            'MT': 'Mato Grosso', 'MS': 'Mato Grosso do Sul', 'MG': 'Minas Gerais',
            'PA': 'Pará', 'PB': 'Paraíba', 'PR': 'Paraná', 'PE': 'Pernambuco',
            'PI': 'Piauí', 'RJ': 'Rio de Janeiro', 'RN': 'Rio Grande do Norte',
            'RS': 'Rio Grande do Sul', 'RO': 'Rondônia', 'RR': 'Roraima',
            'SC': 'Santa Catarina', 'SP': 'São Paulo', 'SE': 'Sergipe',
            'TO': 'Tocantins'
        }
        
        if estado_str in siglas_para_estados:
            return siglas_para_estados[estado_str]
        
        for sigla, nome_completo in siglas_para_estados.items():
            if estado_str == nome_completo.upper():
                return nome_completo
        
        return estado_str.title()
    
    estados_disponiveis_cpt = []
    for tabela_key, df_tabela in cpt_data.items():
        if not df_tabela.empty:
            colunas_estado = ['estado', 'Estado', 'ESTADO', 'uf', 'UF', 'sigla_uf', 'unidade_federacao']
            for col in colunas_estado:
                if col in df_tabela.columns:
                    estados_limpos = df_tabela[col].dropna().apply(clean_state_data).dropna().unique().tolist()
                    estados_disponiveis_cpt.extend(estados_limpos)
                    break
    
    estados_disponiveis_cpt = [estado for estado in set(estados_disponiveis_cpt) if estado and isinstance(estado, str)]
    estados_disponiveis_cpt = ['Todos'] + sorted(estados_disponiveis_cpt)
    
    if len(estados_disponiveis_cpt) > 1:
        st.markdown("### Filtros")
        estado_selecionado_cpt = st.selectbox('Filtrar por Estado:', estados_disponiveis_cpt, key="filtro_estado_cpt")
        
        if estado_selecionado_cpt != "Todos":
            cpt_data_filtrado = {}
            for tabela_key, df_tabela in cpt_data.items():
                if not df_tabela.empty:
                    colunas_estado = ['estado', 'Estado', 'ESTADO', 'uf', 'UF', 'sigla_uf', 'unidade_federacao']
                    coluna_estado_encontrada = None
                    for col in colunas_estado:
                        if col in df_tabela.columns:
                            coluna_estado_encontrada = col
                            break
                    
                    if coluna_estado_encontrada:
                        cpt_data_filtrado[tabela_key] = df_tabela[df_tabela[coluna_estado_encontrada] == estado_selecionado_cpt]
                    else:
                        cpt_data_filtrado[tabela_key] = df_tabela
                else:
                    cpt_data_filtrado[tabela_key] = df_tabela
            cpt_processed_data = processar_dados_cpt_por_municipios(cpt_data_filtrado)
            df_summary = cpt_processed_data['municipios_summary']
            cpt_data_final = cpt_data_filtrado
        else:
            cpt_processed_data = processar_dados_cpt_por_municipios(cpt_data)
            df_summary = cpt_processed_data['municipios_summary']
            cpt_data_final = cpt_data
    else:
        cpt_processed_data = processar_dados_cpt_por_municipios(cpt_data)
        df_summary = cpt_processed_data['municipios_summary']
        cpt_data_final = cpt_data
    
    st.markdown("### Resumo Geral")
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_municipios = len(df_summary)
    total_conflitos = df_summary['Total_Ocorrencias'].sum() if 'Total_Ocorrencias' in df_summary.columns else 0
    total_familias = df_summary['Total_Familias'].sum() if 'Total_Familias' in df_summary.columns else 0
    total_areas = df_summary['Areas_Conflito'].sum() if 'Areas_Conflito' in df_summary.columns else 0
    
    with col1:
        st.metric("Municípios", f"{total_municipios:,}")
    with col2:
        st.metric("Total de Ocorrências", f"{total_conflitos:,}")
    with col3:
        st.metric("Total de Famílias", f"{total_familias:,}")
    with col4:
        st.metric("Áreas em Conflito", f"{total_areas:,}")
    
    st.markdown("### Análise por Municípios")
    
    col_ranking, col_familias = st.columns(2)
    
    with col_ranking:
        st.markdown("#### Ranking de Municípios")
        
        if len(df_summary) > 0 and 'Total_Ocorrencias' in df_summary.columns:
            top_10 = df_summary.nlargest(10, 'Total_Ocorrencias')
            
            if not top_10.empty:
                fig_ranking = px.bar(
                    top_10,
                    x='Total_Ocorrencias',
                    y='Município',
                    orientation='h',
                    title="Top 10 Municípios por Total de Ocorrências",
                    color='Total_Ocorrencias',
                    color_continuous_scale='Reds'
                )
                fig_ranking.update_layout(
                    height=400,
                    yaxis={'categoryorder': 'total ascending'},
                    margin=dict(l=80, r=50, t=50, b=40)
                )
                st.plotly_chart(fig_ranking, use_container_width=True)
            else:
                st.info("Dados insuficientes para ranking")
        else:
            st.info("Dados não disponíveis")
    
    with col_familias:
        st.markdown("#### Top Municípios por Famílias Afetadas")
        
        if not df_summary.empty and 'Total_Familias' in df_summary.columns:
            df_familias = df_summary[
                (df_summary['Total_Familias'] > 0) & 
                (df_summary['Município'].notna()) & 
                (df_summary['Município'] != '') &
                (df_summary['Município'] != 'None') &
                (df_summary['Município'] != 'Nan') &
                (df_summary['Município'].str.len() > 2)
            ].copy()
            
            if not df_familias.empty:
                df_familias['Município'] = df_familias['Município'].astype(str).str.strip().str.title()
                
                top_familias = df_familias.nlargest(10, 'Total_Familias').sort_values('Total_Familias', ascending=True)
                
                familias_text = [formatar_numero_com_pontos(val, 0) for val in top_familias['Total_Familias']]
                
                fig_familias_top = go.Figure()
                fig_familias_top.add_trace(go.Bar(
                    x=top_familias['Total_Familias'],
                    y=top_familias['Município'],
                    orientation='h',
                    text=familias_text,
                    textposition='auto',
                    marker=dict(
                        color=top_familias['Total_Familias'],
                        colorscale='Reds',
                        line=dict(color='rgb(80,80,80)', width=0.5)
                    ),
                    hovertemplate='<b>%{y}</b><br>Famílias: %{text}<extra></extra>'
                ))
                
                fig_familias_top.update_layout(
                    title="Top 10 Municípios por Famílias Afetadas",
                    xaxis_title="Famílias Afetadas",
                    yaxis_title="",
                    height=400,
                    margin=dict(l=120, r=80, t=50, b=40),
                    yaxis=dict(tickfont=dict(size=10)),
                    xaxis=dict(tickfont=dict(size=10), range=[0, top_familias['Total_Familias'].max() * 1.15]),
                    showlegend=False
                )

                st.plotly_chart(fig_familias_top, use_container_width=True)
            else:
                st.info("Sem dados válidos de famílias afetadas após limpeza")
        else:
            st.info("Dados de famílias não disponíveis")
    
    st.markdown("### Evolução Temporal dos Dados CPT")
    
    with st.spinner("Carregando dados temporais..."):
        try:
            if any(len(df) > 0 for df in cpt_data_final.values()):
                df_temporal = pd.DataFrame()
            
                colunas_ano = {
                    'conflitos': ['ano', 'ano_referencia'],
                    'areas_conflito': ['Ano', 'ano', 'ano_referencia'],
                    'assassinatos': ['Ano', 'ano', 'ano_referencia'],
                    'trabalho_escravo': ['Ano', 'ano', 'ano_referencia']
                }
                
                tabelas_info = {
                    'conflitos': 'Conflitos por Terra',
                    'areas_conflito': 'Áreas em Conflito', 
                    'assassinatos': 'Assassinatos',
                    'trabalho_escravo': 'Trabalho Escravo'
                }
                
                for tabela_key, nome_tipo in tabelas_info.items():
                    if tabela_key in cpt_data_final and len(cpt_data_final[tabela_key]) > 0:
                        df_tabela = cpt_data_final[tabela_key].copy()
                        
                        ano_col = None
                        for col_possivel in colunas_ano.get(tabela_key, ['ano']):
                            if col_possivel in df_tabela.columns:
                                ano_col = col_possivel
                                break
                        
                        if ano_col:
                            try:
                                df_tabela[ano_col] = pd.to_numeric(df_tabela[ano_col], errors='coerce')
                                df_tabela = df_tabela.dropna(subset=[ano_col])
                                df_tabela = df_tabela[df_tabela[ano_col] > 1980]  
                                
                                if not df_tabela.empty:
                                    temporal_tabela = df_tabela.groupby(ano_col).size().reset_index()
                                    temporal_tabela.columns = ['ano', 'quantidade']
                                    temporal_tabela['tipo'] = nome_tipo
                                    temporal_tabela['ano'] = temporal_tabela['ano'].astype(int)
                                    
                                    df_temporal = pd.concat([df_temporal, temporal_tabela], ignore_index=True)
                                
                            except Exception as e:
                                st.warning(f"⚠️ Erro ao processar {nome_tipo}: {e}")
                        else:
                            st.warning(f"⚠️ Coluna de ano não encontrada em {nome_tipo}")
            else:
                df_temporal = pd.DataFrame()
            
            if not df_temporal.empty:
                col_filtro1, col_filtro2 = st.columns(2)
                
                with col_filtro1:
                    anos_disponiveis_temp = ['Todos'] + sorted(df_temporal['ano'].unique().tolist())
                    ano_selecionado_temp = st.selectbox('Filtrar por Ano:', anos_disponiveis_temp, key="filtro_ano_temporal")
                
                with col_filtro2:
                    tipos_disponiveis = ['Todos'] + sorted(df_temporal['tipo'].unique().tolist())
                    tipo_selecionado = st.selectbox('Filtrar por Tipo:', tipos_disponiveis, key="filtro_tipo_temporal")
                
                df_temporal_filtrado = df_temporal.copy()
                if ano_selecionado_temp != 'Todos':
                    df_temporal_filtrado = df_temporal_filtrado[df_temporal_filtrado['ano'] == ano_selecionado_temp]
                if tipo_selecionado != 'Todos':
                    df_temporal_filtrado = df_temporal_filtrado[df_temporal_filtrado['tipo'] == tipo_selecionado]
                
                if not df_temporal_filtrado.empty:
                    st.markdown("#### Evolução Temporal dos Dados CPT")
                    
                    cores_customizadas = {
                        'Conflitos por Terra': '#FF6B6B',
                        'Áreas em Conflito': '#4ECDC4', 
                        'Assassinatos': '#FF8E53',
                        'Trabalho Escravo': '#95E1D3'
                    }
                    
                    fig_temporal = px.line(
                        df_temporal_filtrado,
                        x='ano',
                        y='quantidade',
                        color='tipo',
                        markers=True,
                        title="Evolução Temporal dos Dados CPT",
                        color_discrete_map=cores_customizadas
                    )
                    
                    fig_temporal.update_layout(
                        xaxis_title="Ano",
                        yaxis_title="Número de Casos",
                        height=500,
                        legend=dict(
                            orientation="h", 
                            yanchor="bottom", 
                            y=1.02, 
                            xanchor="right", 
                            x=1,
                            title="Tipo de Dados CPT"
                        ),
                        hovermode='x unified'
                    )
                    
                    fig_temporal.update_traces(
                        mode='lines+markers',
                        line=dict(width=3),
                        marker=dict(size=8),
                        hovertemplate='<b>%{fullData.name}</b><br>Ano: %{x}<br>Casos: %{y}<extra></extra>'
                    )
                    
                    st.plotly_chart(fig_temporal, use_container_width=True)
                    st.caption("Figura 2.1: Evolução temporal dos dados registrados pela CPT.")
                    
                    with st.expander("Resumo dos Dados Temporais"):
                        resumo_temporal = df_temporal_filtrado.groupby('tipo').agg({
                            'quantidade': ['sum', 'mean', 'min', 'max'],
                            'ano': ['min', 'max', 'count']
                        }).round(1)
                        resumo_temporal.columns = ['Total Casos', 'Média Anual', 'Min Casos', 'Max Casos', 'Ano Inicial', 'Ano Final', 'Anos com Dados']
                        st.dataframe(resumo_temporal, use_container_width=True)
                else:
                    st.info("Nenhum dado encontrado com os filtros selecionados")
            else:
                st.warning("⚠️ Dados temporais não disponíveis - verifique se as tabelas contêm colunas de ano válidas")
        
        except Exception as e:
            st.error(f"❌ Erro ao carregar dados temporais: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
    
    st.markdown("### Gráficos dos Dados CPT")
    
    if not df_summary.empty and df_summary['Total_Ocorrencias'].sum() > 0:
        col_graph1, col_graph2 = st.columns(2)
        
        with col_graph1:
            tipos_dados = ['Areas_Conflito', 'Assassinatos', 'Conflitos_Terra', 'Trabalho_Escravo']
            labels_dados = ['Áreas de Conflito', 'Assassinatos', 'Conflitos por Terra', 'Trabalho Escravo']
            
            totais_tipo = []
            labels_filtradas = []
            
            for i, col in enumerate(tipos_dados):
                if col in df_summary.columns:
                    total = df_summary[col].sum()
                    if total > 0:
                        totais_tipo.append(total)
                        labels_filtradas.append(labels_dados[i])
            
            if len(totais_tipo) > 0 and sum(totais_tipo) > 0:
                fig_pizza = px.pie(
                    values=totais_tipo,
                    names=labels_filtradas,
                    title="Distribuição por Tipo de Dados CPT"
                )
                st.plotly_chart(fig_pizza, use_container_width=True)
                st.caption("Figura 2.2: Distribuição percentual dos tipos de dados da CPT.")
            else:
                st.info("Sem dados de dados CPT por tipo")
        
        with col_graph2:
            if len(df_summary) > 0:
                top_10 = df_summary.nlargest(10, 'Total_Ocorrencias')
                
                if not top_10.empty:
                    fig_top_mun = px.bar(
                        top_10,
                        x='Total_Ocorrencias',
                        y='Município',
                        orientation='h',
                        title="Top 10 Municípios por Total de Ocorrências",
                        color='Total_Ocorrencias',
                        color_continuous_scale='Reds'
                    )
                    fig_top_mun.update_layout(
                        yaxis={'categoryorder': 'total ascending'},
                        height=400
                    )
                    st.plotly_chart(fig_top_mun, use_container_width=True)
                    st.caption("Figura 2.3: Ranking dos municípios com mais ocorrências.")
                else:
                    st.info("Dados insuficientes para ranking")
            else:
                st.info("Sem dados para ranking")
        
        st.markdown("### Indicadores Consolidados")
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        
        total_ocorrencias = df_summary['Total_Ocorrencias'].sum()
        total_familias_ind = df_summary['Total_Familias'].sum()
        avg_ocorrencias = df_summary['Total_Ocorrencias'].mean() if len(df_summary) > 0 else 0
        municipios_com_conflito = len(df_summary[df_summary['Total_Ocorrencias'] > 0])
        
        with col_m1:
            st.metric("Total de Ocorrências", f"{total_ocorrencias:,}")
        with col_m2:
            st.metric("Total de Famílias", f"{total_familias_ind:,}")
        with col_m3:
            st.metric("Média por Município", f"{avg_ocorrencias:.1f}")
        with col_m4:
            st.metric("Municípios Afetados", municipios_com_conflito)
    else:
        st.info("Aguardando dados processados para exibir gráficos automáticos")
    
    st.markdown("### Análise de Violência e Trabalho Escravo")
    
    col_assassinatos, col_trabalho = st.columns(2)
    
    with col_assassinatos:
        st.markdown("#### Assassinatos no Campo")
        
        if 'Assassinatos' in df_summary.columns:
            df_assassinatos = df_summary[df_summary['Assassinatos'] > 0].copy()
            
            if not df_assassinatos.empty:
                top_assassinatos = df_assassinatos.nlargest(10, 'Assassinatos').sort_values('Assassinatos', ascending=True)
                
                assassinatos_text = [formatar_numero_com_pontos(val, 0) for val in top_assassinatos['Assassinatos']]
                
                fig_assassinatos = go.Figure()
                fig_assassinatos.add_trace(go.Bar(
                    x=top_assassinatos['Assassinatos'],
                    y=top_assassinatos['Município'],
                    orientation='h',
                    marker=dict(
                        color=top_assassinatos['Assassinatos'],
                        colorscale='Reds',
                        line=dict(color='rgb(50,50,50)', width=0.5)
                    ),
                    text=assassinatos_text,
                    textposition='auto',
                    hovertemplate='<b>%{y}</b><br>Assassinatos: %{text}<extra></extra>'
                ))
                
                fig_assassinatos.update_layout(
                    title="Municípios com Mais Assassinatos",
                    xaxis_title="Número de Assassinatos",
                    yaxis_title="",
                    height=400,
                    margin=dict(l=120, r=80, t=50, b=40),
                    yaxis=dict(tickfont=dict(size=10)),
                    xaxis=dict(tickfont=dict(size=10), range=[0, top_assassinatos['Assassinatos'].max() * 1.15]),
                    showlegend=False
                )
                
                st.plotly_chart(fig_assassinatos, use_container_width=True)
            else:
                st.info("SEM DADOS")
        else:
            st.warning("Coluna 'Assassinatos' não encontrada nos dados processados")
    
    with col_trabalho:
        st.markdown("#### Trabalho Escravo")
        
        if 'Trabalho_Escravo' in df_summary.columns:
            df_trabalho = df_summary[
                (df_summary['Trabalho_Escravo'] > 0) & 
                (df_summary['Município'].notna()) & 
                (df_summary['Município'] != '') &
                (df_summary['Município'] != 'None') &
                (df_summary['Município'] != 'Nan') &
                (df_summary['Município'].str.len() > 2)
            ].copy()
            
            if not df_trabalho.empty:
                df_trabalho['Município'] = df_trabalho['Município'].astype(str).str.strip().str.title()
                
                top_trabalho = df_trabalho.nlargest(10, 'Trabalho_Escravo').sort_values('Trabalho_Escravo', ascending=True)
                
                trabalho_text = [formatar_numero_com_pontos(val, 0) for val in top_trabalho['Trabalho_Escravo']]
                
                fig_trabalho = go.Figure()
                fig_trabalho.add_trace(go.Bar(
                    x=top_trabalho['Trabalho_Escravo'],
                    y=top_trabalho['Município'],
                    orientation='h',
                    marker=dict(
                        color=top_trabalho['Trabalho_Escravo'],
                        colorscale='Oranges',
                        line=dict(color='rgb(50,50,50)', width=0.5)
                    ),
                    text=trabalho_text,
                    textposition='auto',
                    hovertemplate='<b>%{y}</b><br>Casos de Trabalho Escravo: %{text}<extra></extra>'
                ))
                
                fig_trabalho.update_layout(
                    title="Municípios com Mais Casos de Trabalho Escravo",
                    xaxis_title="Casos de Trabalho Escravo",
                    yaxis_title="",
                    height=400,
                    margin=dict(l=120, r=80, t=50, b=40),
                    yaxis=dict(tickfont=dict(size=10)),
                    xaxis=dict(tickfont=dict(size=10), range=[0, top_trabalho['Trabalho_Escravo'].max() * 1.15]),
                    showlegend=False
                )
                
                st.plotly_chart(fig_trabalho, use_container_width=True)
            else:
                st.info("Nenhum caso válido")
        else:
            st.warning("Coluna 'Trabalho_Escravo' não encontrada nos dados processados")
    
    st.markdown("### Dados das Tabelas CPT")
    
    if 'detailed_data' in cpt_processed_data and cpt_processed_data['detailed_data']:
        tabelas_disponiveis = list(cpt_processed_data['detailed_data'].keys())
        
        nomes_amigaveis = {
            'areas_conflito': 'Áreas em Conflito',
            'assassinatos': 'Assassinatos no Campo',
            'conflitos': 'Conflitos por Terra',
            'trabalho_escravo': 'Trabalho Escravo'
        }
        
        opcoes_tabela = []
        for tabela in tabelas_disponiveis:
            nome_amigavel = nomes_amigaveis.get(tabela, tabela.replace('_', ' ').title())
            opcoes_tabela.append(f"{nome_amigavel} ({tabela})")
        
        tabela_selecionada = st.selectbox(
            "Escolha a tabela para visualizar:",
            options=opcoes_tabela,
            help="Selecione uma das tabelas do banco de dados CPT para ver seus dados detalhados"
        )
        
        tabela_real = tabela_selecionada.split('(')[1].replace(')', '')
        df_tabela_selecionada = cpt_processed_data['detailed_data'][tabela_real]
        
        if not df_tabela_selecionada.empty:
            df_tabela_filtrada = df_tabela_selecionada.copy()
            
            col_info1, col_info2, col_info3 = st.columns(3)
            with col_info1:
                st.metric("Registros totais", len(df_tabela_selecionada))
            with col_info2:
                st.metric("Registros filtrados", len(df_tabela_filtrada))
            with col_info3:
                st.metric("Colunas", len(df_tabela_filtrada.columns))
            
            if len(df_tabela_filtrada) > 0:
                st.markdown(f"**Visualizando:** {tabela_selecionada}")
                
                df_amostra = df_tabela_filtrada.head(100) if len(df_tabela_filtrada) > 100 else df_tabela_filtrada
                
                st.dataframe(
                    df_amostra,
                    use_container_width=True,
                    hide_index=True
                )
                
                if len(df_tabela_filtrada) > 100:
                    st.info(f"Mostrando as primeiras 100 linhas de {len(df_tabela_filtrada)} registros.")
            else:
                st.warning("Nenhum registro encontrado com os filtros aplicados.")
        else:
            st.warning("Tabela selecionada está vazia.")
    else:
        st.warning("Nenhuma tabela detalhada disponível.")

with tabs[2]:
    st.header("Processos Judiciais")
    
    with st.expander("ℹ️ Sobre esta seção", expanded=True):
        st.write("""
        Esta análise apresenta dados sobre processos judiciais relacionados a questões ambientais, incluindo:
        - Distribuição por municípios
        - Classes processuais
        - Assuntos
        - Órgãos julgadores
        
        Os dados são provenientes do Tribunal de Justiça do Estado do Pará.
        """)
    
    st.markdown(
        "**Fonte Geral da Seção:** CNJ - Conselho Nacional de Justiça.",
        unsafe_allow_html=True
    )
    
    if 'data_ajuizamento' in df_proc_raw.columns:
        df_proc_raw['data_ajuizamento'] = pd.to_datetime(df_proc_raw['data_ajuizamento'], errors='coerce')
    if 'ultima_atualizaçao' in df_proc_raw.columns:
        df_proc_raw['ultima_atualizaçao'] = pd.to_datetime(df_proc_raw['ultima_atualizaçao'], errors='coerce')

    if not df_proc_raw.empty:
        figs_j = fig_justica(df_proc_raw)
        
        cols = st.columns(2, gap="large")
        
        with cols[0]:
            st.markdown("""
            <div style="background:#fff;border-radius:6px;padding:1.5rem;box-shadow:0 2px 4px rgba(0,0,0,0.1);margin-bottom:0.5rem;">
            <h3 style="margin:0 0 .5rem 0;">Top 10 Municípios</h3>
            <p style="margin:0;font-size:.95em;color:#666;">Municípios com maior número de processos.</p>
            </div>
            """, unsafe_allow_html=True)
            
            if figs_j.get('mun') is not None:
                figs_j['mun'].update_layout(height=400)
                st.plotly_chart(figs_j['mun'], use_container_width=True, config={"displayModeBar": True}, key="jud_mun")
            else:
                st.warning("Gráfico de municípios não pôde ser gerado.")
            
            st.caption("Figura 4.1: Top 10 municípios com mais processos.")
            with st.expander("ℹ️ Detalhes e Fonte da Figura 4.1", expanded=False):
                st.write("""
                **Interpretação:**
                Distribuição dos processos por municípios.
                
                **Fonte:** CNJ - Conselho Nacional de Justiça.
                """)
        
        with cols[1]:
            st.markdown("""
            <div style="background:#fff;border-radius:6px;padding:1.5rem;box-shadow:0 2px 4px rgba(0,0,0,0.1);margin-bottom:0.5rem;">
            <h3 style="margin:0 0 .5rem 0;">Classes Processuais</h3>
            <p style="margin:0;font-size:.95em;color:#666;">Top 10 classes mais frequentes.</p>
            </div>
            """, unsafe_allow_html=True)
            
            if figs_j.get('class') is not None:
                figs_j['class'].update_layout(height=400)
                st.plotly_chart(figs_j['class'], use_container_width=True, config={"displayModeBar": True}, key="jud_class")
            else:
                st.warning("Gráfico de classes não pôde ser gerado.")
            st.caption("Figura 4.2: Top 10 classes processuais.")
            with st.expander("ℹ️ Detalhes e Fonte da Figura 4.2", expanded=False):
                st.write("""
                **Interpretação:**
                Distribuição dos processos por classes processuais.
                
                **Fonte:** CNJ - Conselho Nacional de Justiça.
                """)
        
        cols2 = st.columns(2, gap="large")
        
        with cols2[0]:
            st.markdown("""
            <div style="background:#fff;border-radius:6px;padding:1.5rem;box-shadow:0 2px 4px rgba(0,0,0,0.1);margin-bottom:0.5rem;">
            <h3 style="margin:0 0 .5rem 0;">Assuntos</h3>
            <p style="margin:0;font-size:.95em;color:#666;">Top 10 assuntos mais recorrentes.</p>
            </div>
            """, unsafe_allow_html=True)
            
            if figs_j.get('ass') is not None:
                figs_j['ass'].update_layout(height=400)
                st.plotly_chart(figs_j['ass'], use_container_width=True, config={"displayModeBar": True}, key="jud_ass")
            else:
                st.warning("Gráfico de assuntos não pôde ser gerado.")
            st.caption("Figura 4.3: Top 10 assuntos.")
            with st.expander("ℹ️ Detalhes e Fonte da Figura 4.3", expanded=False):
                st.write("""
                **Interpretação:**
                Distribuição dos processos por assuntos.
                
                **Fonte:** CNJ - Conselho Nacional de Justiça.
                """)
        
        with cols2[1]:
            st.markdown("""
            <div style="background:#fff;border-radius:6px;padding:1.5rem;box-shadow:0 2px 4px rgba(0,0,0,0.1);margin-bottom:0.5rem;">
            <h3 style="margin:0 0 .5rem 0;">Órgãos Julgadores</h3>
            <p style="margin:0;font-size:.95em;color:#666;">Top 10 órgãos com mais processos.</p>
            </div>
            """, unsafe_allow_html=True)
            if figs_j.get('org') is not None:
                figs_j['org'].update_layout(height=400)
                st.plotly_chart(figs_j['org'], use_container_width=True, config={"displayModeBar": True}, key="jud_org")
            else:
                st.warning("Gráfico de órgãos julgadores não pôde ser gerado.")
            st.caption("Figura 4.4: Top 10 órgãos julgadores.")
            with st.expander("ℹ️ Detalhes e Fonte da Figura 4.4", expanded=False):
                st.write("""
                **Interpretação:**
                Distribuição dos processos por órgãos julgadores.
                
                **Fonte:** CNJ - Conselho Nacional de Justiça.
                """)
        
        st.markdown("""
        <div style="background:#fff;border-radius:6px;padding:1.5rem;box-shadow:0 2px 4px rgba(0,0,0,0.1);margin:1rem 0 .5rem 0;">
        <h3 style="margin:0 0 .5rem 0;">Evolução Mensal de Processos</h3>
        <p style="margin:0;font-size:.95em;color:#666;">Variação mensal ao longo do período.</p>
        </div>
        """, unsafe_allow_html=True)
        
        if figs_j.get('temp') is not None:
            figs_j['temp'].update_layout(height=400)
            st.plotly_chart(figs_j['temp'], use_container_width=True, config={"displayModeBar": True}, key="jud_temp")
        else:
            st.warning("Gráfico de evolução temporal não pôde ser gerado.")
        st.caption("Figura 4.5: Evolução temporal dos processos judiciais.")
        with st.expander("ℹ️ Detalhes e Fonte da Figura 4.5", expanded=False):
            st.write("""
            **Interpretação:**
            Evolução mensal dos processos.
            
            **Fonte:** CNJ - Conselho Nacional de Justiça.
            """)
        
        st.markdown("""
        <div style="background:#fff;border-radius:6px;padding:1.5rem;box-shadow:0 2px 4px rgba(0,0,0,0.1);margin:1rem 0 .5rem 0;">
        <h3 style="margin:0 0 .5rem 0;">Análise Interativa de Processos</h3>
        <p style="margin:0;font-size:.95em;color:#666;">Tabela com filtros para análise detalhada dos dados.</p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            tipo_analise = st.selectbox(
                "Escolha o tipo de análise:",
                ["Municípios com mais processos", "Órgãos mais atuantes", "Classes processuais mais frequentes", "Assuntos mais recorrentes", "Dados gerais relevantes"],
                key="tipo_analise_proc"
            )
        
        with col2:
            if 'data_ajuizamento' in df_proc_raw.columns:
                df_proc_raw['ano'] = pd.to_datetime(df_proc_raw['data_ajuizamento'], errors='coerce').dt.year
                anos_disponiveis_just = sorted([ano for ano in df_proc_raw['ano'].dropna().unique() if not pd.isna(ano)])
                if anos_disponiveis_just:
                    ano_selecionado_just = st.selectbox(
                        "Filtrar por ano:",
                        ["Todos os anos"] + anos_disponiveis_just,
                        key="ano_filter_proc"
                    )
                else:
                    ano_selecionado_just = "Todos os anos"
            else:
                ano_selecionado_just = "Todos os anos"
        
        df_proc_filtered_year = df_proc_raw.copy()
        if ano_selecionado_just != "Todos os anos":
            df_proc_filtered_year = df_proc_filtered_year[df_proc_filtered_year['ano'] == ano_selecionado_just]
        
        df_filtrado = df_proc_filtered_year.copy()

        def limpar_texto(texto):
            if pd.isna(texto):
                return ""
            return str(texto).strip().title()

        if tipo_analise == "Municípios com mais processos":
            if 'municipio' in df_filtrado.columns and len(df_filtrado) > 0:
                df_filtrado['municipio'] = df_filtrado['municipio'].apply(limpar_texto)
                
                municipio_counts = df_filtrado['municipio'].value_counts().reset_index()
                municipio_counts.columns = ['Município', 'Total de Processos']
                
                if 'data_ajuizamento' in df_filtrado.columns:
                    df_filtrado['data_ajuizamento'] = pd.to_datetime(df_filtrado['data_ajuizamento'], errors='coerce')
                    datas_municipio = df_filtrado.groupby('municipio', observed=False)['data_ajuizamento'].agg(['min', 'max']).reset_index()
                    datas_municipio.columns = ['Município', 'Primeiro Processo', 'Último Processo']
                    municipio_counts = municipio_counts.merge(datas_municipio, on='Município', how='left')
                
                municipio_counts = municipio_counts.head(20)
                st.dataframe(municipio_counts, use_container_width=True)
                st.caption("Tabela 4.1: Top 20 municípios com mais processos judiciais.")
            else:
                 st.info("Dados insuficientes para gerar esta tabela.")
            
        elif tipo_analise == "Órgãos mais atuantes":
            if 'orgao_julgador' in df_filtrado.columns and len(df_filtrado) > 0:
                df_filtrado['orgao_julgador'] = df_filtrado['orgao_julgador'].apply(limpar_texto)
                
                orgao_counts = df_filtrado['orgao_julgador'].value_counts().reset_index()
                orgao_counts.columns = ['Órgão Julgador', 'Total de Processos']
                
                if 'data_ajuizamento' in df_filtrado.columns:
                    df_filtrado['data_ajuizamento'] = pd.to_datetime(df_filtrado['data_ajuizamento'], errors='coerce')
                    datas_orgao = df_filtrado.groupby('orgao_julgador', observed=False)['data_ajuizamento'].agg(['min', 'max']).reset_index()
                    datas_orgao.columns = ['Órgão Julgador', 'Primeiro Processo', 'Último Processo']
                    orgao_counts = orgao_counts.merge(datas_orgao, on='Órgão Julgador', how='left')
                
                orgao_counts = orgao_counts.head(15)
                st.dataframe(orgao_counts, use_container_width=True)
                st.caption("Tabela 4.1: Top 15 órgãos julgadores mais atuantes.")
            else:
                 st.info("Dados insuficientes para gerar esta tabela.")

        elif tipo_analise == "Classes processuais mais frequentes":
            if 'classe' in df_filtrado.columns and len(df_filtrado) > 0:
                df_filtrado['classe'] = df_filtrado['classe'].apply(limpar_texto)
                
                classe_counts = df_filtrado['classe'].value_counts().reset_index()
                classe_counts.columns = ['Classe Processual', 'Total de Processos']
                
                if 'data_ajuizamento' in df_filtrado.columns:
                    df_filtrado['data_ajuizamento'] = pd.to_datetime(df_filtrado['data_ajuizamento'], errors='coerce')
                    datas_classe = df_filtrado.groupby('classe', observed=False)['data_ajuizamento'].agg(['min', 'max']).reset_index()
                    datas_classe.columns = ['Classe Processual', 'Primeiro Processo', 'Último Processo']
                    classe_counts = classe_counts.merge(datas_classe, on='Classe Processual', how='left')
                
                classe_counts = classe_counts.head(15)
                st.dataframe(classe_counts, use_container_width=True)
                st.caption("Tabela 4.1: Top 15 classes processuais mais frequentes.")
            else:
                 st.info("Dados insuficientes para gerar esta tabela.")

        elif tipo_analise == "Assuntos mais recorrentes":
            if 'assuntos' in df_filtrado.columns and len(df_filtrado) > 0:
                df_filtrado['assuntos'] = df_filtrado['assuntos'].apply(limpar_texto)
                
                assunto_counts = df_filtrado['assuntos'].value_counts().reset_index()
                assunto_counts.columns = ['Assunto', 'Total de Processos']
                
                if 'data_ajuizamento' in df_filtrado.columns:
                    df_filtrado['data_ajuizamento'] = pd.to_datetime(df_filtrado['data_ajuizamento'], errors='coerce')
                    datas_assunto = df_filtrado.groupby('assuntos', observed=False)['data_ajuizamento'].agg(['min', 'max']).reset_index()
                    datas_assunto.columns = ['Assunto', 'Primeiro Processo', 'Último Processo']
                    assunto_counts = assunto_counts.merge(datas_assunto, on='Assunto', how='left')
                
                assunto_counts = assunto_counts.head(15)
                st.dataframe(assunto_counts, use_container_width=True)
                st.caption("Tabela 4.1: Top 15 assuntos mais recorrentes.")
            else:
                 st.info("Dados insuficientes para gerar esta tabela.")

        else: 
            if len(df_filtrado) > 0:
                colunas_preferenciais = ['municipio', 'data_ajuizamento', 'classe', 'assuntos', 'orgao_julgador']
                colunas_existentes = [col for col in colunas_preferenciais if col in df_filtrado.columns]
                
                if colunas_existentes:
                    df_relevante = df_filtrado[colunas_existentes].copy()
                    
                    for col in ['municipio', 'classe', 'assuntos', 'orgao_julgador']:
                        if col in df_relevante.columns:
                            df_relevante[col] = df_relevante[col].apply(limpar_texto)
                    
                    if 'data_ajuizamento' in df_relevante.columns:
                        df_relevante['data_ajuizamento'] = pd.to_datetime(df_relevante['data_ajuizamento'], errors='coerce')
                        df_relevante = df_relevante.sort_values('data_ajuizamento', ascending=False)
                    
                    df_amostra = df_relevante.head(500)
                    st.dataframe(df_amostra, use_container_width=True)
                    st.caption("Tabela 4.1: Dados gerais relevantes dos processos judiciais (limitado a 500 registros).")
                    
                    st.info(f"Mostrando {len(df_amostra)} de {len(df_filtrado)} processos totais.")
                else:
                    st.warning("Nenhuma coluna relevante encontrada nos dados.")
            else:
                st.info("Nenhum processo encontrado com os filtros selecionados.")
        
        with st.expander("ℹ️ Sobre esta tabela", expanded=False):
            if tipo_analise == "Municípios com mais processos":
                st.write("""
                Esta tabela mostra os municípios com maior número de processos judiciais,
                incluindo o total de processos e o período de atuação (primeiro e último processo).
                """)
            elif tipo_analise == "Órgãos mais atuantes":
                st.write("""
                Esta tabela apresenta os órgãos julgadores com maior volume de processos,
                mostrando sua atividade ao longo do tempo.
                """)
            elif tipo_analise == "Classes processuais mais frequentes":
                st.write("""
                Esta tabela mostra as classes processuais mais utilizadas nos processos judiciais,
                indicando os tipos de ações mais comuns no sistema judiciário.
                """)
            elif tipo_analise == "Assuntos mais recorrentes":
                st.write("""
                Esta tabela apresenta os assuntos mais frequentes nos processos judiciais,
                revelando as principais questões levadas ao judiciário.
                """)
            else:
                st.write("""
                Esta tabela apresenta os dados gerais mais relevantes dos processos judiciais,
                ordenados por data de ajuizamento (mais recentes primeiro).
                Limitada a 500 registros para melhor performance.
                """)
        
        st.markdown(
            "**Fonte:** CNJ - Conselho Nacional de Justiça.",
            unsafe_allow_html=True
        )
        
        st.divider()
        st.markdown("### 📊 Dados Completos")
        st.markdown("**Dados brutos dos processos judiciais:**")
        if not df_proc_raw.empty:
            st.dataframe(df_proc_raw, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum dado de processos judiciais disponível.")
    else:
        st.warning("Nenhum dado de processos disponível")

with tabs[3]:
    st.header("Focos de Calor")

    with st.expander("ℹ️ Sobre esta seção", expanded=True):
        st.write(
            "Esta análise apresenta dados sobre focos de calor detectados por satélite, incluindo:"
        )
        st.write("- Risco de fogo") 
        st.write("- Precipitação acumulada")
        st.write("- Distribuição espacial")
        st.write("- Análise por Unidades de Conservação")
        
        st.markdown("---")
        st.markdown("**Sobre o Risco de Fogo:** O valor do Risco de Fogo varia de 0.0 a 1.0 e é classificado como:")
        st.write("- **Mínimo:** abaixo de 0,15")
        st.write("- **Baixo:** de 0,15 a 0,4")
        st.write("- **Médio:** de 0,4 a 0,7")
        st.write("- **Alto:** de 0,7 a 0,95")
        st.write("- **Crítico:** acima de 0,95")
        
        st.markdown(
            "**Fonte:** BD Queimadas - INPE, 2025.",
            unsafe_allow_html=True
        )

    st.subheader("Focos de Calor em Unidades de Conservação")
    
    anos_disponiveis, df_base = inicializar_dados()
    
    if df_base is not None and not df_base.empty and not gdf_cnuc_raw.empty:
        try:
            from shapely.geometry import Point
            df_valid = df_base.dropna(subset=['Latitude', 'Longitude']).copy()
            if not df_valid.empty:
                geometry = [Point(lon, lat) for lon, lat in zip(df_valid['Longitude'], df_valid['Latitude'])]
                gdf_focos = gpd.GeoDataFrame(df_valid, geometry=geometry, crs="EPSG:4326")
                crs_proj = "EPSG:31983"
                gdf_focos_proj = gdf_focos.to_crs(crs_proj)
                gdf_cnuc_proj = gdf_cnuc_raw.to_crs(crs_proj)
                focos_in_ucs = gpd.sjoin(gdf_focos_proj, gdf_cnuc_proj, how="inner", predicate="intersects")
                
                total_focos_geral = len(df_base)
                focos_em_ucs = len(focos_in_ucs) if not focos_in_ucs.empty else 0
                percentual_ucs = (focos_em_ucs / total_focos_geral * 100) if total_focos_geral > 0 else 0
                
                col1, col2, col3 = st.columns(3, gap="medium")
                
                card_template = """
                <div style="
                    background-color:#F9F9FF;
                    border:1px solid #E0E0E0;
                    padding:1.5rem;
                    border-radius:8px;
                    box-shadow:0 2px 4px rgba(0,0,0,0.1);
                    text-align:center;
                    height:120px;
                    display:flex;
                    flex-direction:column;
                    justify-content:center;">
                    <h4 style="margin:0; font-size:1rem; color:#2F5496;">{titulo}</h4>
                    <p style="margin:0.5rem 0 0 0; font-size:1.8rem; font-weight:bold; color:#2F5496;">{valor}</p>
                    <small style="color:#666; margin:0;">{descricao}</small>
                </div>
                """
                
                with col1:
                    st.markdown(
                        card_template.format(
                            titulo="Focos em UCs",
                            valor=formatar_numero_com_pontos(focos_em_ucs, 0),
                            descricao="Total de focos detectados em UCs"
                        ),
                        unsafe_allow_html=True
                    )
                
                with col2:
                    st.markdown(
                        card_template.format(
                            titulo="Total de Focos",
                            valor=formatar_numero_com_pontos(total_focos_geral, 0),
                            descricao="Total geral de focos detectados"
                        ),
                        unsafe_allow_html=True
                    )
                
                with col3:
                    st.markdown(
                        card_template.format(
                            titulo="% em UCs",
                            valor=f"{percentual_ucs:.1f}%".replace('.', ','),
                            descricao="Percentual de focos em UCs"
                        ),
                        unsafe_allow_html=True
                    )
                
                if not focos_in_ucs.empty:
                    st.markdown("**Ranking de UCs com mais focos de calor:**")
                    focos_por_uc = focos_in_ucs.groupby('nome_uc', observed=False).size().reset_index(name='quantidade_focos')
                    focos_por_uc = focos_por_uc.sort_values('quantidade_focos', ascending=False).head(10)
                    ranking_display = focos_por_uc.copy()
                    ranking_display.index = range(1, len(ranking_display) + 1)
                    ranking_display.columns = ['Unidade de Conservação', 'Quantidade de Focos']
                    st.dataframe(ranking_display, use_container_width=True)
                else:
                    st.info("Nenhum foco de calor detectado dentro das Unidades de Conservação.")
            else:
                st.warning("Dados de coordenadas não disponíveis para análise espacial.")
        except Exception as e:
            st.warning(f"Erro ao processar focos de calor em UCs: {e}")
    else:
        st.info("Dados não disponíveis para análise de focos em UCs.")
    
    st.divider()

    if df_base is not None and not df_base.empty:
        ano_sel_graf = st.selectbox(
            'Período para gráficos:',
            anos_disponiveis,
            index=0, 
            key="ano_focos_calor_global_tab3"
        )
        
        df_graf = obter_dados_ano(ano_sel_graf, df_base)
        
        ano_param = None if ano_sel_graf == "Todos os Anos" else int(ano_sel_graf)
        display_graf = ("todo o período histórico" if ano_param is None else f"o ano de {ano_param}")

        if not df_graf.empty:
            figs = graficos_inpe(df_graf, ano_sel_graf, gdf_cnuc_raw)
            
            st.subheader("Evolução Temporal do Risco de Fogo")
            st.plotly_chart(figs['temporal'], use_container_width=True)
            st.caption(f"Figura: Evolução mensal do risco médio de fogo para {display_graf}.")

            col1, col2 = st.columns(2, gap="large")
            with col1:
                st.subheader("Top Municípios por Risco Médio de Fogo")
                st.plotly_chart(figs['top_risco'], use_container_width=True)
            with col2:
                st.subheader("Mapa de Distribuição dos Focos de Calor")
                st.plotly_chart(figs['mapa'], use_container_width=True, config={'scrollZoom': True, 'displayModeBar': True})
            
            st.divider()
            col3, col4 = st.columns(2, gap="large")
            with col3:
                st.subheader("Top Municípios por Precipitação Acumulada")
                st.plotly_chart(figs['top_precip'], use_container_width=True)
            with col4:
                st.subheader("Focos de Calor por Unidade de Conservação")
                fig_focos_uc = fig_focos_calor_por_uc(df_graf, gdf_cnuc_raw)
                if fig_focos_uc and fig_focos_uc.data:
                    st.plotly_chart(fig_focos_uc, use_container_width=True, config={'displayModeBar': True})
                    st.caption("Figura: Top 10 Unidades de Conservação com maior quantidade de focos de calor.")
                else:
                    st.info("Não foram encontrados focos de calor dentro das Unidades de Conservação para o período selecionado.")
        else:
            st.warning(f"Nenhum dado para {ano_sel_graf}.")
            
        st.divider()
        st.header("Ranking de Municípios por Indicadores de Queimadas")
        st.caption("Classifica municípios pelo maior registro de cada indicador.")
        colA, colB = st.columns(2)
        with colA:
            ano_sel_rank = st.selectbox(
                'Período para ranking:', anos_disponiveis,
                index=0, key="ano_ranking_tab3"
            )
        with colB:
            tema_rank = st.selectbox(
                'Indicador para ranking:',
                ["Maior Risco de Fogo", "Maior Precipitação (evento)", "Máx. Dias Sem Chuva"],
                key="tema_ranking"
            )
        
        ano_rank_param = None if ano_sel_rank == "Todos os Anos" else int(ano_sel_rank)
        periodo_rank = ("Todo o Período Histórico" if ano_rank_param is None else f"Ano de {ano_rank_param}")

        st.subheader(f"Ranking por {tema_rank} ({periodo_rank})")
        
        df_rank_data = obter_dados_ano(ano_sel_rank, df_base)
        
        if df_rank_data is not None and not df_rank_data.empty:
            from processadores.processador_ranking import ProcessadorRanking
            processador = ProcessadorRanking()
            df_rank, col_ord = processador.processar_ranking(df_rank_data, tema_rank, periodo_rank)
            
            if df_rank is not None and not df_rank.empty:
                st.dataframe(df_rank, use_container_width=True)
            else:
                st.info("Sem dados válidos para este ranking.")
        else:
            st.info("Sem dados válidos para este ranking.")
            
        st.divider()
        st.markdown("### 📊 Dados Completos")
        st.markdown("**Dados brutos de focos de calor:**")
        if df_base is not None and not df_base.empty:
            st.dataframe(df_base, use_container_width=True)
        else:
            st.info("Nenhum dado de focos de calor disponível.")
            
    else:
        st.error("Não foi possível carregar os dados de queimadas. Verifique a conexão com o banco de dados.")

with tabs[4]:
    st.header("Desmatamento")

    with st.expander("ℹ️ Sobre esta seção", expanded=True):
        st.write("""
        Esta análise apresenta dados sobre áreas de alerta de desmatamento, incluindo:
        - Distribuição por Unidade de Conservação
        - Evolução temporal
        - Distribuição por município
        - Distribuição espacial (Mapa)

        Os dados são provenientes do MapBiomas Alerta.
        """)
        st.markdown(
            "**Fonte Geral da Seção:** MapBiomas Alerta. Plataforma de Dados de Alertas de Desmatamento. Disponível em: https://alerta.mapbiomas.org/. Acesso em: maio de 2025.",
            unsafe_allow_html=True
        )

    st.write("**Filtro Global:**")
    anos_disponiveis = obter_anos_disponiveis_desmatamento(gdf_alertas_raw)
    ano_global_selecionado = st.selectbox('Ano de Detecção:', anos_disponiveis, key="filtro_ano_global")
    gdf_alertas_filtrado = processar_dados_desmatamento(gdf_alertas_raw, ano_global_selecionado)

    st.divider()

    col_charts, col_map = st.columns([2, 3], gap="large")

    with col_charts:
        if not gdf_cnuc_raw.empty and not gdf_alertas_filtrado.empty:
            dados_uc_desmatamento = processar_intersecao_uc_desmatamento(gdf_cnuc_raw, gdf_alertas_filtrado)
            
            if not dados_uc_desmatamento.empty:
                dados_uc_desmatamento['uc_wrap'] = dados_uc_desmatamento['nome_uc'].apply(lambda x: wrap_label(x, 15))
                
                fig_desmat_uc = px.bar(
                    dados_uc_desmatamento,
                    x='uc_wrap',
                    y='alerta_ha_total',
                    labels={"alerta_ha_total":"Área de Alertas (ha)","uc_wrap":"UC"},
                    text_auto=True,
                )
                
                alerta_text = [formatar_numero_com_pontos(val, 0) for val in dados_uc_desmatamento['alerta_ha_total']]
                
                fig_desmat_uc.update_traces(
                    customdata=np.stack([alerta_text, dados_uc_desmatamento.nome_uc], axis=-1),
                    hovertemplate=(
                        "<b>%{customdata[1]}</b><br>"
                        "Área de Alertas: %{customdata[0]} ha<extra></extra>" 
                    ),
                    text=alerta_text, 
                    textposition="outside", 
                    marker_line_color="rgb(80,80,80)",
                    marker_line_width=0.5,
                    cliponaxis=False
                )
                
                fig_desmat_uc = aplicar_layout(fig_desmat_uc, titulo="Área de Alertas (Desmatamento) por UC", tamanho_titulo=16)
                fig_desmat_uc.update_layout(height=400)
                st.subheader("Área de Alertas por UC")
                st.plotly_chart(fig_desmat_uc, use_container_width=True, config={'displayModeBar': True}, key="desmat_uc_chart")
                st.caption("Figura 6.1: Área total de alertas de desmatamento por unidade de conservação.")
                with st.expander("Detalhes e Fonte da Figura 6.1"):
                    st.write("""
                    **Interpretação:**
                    O gráfico mostra a área total (em hectares) de alertas de desmatamento detectados dentro de cada unidade de conservação.

                    **Observações:**
                    - Barras representam a área total de alertas em hectares por UC.
                    - Ordenado por área de alertas em ordem decrescente.

                    **Fonte:** MapBiomas Alerta. *Plataforma de Dados de Alertas de Desmatamento*. Disponível em: https://alerta.mapbiomas.org/. Acesso em: maio de 2025.
                    """)
            else:
                st.info("Nenhum alerta de desmatamento encontrado sobrepondo as Unidades de Conservação para o período selecionado.")
        else:
            st.warning("Dados de Unidades de Conservação ou Alertas de Desmatamento não disponíveis para esta análise.")

        st.divider()

    with col_map:
        if not gdf_alertas_filtrado.empty:
            bounds_info = calcular_bounds_desmatamento(gdf_alertas_filtrado)
            if bounds_info:
                fig_desmat_map_pts = fig_desmatamento_mapa_pontos(gdf_alertas_filtrado)
                if fig_desmat_map_pts and fig_desmat_map_pts.data:
                    fig_desmat_map_pts.update_layout(height=850)
                    st.subheader("Mapa de Alertas")
                    st.plotly_chart(
                        fig_desmat_map_pts,
                        use_container_width=True,
                        config={'scrollZoom': True},
                        key="desmat_mapa_pontos_chart"
                    )
                    st.caption("Figura 6.3: Distribuição espacial dos alertas de desmatamento.")
                    with st.expander("Detalhes e Fonte da Figura"):
                        st.write("""
                        **Interpretação:**
                        O mapa mostra a localização e a área (representada pelo tamanho e cor do ponto) dos alertas de desmatamento.

                        **Observações:**
                        - Cada ponto representa um alerta de desmatamento.
                        - O tamanho e a cor do ponto são proporcionais à área desmatada (em hectares).
                        - Áreas com maior concentração de pontos indicam maior atividade de desmatamento.

                        **Fonte:** MapBiomas Alerta. *Plataforma de Dados de Alertas de Desmatamento*. Disponível em: https://alerta.mapbiomas.org/. Acesso em: maio de 2025.
                        """)
                else:
                    st.info("Dados de alertas de desmatamento não contêm informações geográficas válidas para o mapa no período selecionado.")
            else:
                st.info("Dados de alertas de desmatamento não contêm informações geográficas válidas para o mapa no período selecionado.")
        else:
            st.warning("Dados de Alertas de Desmatamento não disponíveis para esta análise.")

    st.divider()
    st.subheader("Ranking de Municípios por Desmatamento")
    if not gdf_alertas_filtrado.empty:
        ranking_municipios = calcular_ranking_municipios_desmatamento(gdf_alertas_filtrado)
        
        if not ranking_municipios.empty:
            ranking_display = ranking_municipios.copy()
            ranking_display['Área Total (ha)'] = ranking_display['Área Total (ha)'].apply(lambda x: formatar_numero_com_pontos(x, 2))
            ranking_display['Área Média (ha)'] = ranking_display['Área Média (ha)'].apply(lambda x: f"{x:.2f}".replace('.', ','))

            st.dataframe(
                ranking_display.head(10),
                use_container_width=True,
                hide_index=True,
                height=400
            )
            st.caption("Tabela 6.1: Ranking dos municípios com maior área de alertas de desmatamento (Top 10).")
            with st.expander("Detalhes da Tabela 6.1 e Informações das Colunas"):
                st.write("""
                **Interpretação:**
                Ranking dos municípios ordenados pela área total de alertas de desmatamento detectados, com informações complementares sobre quantidade de alertas, período e características predominantes.

                **Informações das Colunas:**
                - **Posição**: Ranking baseado na área total de desmatamento
                - **Estado**: Estado onde se localiza o município
                - **Município**: Município onde se localiza o alerta
                - **Área Total (ha)**: Soma de todas as áreas de alertas do município em hectares
                - **Qtd Alertas**: Quantidade total de alertas detectados no município
                - **Área Média (ha)**: Área média por alerta no município
                - **Ano Min/Max**: Período de detecção dos alertas (primeiro e último ano)
                - **Bioma Principal**: Bioma mais frequente nos alertas do município
                - **Vetor Pressão**: Principal vetor de pressão detectado nos alertas

                **Fonte:** MapBiomas Alerta. *Plataforma de Dados de Alertas de Desmatamento*. Disponível em: https://alerta.mapbiomas.org/. Acesso em: maio de 2025.
                """)
        else:
            st.info("Dados insuficientes para gerar o ranking de municípios.")
    else:
        st.info("Dados não disponíveis para o ranking no período selecionado")

    st.divider()

    if not gdf_alertas_raw.empty:
        dados_temporais = preprocessar_dados_desmatamento_temporal(gdf_alertas_raw)
        if not dados_temporais.empty:
            fig_desmat_temp = fig_desmatamento_temporal(dados_temporais)
            if fig_desmat_temp and fig_desmat_temp.data:
                st.subheader("Evolução Temporal de Alertas")
                fig_desmat_temp.update_layout(height=400)
                st.plotly_chart(fig_desmat_temp, use_container_width=True, config={'displayModeBar': True}, key="desmat_temporal_chart")
                st.caption("Figura 6.4: Evolução mensal da área total de alertas de desmatamento.")
                with st.expander("Detalhes e Fonte da Figura 6.4"):
                    st.write("""
                    **Interpretação:**
                    O gráfico de linha mostra a variação mensal da área total (em hectares) de alertas de desmatamento ao longo do tempo.

                    **Observações:**
                    - Cada ponto representa a soma da área de alertas para um determinado mês.
                    - A linha conecta os pontos para mostrar a tendência temporal.
                    - Valores são exibidos acima de cada ponto para facilitar a leitura.

                    **Fonte:** MapBiomas Alerta. *Plataforma de Dados de Alertas de Desmatamento*. Disponível em: https://alerta.mapbiomas.org/. Acesso em: maio de 2025.
                    """)
            else:
                st.info("Dados de alertas de desmatamento não contêm informações temporais válidas.")
        else:
            st.info("Dados de alertas de desmatamento não contêm informações temporais válidas.")
    
    st.divider()
    st.markdown("### 📊 Dados Completos")
    st.markdown("**Dados brutos de alertas de desmatamento:**")
    if not gdf_alertas_raw.empty:
        df_alertas_display = gdf_alertas_raw.drop(columns=['geometry']) if 'geometry' in gdf_alertas_raw.columns else gdf_alertas_raw
        st.dataframe(df_alertas_display, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum dado de alertas de desmatamento disponível.")

st.markdown("---")
st.markdown("**Dashboard Modular** | Desenvolvido com Streamlit | Dados: INPE, MMA, CPT, TJ-PA")
