import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import io

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Dashboard FPD2 Pro", layout="wide")
st.title("📊 Monitor FPD")

MESES_A_EXCLUIR = 2    
VENTANA_MESES = 24     
MIN_CREDITOS_RANKING = 5 

# --- 2. FUNCIÓN DE CARGA ROBUSTA (RECUPERADA) ---
@st.cache_data 
def load_data():
    archivo = 'fpd gemini.xlsx'
    if not os.path.exists(archivo):
        archivo = 'fpd gemini.csv'
        if not os.path.exists(archivo):
             st.error("⚠️ No se encontró el archivo de datos.")
             st.stop()
    
    try:
        df = pd.read_excel(archivo) if archivo.endswith('.xlsx') else pd.read_csv(archivo, encoding='latin1')
    except Exception as e:
        st.error(f"Error: {e}"); st.stop()

    df.columns = [str(c).lower().strip() for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]

    # Buscador inteligente de columnas (Lógica original)
    def find_best_column(dataframe, candidates_priority, fallback_search_term):
        for cand in candidates_priority:
            if cand in dataframe.columns: return cand
        possible = [c for c in dataframe.columns if fallback_search_term in c and 'id' not in c]
        return possible[0] if possible else None

    col_cosecha = next((c for c in df.columns if 'cosecha' in c), None)
    col_fpd2 = next((c for c in df.columns if 'fpd2' in c or 'fpd' in c), None)
    col_np = next((c for c in df.columns if 'np' == c or 'np' in c.split('_')), None)
    col_monto = next((c for c in df.columns if 'monto' in c and 'otorgado' in c), None) or next((c for c in df.columns if 'monto' in c), None)

    df_clean = df.copy()
    df_clean['cosecha_str'] = df_clean[col_cosecha].astype(str).str.replace(r'\.0$', '', regex=True)
    df_clean['fecha_dt'] = pd.to_datetime(df_clean['cosecha_str'], format='%Y%m', errors='coerce')
    df_clean['anio'] = df_clean['fecha_dt'].dt.year.fillna(0).astype(int).astype(str)
    df_clean['mes_num'] = df_clean['fecha_dt'].dt.month.fillna(0).astype(int)
    
    mapa_meses = {1:'Ene', 2:'Feb', 3:'Mar', 4:'Abr', 5:'May', 6:'Jun', 7:'Jul', 8:'Ago', 9:'Sep', 10:'Oct', 11:'Nov', 12:'Dic', 0:'SD'}
    df_clean['mes_nombre'] = df_clean['mes_num'].map(mapa_meses)
    
    df_clean['is_fpd2'] = df_clean[col_fpd2].astype(str).apply(lambda x: 1 if 'FPD' in x.upper() or '1' in x else 0)
    df_clean['is_np'] = df_clean[col_np].astype(str).apply(lambda x: 1 if 'NP' in x.upper() else 0) if col_np else 0
    df_clean['monto'] = pd.to_numeric(df_clean[col_monto], errors='coerce').fillna(0) if col_monto else 0

    # Dimensiones recuperadas
    c_suc = find_best_column(df_clean, ['sucursal', 'nombre_sucursal'], 'sucursal')
    df_clean['sucursal'] = df_clean[c_suc].fillna('Sin Dato').astype(str) if c_suc else 'Sin Dato'
    c_uni = find_best_column(df_clean, ['unidad_regional', 'regional', 'region', 'unidad'], 'regional')
    df_clean['unidad'] = df_clean[c_uni].fillna('Sin Dato').astype(str) if c_uni else 'Sin Dato'
    c_prod = find_best_column(df_clean, ['producto_agrupado', 'nombre_producto', 'producto'], 'producto')
    df_clean['producto'] = df_clean[c_prod].fillna('Sin Dato').astype(str) if c_prod else 'Sin Dato'
    c_ori = find_best_column(df_clean, ['origen2', 'origen'], 'origen')
    df_clean['origen'] = df_clean[c_ori].fillna('Sin Dato').astype(str).str.title() if c_ori else 'Sin Dato'
    c_tip = find_best_column(df_clean, ['tipo_cliente', 'tipo'], 'cliente')
    df_clean['tipo_cliente'] = df_clean[c_tip].fillna('Sin Dato').astype(str) if c_tip else 'Sin Dato'
    
    # Preservar nombres exactos para TAB 4
    df_clean['id_credito'] = df_clean[next((c for c in df.columns if 'id_credito' in c), df.columns[0])]
    df_clean['id_producto'] = df_clean[next((c for c in df.columns if 'id_producto' in c), df.columns[0])]
    df_clean['producto_agrupado'] = df_clean[c_prod]
    df_clean['origen2'] = df_clean[c_ori]
    df_clean['cosecha'] = df_clean[col_cosecha]
    df_clean['fpd2'] = df_clean[col_fpd2]
    df_clean['cosecha_x'] = df_clean['cosecha_str']
    
    return df_clean

df = load_data()

