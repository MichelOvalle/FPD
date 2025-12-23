import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Dashboard FPD2 Pro", layout="wide")
st.title("📊 Monitor FPD")

# Parámetros de Negocio
MESES_A_EXCLUIR = 2    
VENTANA_MESES = 24     
MIN_CREDITOS_RANKING = 5 

# --- 2. FUNCIÓN DE CARGA Y PROCESAMIENTO ---
@st.cache_data 
def load_data():
    # Intento de carga de archivo (Excel o CSV)
    archivo = 'fpd gemini.xlsx'
    if not os.path.exists(archivo):
        archivo = 'fpd gemini.csv'
        if not os.path.exists(archivo):
             st.error("⚠️ No se encontró el archivo de datos. Asegúrate de que 'fpd gemini.xlsx' o '.csv' esté en la carpeta.")
             st.stop()
    
    try:
        if archivo.endswith('.xlsx'):
            df = pd.read_excel(archivo)
        else:
            df = pd.read_csv(archivo, encoding='latin1')
    except Exception as e:
        st.error(f"Error leyendo el archivo: {e}")
        st.stop()

    # Estandarización de nombres de columnas
    df.columns = [str(c).lower().strip() for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]

    # Mapeo dinámico de columnas clave
    col_cosecha = next((c for c in df.columns if 'cosecha' in c), None)
    col_fpd2 = next((c for c in df.columns if 'fpd2' in c), None)
    if not col_fpd2: col_fpd2 = next((c for c in df.columns if 'fpd' in c), None)
    col_np = next((c for c in df.columns if 'np' == c or 'np' in c.split('_')), None) 
    col_monto = next((c for c in df.columns if 'monto' in c and 'otorgado' in c), None)
    if not col_monto: col_monto = next((c for c in df.columns if 'monto' in c), None)

    if not col_cosecha or not col_fpd2:
        st.error(f"Columnas críticas no encontradas.")
        st.stop()

    df_clean = df.copy()
    
    # Procesamiento de Fechas (Formato YYYYMM)
    df_clean['cosecha_str'] = df_clean[col_cosecha].astype(str).str.replace(r'\.0$', '', regex=True)
    df_clean['fecha_dt'] = pd.to_datetime(df_clean['cosecha_str'], format='%Y%m', errors='coerce')
    df_clean['anio'] = df_clean['fecha_dt'].dt.year.fillna(0).astype(int).astype(str)
    df_clean['mes_num'] = df_clean['fecha_dt'].dt.month.fillna(0).astype(int)
    
    mapa_meses = {1:'Ene', 2:'Feb', 3:'Mar', 4:'Abr', 5:'May', 6:'Jun', 7:'Jul', 8:'Ago', 9:'Sep', 10:'Oct', 11:'Nov', 12:'Dic', 0:'SD'}
    df_clean['mes_nombre'] = df_clean['mes_num'].map(mapa_meses)
    
    # Flags de Riesgo
    df_clean['is_fpd2'] = df_clean[col_fpd2].astype(str).apply(lambda x: 1 if 'FPD' in x.upper() else 0)
    df_clean['is_np'] = df_clean[col_np].astype(str).apply(lambda x: 1 if 'NP' in x.upper() else 0) if col_np else 0
    df_clean['monto'] = pd.to_numeric(df_clean[col_monto], errors='coerce').fillna(0) if col_monto else 0

    # Buscador de columnas de agrupación
    def find_col(dataframe, priority, fallback):
        for cand in priority:
            if cand in dataframe.columns: return cand
        pos = [c for c in dataframe.columns if fallback in c and 'id' not in c]
        return pos[0] if pos else None

    c_suc = find_col(df_clean, ['sucursal', 'nombre_sucursal'], 'sucursal')
    df_clean['sucursal'] = df_clean[c_suc].fillna('Sin Dato').astype(str) if c_suc else 'Sin Dato'

    c_uni = find_col(df_clean, ['unidad_regional', 'regional', 'region', 'unidad'], 'regional')
    df_clean['unidad'] = df_clean[c_uni].fillna('Sin Dato').astype(str) if c_uni else 'Sin Dato'

    c_prod = find_col(df_clean, ['producto_agrupado', 'nombre_producto', 'producto'], 'producto')
    df_clean['producto'] = df_clean[c_prod].fillna('Sin Dato').astype(str) if c_prod else 'Sin Dato'

    c_ori = find_col(df_clean, ['origen2', 'origen'], 'origen')
    df_clean['origen'] = df_clean[c_ori].fillna('Sin Dato').astype(str).str.title() if c_ori else 'Sin Dato'

    c_tip = find_col(df_clean, ['tipo_cliente', 'tipo'], 'cliente')
    df_clean['tipo_cliente'] = df_clean[c_tip].fillna('Sin Dato').astype(str) if c_tip else 'Sin Dato'
    
    df_clean['cosecha_x'] = df_clean['cosecha_str']
    return df_clean

df = load_data()

# --- 3. LOGICA DE TIEMPO ---
todas = sorted(df['cosecha_x'].unique())
maduras = todas[:-MESES_A_EXCLUIR] if len(todas) > MESES_A_EXCLUIR else todas
visualizar = maduras[-VENTANA_MESES:] if len(maduras) > VENTANA_MESES else maduras
mes_actual = maduras[-1] if len(maduras) >= 1 else None
mes_anterior = maduras[-2] if len(maduras) >= 2 else None

# --- 4. SIDEBAR ---
st.sidebar.header("🎯 Filtros de Negocio")
sel_uni = st.sidebar.multiselect("Unidad Regional:", sorted(df['unidad'].unique()))
sel_suc = st.sidebar.multiselect("Sucursal:", sorted(df['sucursal'].unique()))
sel_pro = st.sidebar.multiselect("Producto:", sorted(df['producto'].unique()))
sel_tip = st.sidebar.multiselect("Tipo Cliente:", sorted(df['tipo_cliente'].unique()))

