import pandas as pd
import geopandas as gpd
import streamlit as st
from utilitarios.formatacao import formatar_numero_com_pontos


def criar_cards(gdf_cnuc_filtered, gdf_sigef_filtered, invadindo_opcao):
    try:
        ucs_selecionadas = gdf_cnuc_filtered.copy()
        sigef_base = gdf_sigef_filtered.copy()
        
        if ucs_selecionadas.empty:
            return (0.0, 0.0, 0, 0, 0)

        crs_proj = "EPSG:31983"
        ucs_proj = ucs_selecionadas.to_crs(crs_proj)
        sigef_proj = sigef_base.to_crs(crs_proj)

        if invadindo_opcao and invadindo_opcao.lower() != "todos":
            mascara = sigef_proj["invadindo"].str.strip().str.lower() == invadindo_opcao.strip().lower()
            sigef_filtrado = sigef_proj[mascara].copy()
        else:
            sigef_filtrado = sigef_proj.copy()
        if not ucs_proj.empty and not sigef_filtrado.empty:
            sobreposicao = gpd.overlay(
                ucs_proj,
                sigef_filtrado,
                how='intersection',
                keep_geom_type=False,
                make_valid=True
            )
            sobreposicao['area_sobreposta'] = sobreposicao.geometry.area / 1e6
            total_sigef = sobreposicao['area_sobreposta'].sum()
            contagem_sigef_overlay = sobreposicao.shape[0]
        else:
            total_sigef = 0.0
            contagem_sigef_overlay = 0

        total_area_ucs = ucs_proj.geometry.area.sum() / 1e6
        total_alerta = ucs_selecionadas.get("alerta_km2", pd.Series([0])).sum()
        contagem_alerta_uc = ucs_selecionadas.get("c_alertas", pd.Series([0])).sum() 

        perc_alerta = (total_alerta / total_area_ucs * 100) if total_area_ucs > 0 else 0
        perc_sigef = (total_sigef / total_area_ucs * 100) if total_area_ucs > 0 else 0

        municipios = set()
        if "municipio" in ucs_selecionadas.columns:
            for munic in ucs_selecionadas["municipio"]:
                if pd.notna(munic):
                    partes = str(munic).replace(';', ',').split(',')
                    for parte in partes:
                        if parte.strip():
                            municipios.add(parte.strip().title())

        return (
            round(perc_alerta, 1),
            round(perc_sigef, 1),
            len(municipios),
            int(contagem_alerta_uc),
            int(contagem_sigef_overlay) 
        ) 

    except Exception as e:
        st.error(f"Erro crítico ao criar cards: {str(e)}")
        return (0.0, 0.0, 0, 0, 0)


def render_cards(perc_alerta, perc_sigef, total_unidades, contagem_alerta, contagem_sigef):
    col1, col2, col3, col4, col5 = st.columns(5, gap="small")
    
    card_html_template = """
    <div style="
        background: rgba(255,255,255,0.9);
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
        height: 100px;
        display: flex;
        flex-direction: column;
        justify-content: center;">
        <div style="font-size: 0.9rem; color: #6FA8DC;">{titulo}</div>
        <div style="font-size: 1.2rem; font-weight: bold; color: #2F5496;">{valor}</div>
        <div style="font-size: 0.7rem; color: #666;">{descricao}</div>
    </div>
    """
    
    perc_alerta_fmt = f"{perc_alerta:.1f}%".replace('.', ',')
    perc_sigef_fmt = f"{perc_sigef:.1f}%".replace('.', ',')
    
    with col1:
        st.markdown(
            card_html_template.format(
                titulo="Alertas / Ext. Ter.",
                valor=perc_alerta_fmt,
                descricao="Área de alertas sobre extensão territorial"
            ),
            unsafe_allow_html=True
        )
    
    with col2:
        st.markdown(
            card_html_template.format(
                titulo="CARs / Ext. Ter.", 
                valor=perc_sigef_fmt,
                descricao="CARs sobre extensão territorial"
            ),
            unsafe_allow_html=True
        )
    
    with col3:
        st.markdown(
            card_html_template.format(
                titulo="Municípios Abrangidos",
                valor=formatar_numero_com_pontos(total_unidades, 0),
                descricao="Total de municípios na análise"
            ),
            unsafe_allow_html=True
        )

    with col4:
        st.markdown(
            card_html_template.format(
                titulo="Alertas",
                valor=formatar_numero_com_pontos(contagem_alerta, 0),
                descricao="Total de registros de alertas"
            ),
            unsafe_allow_html=True
        )

    with col5:
        st.markdown(
            card_html_template.format(
                titulo="CARs",
                valor=formatar_numero_com_pontos(contagem_sigef, 0),
                descricao="Cadastros Ambientais Rurais"
            ),
            unsafe_allow_html=True
        )


