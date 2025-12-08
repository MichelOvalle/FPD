import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Dashboard FPD2 Pro", layout="wide")
st.title("📊 Monitor FPD")

# Configuraciones
MESES_A_EXCLUIR = 2    
VENTANA_MESES = 24     
MIN_CREDITOS_RANKING = 5 

# --- 2. FUNCIÓN DE CARGA ---
def load_data():
    
    archivo = 'fpd gemini.xlsx'
    if not os.path.exists(archivo):
        archivo = 'fpd gemini.csv'
        if not os.path.exists(archivo):
             st.error("⚠️ No se encontró 'fpd gemini.xlsx' ni 'fpd gemini.csv'. Asegúrate de que el archivo de datos esté en la misma carpeta que el script.")
             st.stop()
    
    try:
        if archivo.endswith('.xlsx'):
            df = pd.read_excel(archivo)
        else:
            df = pd.read_csv(archivo, encoding='latin1')
    except Exception as e:
        st.error(f"Error leyendo el archivo {archivo}: {e}")
        st.stop()

    df.columns = [str(c).lower().strip() for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]

    col_cosecha = next((c for c in df.columns if 'cosecha' in c), None)
    col_fpd2 = next((c for c in df.columns if 'fpd2' in c), None)
    if not col_fpd2: col_fpd2 = next((c for c in df.columns if 'fpd' in c), None)
    col_np = next((c for c in df.columns if 'np' == c or 'np' in c.split('_')), None) 
    col_monto = next((c for c in df.columns if 'monto' in c and 'otorgado' in c), None)
    if not col_monto: col_monto = next((c for c in df.columns if 'monto' in c), None)

    if not col_cosecha or not col_fpd2:
        st.error(f"Faltan columnas clave. Encontré: {list(df.columns)}")
        st.stop()

    df_clean = df.copy()
    
    # Procesamiento Fechas
    df_clean['cosecha_str'] = df_clean[col_cosecha].astype(str).str.replace(r'\.0$', '', regex=True)
    try:
        df_clean['fecha_dt'] = pd.to_datetime(df_clean['cosecha_str'], format='%Y%m', errors='coerce')
    except:
        df_clean['fecha_dt'] = pd.to_datetime(df_clean['cosecha_str'], errors='coerce')

    df_clean['anio'] = df_clean['fecha_dt'].dt.year.fillna(0).astype(int).astype(str)
    df_clean['mes_num'] = df_clean['fecha_dt'].dt.month.fillna(0).astype(int)
    
    mapa_meses = {1:'Ene', 2:'Feb', 3:'Mar', 4:'Abr', 5:'May', 6:'Jun', 7:'Jul', 8:'Ago', 9:'Sep', 10:'Oct', 11:'Nov', 12:'Dic', 0:'SinDato'}
    df_clean['mes_nombre'] = df_clean['mes_num'].map(mapa_meses)
    
    df_clean['is_fpd2'] = df_clean[col_fpd2].astype(str).apply(lambda x: 1 if 'FPD' in x.upper() else 0)
    df_clean['is_np'] = df_clean[col_np].astype(str).apply(lambda x: 1 if 'NP' in x.upper() else 0) if col_np else 0

    if col_monto: df_clean['monto'] = pd.to_numeric(df_clean[col_monto], errors='coerce').fillna(0)
    else: df_clean['monto'] = 0

    def find_best_column(dataframe, candidates_priority, fallback_search_term):
        for cand in candidates_priority:
            if cand in dataframe.columns: return cand
        possible = [c for c in dataframe.columns if fallback_search_term in c and 'id' not in c]
        if possible: return possible[0]
        return None

    c_suc = find_best_column(df_clean, ['sucursal', 'nombre_sucursal'], 'sucursal')
    df_clean['sucursal'] = df_clean[c_suc].fillna('Sin Dato').astype(str) if c_suc else 'Sin Dato'

    c_uni = find_best_column(df_clean, ['unidad_regional', 'regional', 'region', 'unidad'], 'regional')
    if not c_uni: c_uni = find_best_column(df_clean, [], 'unidad')
    df_clean['unidad'] = df_clean[c_uni].fillna('Sin Dato').astype(str) if c_uni else 'Sin Dato'

    c_prod = find_best_column(df_clean, ['producto_agrupado', 'nombre_producto', 'producto'], 'producto')
    df_clean['producto'] = df_clean[c_prod].fillna('Sin Dato').astype(str) if c_prod else 'Sin Dato'

    c_ori = find_best_column(df_clean, ['origen2', 'origen'], 'origen')
    df_clean['origen'] = df_clean[c_ori].fillna('Sin Dato').astype(str).str.title() if c_ori else 'Sin Dato'

    c_tip = find_best_column(df_clean, ['tipo_cliente', 'tipo'], 'cliente')
    df_clean['tipo_cliente'] = df_clean[c_tip].fillna('Sin Dato').astype(str) if c_tip else 'Sin Dato'
    
    df_clean['cosecha_x'] = df_clean['cosecha_str']
    
    return df_clean