df_base = df.copy()
if sel_uni: df_base = df_base[df_base['unidad'].isin(sel_uni)]
if sel_suc: df_base = df_base[df_base['sucursal'].isin(sel_suc)]
if sel_pro: df_base = df_base[df_base['producto'].isin(sel_pro)]
if sel_tip: df_base = df_base[df_base['tipo_cliente'].isin(sel_tip)]

# --- 5. CÁLCULO DE RANKING (PESTAÑA 1) ---
worst_10_sucursales = []
df_ranking_calc = pd.DataFrame()
if mes_actual and not df_base.empty:
    df_ranking_base = df_base[df_base['cosecha_x'] == mes_actual].copy()
    mask_999 = df_ranking_base['sucursal'].astype(str).str.contains("999", na=False)
    mask_nom = df_ranking_base['sucursal'].astype(str).str.lower().str.contains("nomina", na=False)
    df_ranking_calc = df_ranking_base[~(mask_999 | mask_nom)]
    
    r_calc = df_ranking_calc.groupby('sucursal')['is_fpd2'].agg(['count', 'sum', 'mean']).reset_index()
    r_clean_calc = r_calc[r_calc['count'] >= MIN_CREDITOS_RANKING]
    if not r_clean_calc.empty:
        worst_10_sucursales = r_clean_calc.sort_values('mean', ascending=False).head(10)['sucursal'].tolist()

# =========================================================
# --- PESTAÑAS ---
# =========================================================
tab1, tab2, tab3, tab4 = st.tabs(["📉 Monitor FPD", "📋 Resumen Ejecutivo", "🎯 Insights Estratégicos", "💾 Exportar"])

# --- TAB 1: MONITOR ---
with tab1:
    if df_base.empty:
        st.warning("Sin datos.")
    else:
        st.markdown("### Resumen Operativo")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("1. Tendencia Global")
            d = df_base[df_base['cosecha_x'].isin(visualizar)].groupby('cosecha_x')['is_fpd2'].mean().reset_index()
            fig = px.line(d, x='cosecha_x', y='is_fpd2', markers=True, text=(d['is_fpd2']*100).map('{:.1f}%'.format))
            fig.update_traces(line_color='#FF4B4B', textposition="top center")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.subheader("2. Físico vs Digital")
            d = df_base[df_base['cosecha_x'].isin(visualizar)].groupby(['cosecha_x', 'origen'])['is_fpd2'].mean().reset_index()
            fig = px.line(d, x='cosecha_x', y='is_fpd2', color='origen', markers=True)
            st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.subheader(f"3. Ranking Sucursales ({mes_actual})")
        if not df_ranking_calc.empty and not r_clean_calc.empty:
            r_clean_calc['FPD2 %'] = r_clean_calc['mean'] * 100
            col_a, col_b = st.columns(2)
            config = {"FPD2 %": st.column_config.NumberColumn(format="%.2f%%")}
            col_a.dataframe(r_clean_calc.sort_values('mean', ascending=False).head(10)[['sucursal', 'FPD2 %']], hide_index=True, use_container_width=True, column_config=config)
            col_b.dataframe(r_clean_calc.sort_values('mean', ascending=True).head(10)[['sucursal', 'FPD2 %']], hide_index=True, use_container_width=True, column_config=config)

# --- TAB 2: RESUMEN EJECUTIVO ---
with tab2:
    st.header("📋 Análisis Ejecutivo")
    if mes_actual:
        df_m = df[df['cosecha_x'] == mes_actual].copy()
        res_u = df_m.groupby('unidad')['is_fpd2'].mean().reset_index()
        if not res_u.empty:
            m, p = res_u.loc[res_u['is_fpd2'].idxmin()], res_u.loc[res_u['is_fpd2'].idxmax()]
            k1, k2 = st.columns(2)
            k1.metric("🟢 Mejor Región", m['unidad'], f"{m['is_fpd2']*100:.2f}%", delta_color="inverse")
            k2.metric("🔴 Mayor Riesgo", p['unidad'], f"{p['is_fpd2']*100:.2f}%", delta_color="inverse")

        st.divider()
        st.subheader("4. Detalle de Riesgo por Producto y Sucursal (Bottom 10)")
        if worst_10_sucursales:
            df_det = df_base[(df_base['cosecha_x'] == mes_actual) & (df_base['sucursal'].isin(worst_10_sucursales))]
            pivot = df_det.groupby(['sucursal', 'producto']).agg(Casos=('is_fpd2', 'sum'), Total=('is_fpd2', 'count'), Tasa=('is_fpd2', 'mean')).reset_index()
            pivot['Tasa'] = (pivot['Tasa']*100).map('{:.1f}%'.format)
            st.dataframe(pivot.pivot(index='sucursal', columns='producto', values=['Casos', 'Tasa']), use_container_width=True)

# --- TAB 3: STRATEGIC INSIGHTS ---
with tab3:
    st.header("🎯 Análisis de Patrones")
    if len(maduras) >= 6:
        st.subheader("1. Heatmap Regional")
        h = df[df['cosecha_x'].isin(maduras[-6:])].groupby(['unidad', 'cosecha_x'])['is_fpd2'].mean().unstack() * 100
        fig_h = px.imshow(h, text_auto='.1f', color_continuous_scale='RdYlGn_r')
        st.plotly_chart(fig_h, use_container_width=True)

# --- TAB 4: EXPORTAR ---
with tab4:
    st.info("Pestaña lista para funciones de exportación.")