def mostrar_tabela_unificada(gdf_alertas, gdf_sigef, gdf_cnuc):
    try:
        if gdf_cnuc.empty:
            st.info("Nenhum dado de UC disponível para tabela unificada")
            return
        
        # Preparar dados por UC
        dados_tabela = []
        
        for idx, uc in gdf_cnuc.iterrows():
            nome_uc = uc.get('nome_uc', 'N/A')
            area_uc_ha = uc.get('area_ha', 0) if 'area_ha' in gdf_cnuc.columns else uc.get('ha_total', 0)
            
            # Sobreposição com Alertas
            area_alertas_ha = 0
            qtd_alertas = 0
            if not gdf_alertas.empty and uc.geometry is not None:
                try:
                    alertas_proj = gdf_alertas.to_crs(epsg=31983)
                    uc_geom = gpd.GeoSeries([uc.geometry], crs=gdf_cnuc.crs).to_crs(epsg=31983).iloc[0]
                    alertas_intersect = alertas_proj[alertas_proj.intersects(uc_geom)]
                    if not alertas_intersect.empty:
                        intersecao = gpd.overlay(
                            gpd.GeoDataFrame([{'geometry': uc_geom}], crs='EPSG:31983'),
                            alertas_intersect,
                            how='intersection'
                        )
                        area_alertas_ha = intersecao.geometry.area.sum() / 10000
                        qtd_alertas = len(alertas_intersect)
                except:
                    area_alertas_ha = uc.get('alerta_ha', 0)
                    qtd_alertas = uc.get('c_alertas', 0)
            
            # Sobreposição com CAR
            area_car_ha = 0
            qtd_car = 0
            if not gdf_sigef.empty and uc.geometry is not None:
                try:
                    sigef_proj = gdf_sigef.to_crs(epsg=31983)
                    uc_geom = gpd.GeoSeries([uc.geometry], crs=gdf_cnuc.crs).to_crs(epsg=31983).iloc[0]
                    sigef_intersect = sigef_proj[sigef_proj.intersects(uc_geom)]
                    if not sigef_intersect.empty:
                        intersecao_car = gpd.overlay(
                            gpd.GeoDataFrame([{'geometry': uc_geom}], crs='EPSG:31983'),
                            sigef_intersect,
                            how='intersection'
                        )
                        area_car_ha = intersecao_car.geometry.area.sum() / 10000
                        qtd_car = len(sigef_intersect)
                except:
                    area_car_ha = uc.get('sigef_ha', 0)
                    qtd_car = uc.get('c_sigef', 0)
            
            dados_tabela.append({
                'UC': nome_uc,
                'Área UC (ha)': area_uc_ha,
                'Alertas (ha)': area_alertas_ha,
                'Qtd Alertas': qtd_alertas,
                'CAR (ha)': area_car_ha,
                'Qtd CAR': qtd_car
            })
        
        if dados_tabela:
            df_tabela = pd.DataFrame(dados_tabela)
            
            # Ordenar por área de UC decrescente
            df_tabela = df_tabela.sort_values('Área UC (ha)', ascending=False)
            
            # Formatar números
            df_tabela['Área UC (ha)'] = df_tabela['Área UC (ha)'].apply(lambda x: f"{x:,.1f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
            df_tabela['Alertas (ha)'] = df_tabela['Alertas (ha)'].apply(lambda x: f"{x:,.1f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
            df_tabela['CAR (ha)'] = df_tabela['CAR (ha)'].apply(lambda x: f"{x:,.1f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
            
            st.dataframe(df_tabela, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum dado disponível para tabela unificada")
            
    except Exception as e:
        st.error(f"Erro ao criar tabela unificada: {e}")