# Cargar DATOS
df = load_data()

# --- 3. CONFIGURACIÓN DE VENTANA DE TIEMPO (AHORA FIJA) ---
todas = sorted(df['cosecha_x'].unique())
maduras = todas[:-MESES_A_EXCLUIR] if len(todas) > MESES_A_EXCLUIR else todas
visualizar = maduras[-VENTANA_MESES:] if len(maduras) > VENTANA_MESES else maduras

sel_cosecha = visualizar

# --- 4. FILTROS DE NEGOCIO EN BARRA LATERAL ---
st.sidebar.header("🎯 Filtros Generales")
st.sidebar.info("La ventana de análisis temporal (24 meses) es fija. Los filtros de negocio aplican solo a la Pestaña 1.")

st.sidebar.divider()
st.sidebar.markdown("**Filtros de Negocio**")
sel_uni = st.sidebar.multiselect("1. Unidad Regional:", sorted(df['unidad'].unique()))
sel_suc = st.sidebar.multiselect("2. Sucursal:", sorted(df['sucursal'].unique()))
sel_pro = st.sidebar.multiselect("3. Producto Agrupado:", sorted(df['producto'].unique()))
sel_tip = st.sidebar.multiselect("4. Tipo de Cliente:", sorted(df['tipo_cliente'].unique()))

# --- 5. PREPARACIÓN BASE FILTRADA (PESTAÑA 1) ---
df_base = df.copy()

if sel_uni: df_base = df_base[df_base['unidad'].isin(sel_uni)]
if sel_suc: df_base = df_base[df_base['sucursal'].isin(sel_suc)]
if sel_pro: df_base = df_base[df_base['producto'].isin(sel_pro)]
if sel_tip: df_base = df_base[df_base['tipo_cliente'].isin(sel_tip)]

if df_base.empty:
    st.sidebar.warning("⚠️ Los filtros seleccionados no devolvieron datos para el Monitor.")

df_top = df_base[df_base['cosecha_x'].isin(sel_cosecha)]

# =========================================================
# --- CÁLCULO CENTRALIZADO DEL BOTTOM 10 DE SUCURSALES ---
# (Basado en la misma data filtrada que Tab 1)
# =========================================================

worst_10_sucursales = []
df_ranking_calc = pd.DataFrame()

if not df_top.empty:
    # 1. Base para el Ranking (Excluir '999' y 'nomina')
    mask_999 = df_top['sucursal'].astype(str).str.contains("999", na=False)
    mask_nomina = df_top['sucursal'].astype(str).str.lower().str.contains("nomina colaboradores", na=False)
    df_ranking_calc = df_top[~(mask_999 | mask_nomina)]
    
    r_calc = df_ranking_calc.groupby('sucursal')['is_fpd2'].agg(['count', 'mean']).reset_index()
    r_clean_calc = r_calc[r_calc['count'] >= MIN_CREDITOS_RANKING]

    # 2. Obtener el Bottom 10 (peores tasas)
    if not r_clean_calc.empty:
        bottom_10_df = r_clean_calc.sort_values('mean', ascending=False).head(10)
        worst_10_sucursales = bottom_10_df['sucursal'].tolist()