# --- 3. TIEMPOS (RECUPERADOS) ---
todas = sorted(df['cosecha_x'].unique())
maduras = todas[:-MESES_A_EXCLUIR] if len(todas) > MESES_A_EXCLUIR else todas
visualizar = maduras[-VENTANA_MESES:] if len(maduras) > VENTANA_MESES else maduras
mes_actual = maduras[-1] if maduras else None
mes_anterior = maduras[-2] if len(maduras) >= 2 else None
idx = todas.index(mes_actual) if mes_actual in todas else -1
mes_siguiente = todas[idx + 1] if idx != -1 and (idx + 1) < len(todas) else None

# --- 4. FILTROS ---
st.sidebar.header("🎯 Filtros de Negocio")
sel_uni = st.sidebar.multiselect("1. Unidad Regional:", sorted(df['unidad'].unique()))
sel_suc = st.sidebar.multiselect("2. Sucursal:", sorted(df['sucursal'].unique()))
sel_pro = st.sidebar.multiselect("3. Producto Agrupado:", sorted(df['producto'].unique()))
sel_tip = st.sidebar.multiselect("4. Tipo de Cliente:", sorted(df['tipo_cliente'].unique()))

df_base = df.copy()
if sel_uni: df_base = df_base[df_base['unidad'].isin(sel_uni)]
if sel_suc: df_base = df_base[df_base['sucursal'].isin(sel_suc)]
if sel_pro: df_base = df_base[df_base['producto'].isin(sel_pro)]
if sel_tip: df_base = df_base[df_base['tipo_cliente'].isin(sel_tip)]

# --- CÁLCULO CENTRALIZADO BOTTOM 10 (RECUPERADO) ---
worst_10_sucursales = []
if mes_actual and not df_base.empty:
    df_r = df_base[df_base['cosecha_x'] == mes_actual]
    r_calc = df_r[~df_r['sucursal'].str.contains("999|nomina", case=False)].groupby('sucursal')['is_fpd2'].agg(['count', 'mean']).reset_index()
    r_calc = r_calc[r_calc['count'] >= MIN_CREDITOS_RANKING]
    worst_10_sucursales = r_calc.sort_values('mean', ascending=False).head(10)['sucursal'].tolist()

# --- 5. PESTAÑAS ---
tab1, tab2, tab3, tab4 = st.tabs(["📉 Monitor FPD", "📋 Resumen Ejecutivo", "🎯 Insights", "📥 Exportar"])

# --- TAB 1: MONITOR (RECONSTRUIDA AL 100%) ---
with tab1:
    if df_base.empty: st.warning("Sin datos")
    else:
        st.markdown("### Resumen Operativo")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("1. Tendencia Global")
            d_top = df_base[df_base['cosecha_x'].isin(visualizar)].groupby('cosecha_x')['is_fpd2'].mean().reset_index()
            fig = px.line(d_top, x='cosecha_x', y='is_fpd2', markers=True, text=(d_top['is_fpd2']*100).map("{:.1f}%".format))
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.subheader("2. Físico vs Digital")
            d_fd = df_base[df_base['cosecha_x'].isin(visualizar)].groupby(['cosecha_x', 'origen'])['is_fpd2'].mean().reset_index()
            fig_fd = px.line(d_fd, x='cosecha_x', y='is_fpd2', color='origen', markers=True)
            st.plotly_chart(fig_fd, use_container_width=True)
        
        st.divider()
        st.subheader(f"3. Rankings Sucursales ({mes_actual})")
        r_cols = st.columns(2)
        if not r_calc.empty:
            r_calc['FPD2 %'] = (r_calc['mean'] * 100).round(2)
            r_cols[0].dataframe(r_calc.sort_values('mean', ascending=False).head(10)[['sucursal', 'FPD2 %']], hide_index=True, use_container_width=True)
            r_cols[1].dataframe(r_calc.sort_values('mean', ascending=True).head(10)[['sucursal', 'FPD2 %']], hide_index=True, use_container_width=True)

        st.divider()
        st.subheader("4. Análisis Detallado YoY y Clientes")
        cy1, cy2 = st.columns(2)
        with cy1:
            dy = df_base[df_base['anio'].isin(['2023','2024','2025'])].groupby(['mes_num','mes_nombre','anio'])['is_fpd2'].mean().reset_index()
            fig_y = px.line(dy.sort_values('mes_num'), x='mes_nombre', y='is_fpd2', color='anio', markers=True, title="Comparativo Anual")
            st.plotly_chart(fig_y, use_container_width=True)
        with cy2:
            dt = df_base[df_base['cosecha_x'].isin(visualizar)].groupby(['cosecha_x','tipo_cliente'])['is_fpd2'].mean().reset_index()
            fig_t = px.line(dt, x='cosecha_x', y='is_fpd2', color='tipo_cliente', markers=True, title="Por Tipo de Cliente")
            st.plotly_chart(fig_t, use_container_width=True)