# =========================================================
# --- PESTAÑAS ---
# =========================================================
tab1, tab2, tab3 = st.tabs(["📉 Monitor FPD", "📋 Resumen Ejecutivo", "🎯 Insights Estratégicos"])

# --- PESTAÑA 1: MONITOR FPD ---
with tab1:
    if df_base.empty:
        st.warning("No hay datos para mostrar con los filtros actuales.")
    else:
        st.markdown("### Resumen Operativo")
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("1. Tendencia Global")
            if not df_top.empty:
                d = df_top.groupby('cosecha_x')['is_fpd2'].mean().reset_index()
                d['FPD2 %'] = d['is_fpd2']*100
                fig = px.line(d, x='cosecha_x', y='FPD2 %', markers=True, text=d['FPD2 %'].apply(lambda x: f'{x:.1f}%'))
                fig.update_traces(line_color='#FF4B4B', line_width=3, textposition="top center")
                fig.update_layout(xaxis_type='category')
                st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.subheader("2. Físico vs Digital")
            mask = df_top['origen'].str.contains('Fisico|Digital', case=False, na=False)
            d_comp = df_top[mask].copy()
            if not d_comp.empty:
                d = d_comp.groupby(['cosecha_x', 'origen'])['is_fpd2'].mean().reset_index()
                d['FPD2 %'] = d['is_fpd2']*100
                fig = px.line(d, x='cosecha_x', y='FPD2 %', color='origen', markers=True, color_discrete_map={'Fisico': '#1f77b4', 'Digital': '#2ca02c'})
                fig.update_layout(xaxis_type='category', legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sin datos de Origen.")

        st.divider()
        
        st.subheader("3. Ranking de Sucursales")
        
        # Reutilizar el cálculo r_clean_calc
        if not df_ranking_calc.empty and not r_clean_calc.empty:
            c1, c2 = st.columns(2)
            c1.dataframe(r_clean_calc.sort_values('mean', ascending=False).head(10)[['sucursal', 'count', 'mean']].rename(columns={'mean': 'FPD2 %'}), hide_index=True, use_container_width=True, column_config={"FPD2 %": st.column_config.ProgressColumn("FPD2 %", format="%.2f%%", min_value=0, max_value=r_clean_calc['mean'].max())})
            c2.dataframe(r_clean_calc.sort_values('mean', ascending=True).head(10)[['sucursal', 'count', 'mean']].rename(columns={'mean': 'FPD2 %'}), hide_index=True, use_container_width=True, column_config={"FPD2 %": st.column_config.ProgressColumn("FPD2 %", format="%.2f%%", min_value=0, max_value=r_clean_calc['mean'].max())})

        st.divider()
        
        st.subheader("4. Análisis Detallado")
        cy1, cy2 = st.columns(2)

        with cy1:
            st.markdown("##### Comparativo Anual (Mes a Mes)")
            todas_neg = sorted(df_base['cosecha_x'].unique())
            cosechas_maduras_globales = todas_neg[:-MESES_A_EXCLUIR] if len(todas_neg) > MESES_A_EXCLUIR else todas_neg
            
            df_yoy = df_base[
                (df_base['cosecha_x'].isin(cosechas_maduras_globales)) & 
                (df_base['anio'].isin(['2023', '2024', '2025']))
            ].copy()
            
            if not df_yoy.empty:
                dy = df_yoy.groupby(['mes_num', 'mes_nombre', 'anio'])['is_fpd2'].mean().reset_index()
                dy['FPD2 %'] = dy['is_fpd2'] * 100
                dy = dy.sort_values('mes_num')
                dy['etiqueta'] = dy.apply(lambda r: f"{r['FPD2 %']:.1f}%" if r['anio'] == '2025' else None, axis=1)
                
                fig_yoy = px.line(dy, x='mes_nombre', y='FPD2 %', color='anio', markers=True, text='etiqueta',
                    color_discrete_map={'2023': '#999999', '2024': '#1f77b4', '2025': '#d62728'})
                fig_yoy.update_traces(textposition="top center")
                fig_yoy.update_layout(xaxis_title="Mes", yaxis_title="% FPD", hovermode="x unified", legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center", title=None), margin=dict(b=50))
                st.plotly_chart(fig_yoy, use_container_width=True)
            else:
                st.info("No hay datos históricos.")

        with cy2:
            st.markdown(f"##### Histórico Indicadores ({visualizar[0]} - {visualizar[-1]})")
            df_ind = df_base[df_base['cosecha_x'].isin(visualizar)].copy()
            if not df_ind.empty:
                dh = df_ind.groupby('cosecha_x')[['is_fpd2', 'is_np']].mean().reset_index()
                dh['% FPD'] = dh['is_fpd2'] * 100
                dh['% NP'] = dh['is_np'] * 100
                dh_melt = dh.melt(id_vars=['cosecha_x'], value_vars=['% FPD', '% NP'], var_name='Indicador', value_name='Porcentaje')
                dh_melt['etiqueta'] = dh_melt['Porcentaje'].map('{:.1f}%'.format)
                fig_ind = px.line(dh_melt, x='cosecha_x', y='Porcentaje', color='Indicador', markers=True, text='etiqueta', color_discrete_map={'% FPD': '#d62728', '% NP': '#ff7f0e'})
                fig_ind.update_traces(textposition="top center")
                fig_ind.update_layout(xaxis_title="Cosecha", yaxis_title="%", xaxis_type='category', hovermode="x unified", legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center", title=None), margin=dict(b=50))
                st.plotly_chart(fig_ind, use_container_width=True)
            else:
                st.info("No hay datos en la ventana seleccionada.")

        st.divider()
        st.subheader("5. Evolución por Tipo de Cliente")
        df_tipo = df_base[df_base['cosecha_x'].isin(visualizar)].copy()
        df_tipo = df_tipo[~df_tipo['tipo_cliente'].astype(str).str.lower().str.contains('former')]
        
        if not df_tipo.empty:
            dt = df_tipo.groupby(['cosecha_x', 'tipo_cliente'])['is_fpd2'].mean().reset_index()
            dt['FPD2 %'] = dt['is_fpd2'] * 100
            dt['etiqueta'] = dt['FPD2 %'].map('{:.1f}%'.format)
            fig_tipo = px.line(dt, x='cosecha_x', y='FPD2 %', color='tipo_cliente', markers=True, text='etiqueta', title=f"Comportamiento FPD por Tipo Cliente ({visualizar[0]} - {visualizar[-1]})")
            fig_tipo.update_traces(textposition="top center")
            fig_tipo.update_layout(xaxis_title="Cosecha", yaxis_title="% FPD", xaxis_type='category', hovermode="x unified", legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center", title=None))
            st.plotly_chart(fig_tipo, use_container_width=True)
        else:
            st.info("No hay datos para la gráfica de Tipo de Cliente.")

# --- PESTAÑA 2: RESUMEN EJECUTIVO (GLOBAL) ---
with tab2:
    st.header("📋 Resumen Ejecutivo Global (Sin Filtros)")
    
    if len(maduras) < 2:
        st.error("No hay suficientes cosechas maduras.")
    else:
        mes_actual = maduras[-1]
        mes_anterior = maduras[-2]
        
        # --- BLOQUE 1: UNIDAD REGIONAL (GLOBAL) ---
        st.markdown(f"#### 🌍 Análisis Regional ({mes_actual})")
        df_resumen = df[df['cosecha_x'] == mes_actual]
        df_resumen_clean = df_resumen[~df_resumen['unidad'].astype(str).str.lower().str.contains("pr nominas", case=False)]
        resumen_unidad = df_resumen_clean.groupby('unidad')['is_fpd2'].mean().reset_index()
        
        if not resumen_unidad.empty:
            mejor = resumen_unidad.loc[resumen_unidad['is_fpd2'].idxmin()]
            peor = resumen_unidad.loc[resumen_unidad['is_fpd2'].idxmax()]
            
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                st.markdown(f"""
                <div style='background-color: #e8f5e9; padding: 20px; border-radius: 12px; border: 1px solid #c8e6c9;'>
                    <h3 style='color: #2e7d32; margin:0;'>🟢 Mejor Región</h3>
                    <h4 style='margin:5px 0;'>{mejor['unidad']}</h4>
                    <h2 style='color: #2e7d32; font-size: 2.5em; margin: 0;'>{mejor['is_fpd2']*100:.2f}%</h2>
                </div>
                """, unsafe_allow_html=True)
            with col_r2:
                st.markdown(f"""
                <div style='background-color: #ffebee; padding: 20px; border-radius: 12px; border: 1px solid #ffcdd2;'>
                    <h3 style='color: #c62828; margin:0;'>🔴 Mayor Riesgo</h3>
                    <h4 style='margin:5px 0;'>{peor['unidad']}</h4>
                    <h2 style='color: #c62828; font-size: 2.5em; margin: 0;'>{peor['is_fpd2']*100:.2f}%</h2>
                </div>
                """, unsafe_allow_html=True)
        
        st.divider()

        # --- BLOQUE 2: PRODUCTOS (GLOBAL) ---
        st.markdown(f"#### 📦 Análisis de Productos ({mes_actual})")
        
        resumen_prod = df_resumen.groupby('producto').agg(
            tasa=('is_fpd2', 'mean'),
            conteo_total=('is_fpd2', 'count'),
            conteo_fpd=('is_fpd2', 'sum')
        ).reset_index()
        
        resumen_prod = resumen_prod[resumen_prod['conteo_total'] >= MIN_CREDITOS_RANKING]
        promedio_global = df_resumen['is_fpd2'].mean()
        
        if not resumen_prod.empty:
            prod_mejor = resumen_prod.sort_values(by=['tasa', 'conteo_total'], ascending=[True, False]).iloc[0]
            prod_peor = resumen_prod.sort_values(by=['tasa', 'conteo_total'], ascending=[False, False]).iloc[0]
            
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                st.markdown(f"""
                <div style='background-color: #e3f2fd; padding: 20px; border-radius: 12px; border: 1px solid #bbdefb;'>
                    <h3 style='color: #1565c0; margin:0;'>🏆 Mejor Producto</h3>
                    <h4 style='margin:5px 0;'>{prod_mejor['producto']}</h4>
                    <h2 style='color: #1565c0; font-size: 2.5em; margin: 0;'>{prod_mejor['tasa']*100:.2f}%</h2>
                    <p style='color: #555; margin-top: 10px;'>
                        <b>{int(prod_mejor['conteo_fpd'])}</b> créditos en FPD<br>
                        de <b>{int(prod_mejor['conteo_total'])}</b> colocados.
                    </p>
                </div>
                """, unsafe_allow_html=True)
            with col_p2:
                st.markdown(f"""
                <div style='background-color: #fff3e0; padding: 20px; border-radius: 12px; border: 1px solid #ffe0b2;'>
                    <h3 style='color: #e65100; margin:0;'>⚠️ Mayor Riesgo FPD</h3>
                    <h4 style='margin:5px 0;'>{prod_peor['producto']}</h4>
                    <h2 style='color: #e65100; font-size: 2.5em; margin: 0;'>{prod_peor['tasa']*100:.2f}%</h2>
                    <p style='color: #555; margin-top: 10px;'>
                        <b>{int(prod_peor['conteo_fpd'])}</b> créditos en FPD<br>
                        de <b>{int(prod_peor['conteo_total'])}</b> colocados.
                    </p>
                </div>
                """, unsafe_allow_html=True)
            
            with st.expander("Ver tabla completa de productos (Coloreada)"):
                df_view = resumen_prod.copy()
                df_view = df_view.rename(columns={'producto': 'Producto', 'conteo_total': 'Total Créditos', 'conteo_fpd': 'Créditos FPD', 'tasa': 'Tasa %'})
                df_view = df_view.sort_values('Tasa %', ascending=False)
                
                def estilo_tasas(val):
                    color = '#d32f2f' if val > promedio_global else '#2e7d32'
                    weight = 'bold'
                    return f'color: {color}; font-weight: {weight}'

                st.dataframe(
                    df_view.style
                    .applymap(estilo_tasas, subset=['Tasa %'])
                    .format({'Tasa %': '{:.2%}'})
                    .applymap(lambda x: 'font-weight: bold', subset=['Producto']),
                    use_container_width=True,
                    hide_index=True
                )
        else:
            st.warning("No hay productos con suficientes créditos para evaluar.")

        st.divider()

        # --- BLOQUE 3: COMPARATIVA SUCURSALES (GLOBAL) ---
        st.markdown(f"#### 🏦 Comparativa de Sucursales ({mes_anterior} vs {mes_actual})")
        
        df_comp = df[df['cosecha_x'].isin([mes_anterior, mes_actual])].copy()
        mask_999 = df_comp['sucursal'].astype(str).str.contains("999", na=False)
        mask_nom = df_comp['sucursal'].astype(str).str.lower().str.contains("nomina colaboradores", na=False)
        df_comp = df_comp[~(mask_999 | mask_nom)]
        
        pivot = df_comp.groupby(['sucursal', 'cosecha_x']).agg(tasa=('is_fpd2', 'mean'), conteo=('is_fpd2', 'count')).reset_index()
        
        pivot_tasa = pivot.pivot(index='sucursal', columns='cosecha_x', values='tasa')
        pivot_count = pivot.pivot(index='sucursal', columns='cosecha_x', values='conteo')
        
        if mes_actual in pivot_tasa.columns and mes_anterior in pivot_tasa.columns:
            validas = pivot_count[(pivot_count[mes_actual] >= MIN_CREDITOS_RANKING) & (pivot_count[mes_anterior] > 0)].index
            df_final_comp = pivot_tasa.loc[validas]
            
            if not df_final_comp.empty:
                suc_mejor = df_final_comp[mes_actual].idxmin()
                val_mejor_act = df_final_comp.loc[suc_mejor, mes_actual] * 100
                val_mejor_ant = df_final_comp.loc[suc_mejor, mes_anterior] * 100
                
                suc_peor = df_final_comp[mes_actual].idxmax()
                val_peor_act = df_final_comp.loc[suc_peor, mes_actual] * 100
                val_peor_ant = df_final_comp.loc[suc_peor, mes_anterior] * 100
                
                st.markdown(f"""
                <div style='background-color: #fff8e1; padding: 15px; border-radius: 10px; border-left: 5px solid #ffb300;'>
                    <p>🏆 <b>Mejor Comportamiento:</b> <b>{suc_mejor}</b><br>
                    Pasó de {val_mejor_ant:.1f}% ➡️ <b>{val_mejor_act:.1f}%</b>.</p>
                </div>
                <div style='background-color: #ffebee; padding: 15px; border-radius: 10px; border-left: 5px solid #d32f2f; margin-top: 10px;'>
                    <p>📉 <b>Mayor Deterioro:</b> <b>{suc_peor}</b><br>
                    Pasó de {val_peor_ant:.1f}% ➡️ <b>{val_peor_act:.1f}%</b>.</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("Sin datos suficientes para comparar.")

        st.divider()
        
        # --- BLOQUE 4: DETALLE PRODUCTO POR SUCURSAL (BOTTOM 10) ---
        st.markdown("#### 4. Detalle de Riesgo por Producto y Sucursal (Bottom 10)")
        st.markdown("⚠️ **Nota:** Esta tabla muestra solo las **10 sucursales con mayor FPD** según los filtros de negocio aplicados en el panel lateral.")

        if worst_10_sucursales:
            # 1. Usar df_base (filtrado por sidebar) y el mes actual
            df_detalle = df_base[df_base['cosecha_x'] == mes_actual].copy()
            
            # 2. FILTRAR POR EL BOTTOM 10 CALCULADO
            df_detalle = df_detalle[df_detalle['sucursal'].isin(worst_10_sucursales)]
            
            # Limpieza básica para evitar outliers
            df_detalle = df_detalle[~df_detalle['sucursal'].astype(str).str.contains("999", na=False)]
            
            if not df_detalle.empty:
                # 3. Calcular FPD % por Sucursal y Producto
                pivot_data = df_detalle.groupby(['sucursal', 'producto'])['is_fpd2'].mean().reset_index()
                
                # 4. Pivotar la tabla
                table_pivot = pivot_data.pivot(index='sucursal', columns='producto', values='is_fpd2')
                
                # 5. Aplicar formato condicional (Heatmap)
                st.dataframe(
                    table_pivot.style
                    .background_gradient(cmap='RdYlGn_r', axis=None) 
                    .format("{:.2%}", na_rep="-"),
                    use_container_width=True
                )
            else:
                st.warning(f"No hay datos para la cosecha {mes_actual} con el Bottom 10 de sucursales filtrado.")

        else:
            st.info("No hay suficientes datos para calcular el Bottom 10 de sucursales con los filtros de negocio aplicados.")

# --- PESTAÑA 3: INSIGHTS ESTRATÉGICOS (GLOBAL) ---
with tab3:
    st.header("🎯 Insights Estratégicos & Análisis Profundo")
    st.markdown("Esta sección utiliza la **base completa** (global) para detectar patrones de riesgo y oportunidades.")
    
    if len(maduras) < 6:
        st.warning("Se necesitan al menos 6 meses de historia madura para generar el mapa de calor.")
    else:
        # 1. HEATMAP DE RIESGO REGIONAL (Últimos 6 meses)
        st.subheader("1. Mapa de Calor de Riesgo Regional (Últimos 6 meses)")
        ultimos_6 = maduras[-6:]
        df_heat = df[df['cosecha_x'].isin(ultimos_6)].copy()
        df_heat = df_heat[~df_heat['unidad'].astype(str).str.lower().str.contains("pr nominas", case=False)]
        
        pivot_heat = df_heat.groupby(['unidad', 'cosecha_x'])['is_fpd2'].mean().reset_index()
        pivot_heat['FPD2 %'] = pivot_heat['is_fpd2'] * 100
        
        heatmap_data = pivot_heat.pivot(index='unidad', columns='cosecha_x', values='FPD2 %')
        
        fig_heat = px.imshow(
            heatmap_data,
            labels=dict(x="Cosecha", y="Unidad Regional", color="% FPD"),
            x=heatmap_data.columns,
            y=heatmap_data.index,
            text_auto='.1f',
            color_continuous_scale='RdYlGn_r',
            aspect="auto"
        )
        fig_heat.update_xaxes(type='category') 
        fig_heat.update_layout(title="Evolución del Riesgo por Región")
        st.plotly_chart(fig_heat, use_container_width=True)

    st.divider()

    # 2. PARETO DE SUCURSALES (80/20)
    st.subheader("2. Ley de Pareto: ¿Quién genera el riesgo?")
    st.markdown("Identificamos qué porcentaje de sucursales concentra el 80% de los casos de FPD en la **última cosecha madura**.")
    
    ultima = maduras[-1]
    df_pareto = df[df['cosecha_x'] == ultima].copy()
    
    mask_999 = df_pareto['sucursal'].astype(str).str.contains("999", na=False)
    mask_nom = df_pareto['sucursal'].astype(str).str.lower().str.contains("nomina colaboradores", na=False)
    df_pareto = df_pareto[~(mask_999 | mask_nom)]
    
    pareto = df_pareto.groupby('sucursal')['is_fpd2'].sum().reset_index()
    pareto = pareto.sort_values('is_fpd2', ascending=False)
    pareto = pareto[pareto['is_fpd2'] > 0]
    
    pareto['Acumulado'] = pareto['is_fpd2'].cumsum()
    pareto['% Acumulado'] = pareto['is_fpd2'].cumsum() / pareto['is_fpd2'].sum() * 100
    pareto['Rank'] = range(1, len(pareto) + 1)
    
    corte_80 = pareto[pareto['% Acumulado'] <= 80]
    num_sucursales_80 = len(corte_80)
    total_sucursales = len(pareto)
    pct_sucursales = (num_sucursales_80 / total_sucursales * 100) if total_sucursales > 0 else 0
    
    col_p1, col_p2 = st.columns([1, 3])
    with col_p1:
        st.info(f"""
        **El Principio 80/20 en acción:**
        
        El **{pct_sucursales:.1f}%** de las sucursales con FPD ({num_sucursales_80} de {total_sucursales}) generan el **80%** de todos los casos de impago.
        """)
        st.metric(label="Total Casos FPD", value=int(pareto['is_fpd2'].sum()))
    
    with col_p2:
        fig_pareto = px.bar(pareto.head(30), x='sucursal', y='is_fpd2', title="Top 30 Sucursales con más casos (Volumen)", labels={'is_fpd2': 'Casos FPD'})
        fig_pareto.update_traces(marker_color='#d62728')
        st.plotly_chart(fig_pareto, use_container_width=True)

    st.divider()

    # 3. ANÁLISIS DE SENSIBILIDAD POR MONTO
    st.subheader("3. Sensibilidad al Riesgo por Monto Otorgado")
    st.markdown(f"Análisis de la cosecha **{ultima}**. ¿Los créditos más grandes tienen peor comportamiento?")
    
    df_monto = df[df['cosecha_x'] == ultima].copy()
    
    bins = [0, 3000, 5000, 8000, 12000, 20000, 1000000]
    labels = ['0-3k', '3k-5k', '5k-8k', '8k-12k', '12k-20k', '>20k']
    
    df_monto['rango_monto'] = pd.cut(df_monto['monto'], bins=bins, labels=labels)
    
    resumen_monto = df_monto.groupby('rango_monto')['is_fpd2'].agg(['mean', 'count']).reset_index()
    resumen_monto['FPD2 %'] = resumen_monto['mean'] * 100
    
    fig_dual = go.Figure()
    
    fig_dual.add_trace(go.Bar(
        x=resumen_monto['rango_monto'],
        y=resumen_monto['count'],
        name='Volumen Créditos',
        marker_color='#bbdefb',
        yaxis='y'
    ))
    
    fig_dual.add_trace(go.Scatter(
        x=resumen_monto['rango_monto'],
        y=resumen_monto['FPD2 %'],
        name='% FPD',
        mode='lines+markers+text',
        text=[f'{v:.1f}%' for v in resumen_monto['FPD2 %']],
        textposition='top center',
        line=dict(color='#d62728', width=3),
        yaxis='y2'
    ))
    
    fig_dual.update_layout(
        title="Volumen vs Riesgo por Rango de Monto",
        yaxis=dict(title='Cantidad de Créditos'),
        yaxis2=dict(title='% FPD', overlaying='y', side='right'),
        legend=dict(orientation="h", y=-0.1),
        hovermode="x unified"
    )
    
    st.plotly_chart(fig_dual, use_container_width=True)