# --- TAB 2: EJECUTIVO (RECONSTRUIDA AL 100%) ---
with tab2:
    st.header("📋 Resumen Ejecutivo Global")
    df_global_act = df[df['cosecha_x'] == mes_actual]
    
    # 🌍 Regional Cards
    st.markdown(f"#### Análisis Regional ({mes_actual})")
    res_uni = df_global_act.groupby('unidad')['is_fpd2'].mean().reset_index()
    if not res_uni.empty:
        mj, pr = res_uni.loc[res_uni['is_fpd2'].idxmin()], res_uni.loc[res_uni['is_fpd2'].idxmax()]
        colr1, colr2 = st.columns(2)
        colr1.success(f"🟢 **Mejor Región:** {mj['unidad']} ({mj['is_fpd2']*100:.2f}%)")
        colr2.error(f"🔴 **Mayor Riesgo:** {pr['unidad']} ({pr['is_fpd2']*100:.2f}%)")

    st.divider()
    # 🏦 Deterioro Sucursales
    st.markdown(f"#### Deterioro ({mes_anterior} vs {mes_actual})")
    df_comp = df[df['cosecha_x'].isin([mes_anterior, mes_actual])].pivot_table(index='sucursal', columns='cosecha_x', values='is_fpd2', aggfunc='mean')
    if mes_anterior in df_comp.columns and mes_actual in df_comp.columns:
        df_comp['diff'] = df_comp[mes_actual] - df_comp[mes_anterior]
        peor_det = df_comp['diff'].idxmax()
        st.warning(f"⚠️ **Mayor Deterioro:** {peor_det} (Creció {df_comp.loc[peor_det, 'diff']*100:.1f} puntos)")

    st.divider()
    # 📊 Matriz Detallada (Bottom 10)
    st.markdown("#### Detalle de Riesgo Producto/Sucursal (Bottom 10)")
    if worst_10_sucursales:
        df_matriz = df_base[(df_base['cosecha_x'] == mes_actual) & (df_base['sucursal'].isin(worst_10_sucursales))]
        pivot_m = df_matriz.pivot_table(index='sucursal', columns='producto', values='is_fpd2', aggfunc='mean')
        st.dataframe(pivot_m.style.background_gradient(cmap='YlOrRd').format("{:.1%}"), use_container_width=True)

# --- TAB 3: INSIGHTS (RECUPERADO HEATMAP Y PARETO) ---
with tab3:
    st.header("🎯 Insights Estratégicos")
    col_i1, col_i2 = st.columns(2)
    with col_i1:
        st.subheader("1. Mapa de Riesgo Regional")
        dh = df[df['cosecha_x'].isin(maduras[-6:])].pivot_table(index='unidad', columns='cosecha_x', values='is_fpd2', aggfunc='mean')
        st.plotly_chart(px.imshow(dh, text_auto=".1%", color_continuous_scale='RdYlGn_r'), use_container_width=True)
    with col_i2:
        st.subheader("2. Sensibilidad por Monto")
        df['rango'] = pd.cut(df['monto'], bins=[0, 5000, 10000, 20000, 1000000], labels=['<5k','5k-10k','10k-20k','>20k'])
        rm = df[df['cosecha_x'] == mes_actual].groupby('rango')['is_fpd2'].mean().reset_index()
        st.plotly_chart(px.bar(rm, x='rango', y='is_fpd2', title="Tasa FPD por Monto"), use_container_width=True)

# --- TAB 4: EXPORTAR (TU REQUERIMIENTO FINAL) ---
with tab4:
    st.header("📥 Exportar Próxima Cosecha")
    if mes_siguiente:
        st.info(f"Preparando descarga para: **{mes_siguiente}** (Octubre 2025)")
        # Aplicamos reglas: Mes siguiente + Filtros Sidebar + FPD2=1
        df_exp = df[df['cosecha_x'] == mes_siguiente].copy()
        if sel_uni: df_exp = df_exp[df_exp['unidad'].isin(sel_uni)]
        if sel_suc: df_exp = df_exp[df_exp['sucursal'].isin(sel_suc)]
        
        # Filtro de Riesgo
        df_final_exp = df_exp[df_exp['is_fpd2'] == 1]
        
        # Columnas exactas solicitadas
        cols_final = ['id_credito', 'id_producto', 'producto_agrupado', 'origen2', 'cosecha', 'sucursal', 'fpd2']
        # Nos aseguramos que existan
        cols_output = [c for c in cols_final if c in df_final_exp.columns]
        df_csv = df_final_exp[cols_output]

        st.write(f"Casos encontrados: `{len(df_csv)}`")
        
        csv_data = df_csv.to_csv(index=False).encode('utf-8')
        st.download_button(label="💾 Descargar CSV", data=csv_data, file_name=f"FPD_DETALLE_{mes_siguiente}.csv", use_container_width=True)
        st.dataframe(df_csv, use_container_width=True)
    else:
        st.error("No hay cosecha siguiente disponible.")