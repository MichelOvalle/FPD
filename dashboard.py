import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import io

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Dashboard FPD2 Pro", layout="wide")
st.title("📊 Monitor FPD")

# Configuraciones constantes
MESES_A_EXCLUIR = 2    
VENTANA_MESES = 24     
MIN_CREDITOS_RANKING = 5 

# --- 2. FUNCIÓN DE CARGA ---
@st.cache_data 
def load_data():
    archivo = 'fpd gemini.xlsx'
    if not os.path.exists(archivo):
        archivo = 'fpd gemini.csv'
        if not os.path.exists(archivo):
             st.error("⚠️ No se encontró 'fpd gemini.xlsx' ni 'fpd gemini.csv'.")
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

    # Buscador inteligente de columnas
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

# --- 3. CONFIGURACIÓN DE VENTANA DE TIEMPO ---
todas = sorted(df['cosecha_x'].unique())
maduras = todas[:-MESES_A_EXCLUIR] if len(todas) > MESES_A_EXCLUIR else todas
visualizar = maduras[-VENTANA_MESES:] if len(maduras) > VENTANA_MESES else maduras

sel_cosecha = visualizar
mes_actual = maduras[-1] if len(maduras) >= 1 else None
mes_anterior = maduras[-2] if len(maduras) >= 2 else None

# --- 4. FILTROS DE BARRA LATERAL ---
st.sidebar.header("🎯 Filtros Generales")
st.sidebar.divider()
sel_uni = st.sidebar.multiselect("1. Unidad Regional:", sorted(df['unidad'].unique()))
sel_suc = st.sidebar.multiselect("2. Sucursal:", sorted(df['sucursal'].unique()))
sel_pro = st.sidebar.multiselect("3. Producto Agrupado:", sorted(df['producto'].unique()))
sel_tip = st.sidebar.multiselect("4. Tipo de Cliente:", sorted(df['tipo_cliente'].unique()))

# --- 5. PREPARACIÓN BASE FILTRADA ---
df_base = df.copy()
if sel_uni: df_base = df_base[df_base['unidad'].isin(sel_uni)]
if sel_suc: df_base = df_base[df_base['sucursal'].isin(sel_suc)]
if sel_pro: df_base = df_base[df_base['producto'].isin(sel_pro)]
if sel_tip: df_base = df_base[df_base['tipo_cliente'].isin(sel_tip)]

df_top = df_base[df_base['cosecha_x'].isin(sel_cosecha)]

# --- CÁLCULO DEL BOTTOM 10 ---
worst_10_sucursales = []
df_ranking_calc = pd.DataFrame()

if mes_actual and not df_base.empty:
    df_ranking_base = df_base[df_base['cosecha_x'] == mes_actual].copy()
    if not df_ranking_base.empty:
        mask_999 = df_ranking_base['sucursal'].astype(str).str.contains("999", na=False)
        mask_nomina = df_ranking_base['sucursal'].astype(str).str.lower().str.contains("nomina colaboradores", na=False)
        df_ranking_calc = df_ranking_base[~(mask_999 | mask_nomina)]
        r_calc = df_ranking_calc.groupby('sucursal')['is_fpd2'].agg(['count', 'sum', 'mean']).reset_index()
        r_clean_calc = r_calc[r_calc['count'] >= MIN_CREDITOS_RANKING]
        if not r_clean_calc.empty:
            bottom_10_df = r_clean_calc.sort_values('mean', ascending=False).head(10)
            worst_10_sucursales = bottom_10_df['sucursal'].tolist()

# --- 6. PESTAÑAS ---
tab1, tab2, tab3, tab4 = st.tabs(["📉 Monitor FPD", "📋 Resumen Ejecutivo", "🎯 Insights Estratégicos", "📥 Exportar"])

# --- PESTAÑA 1: MONITOR ---
with tab1:
    if df_base.empty:
        st.warning("No hay datos para mostrar con los filtros actuales.")
    else:
        st.markdown("### Resumen Operativo")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("1. Tendencia Global")
            d = df_top.groupby('cosecha_x')['is_fpd2'].mean().reset_index()
            d['FPD2 %'] = d['is_fpd2']*100
            fig = px.line(d, x='cosecha_x', y='FPD2 %', markers=True, text=d['FPD2 %'].apply(lambda x: f'{x:.1f}%'))
            fig.update_traces(line_color='#FF4B4B', textposition="top center")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.subheader("2. Físico vs Digital")
            mask = df_top['origen'].str.contains('Fisico|Digital', case=False, na=False)
            d_comp = df_top[mask].copy()
            if not d_comp.empty:
                d = d_comp.groupby(['cosecha_x', 'origen'])['is_fpd2'].mean().reset_index()
                d['FPD2 %'] = d['is_fpd2']*100
                fig = px.line(d, x='cosecha_x', y='FPD2 %', color='origen', markers=True)
                st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.subheader(f"3. Ranking de Sucursales (Cosecha {mes_actual})")
        if not df_ranking_calc.empty and not r_clean_calc.empty:
            rx1, rx2 = st.columns(2)
            r_clean_calc['FPD2 %'] = r_clean_calc['mean'] * 100
            column_config = {"FPD2 %": st.column_config.NumberColumn(format="%.2f%%")}
            rx1.dataframe(r_clean_calc.sort_values('mean', ascending=False).head(10)[['sucursal', 'FPD2 %']], hide_index=True, use_container_width=True, column_config=column_config)
            rx2.dataframe(r_clean_calc.sort_values('mean', ascending=True).head(10)[['sucursal', 'FPD2 %']], hide_index=True, use_container_width=True, column_config=column_config)

# --- PESTAÑA 2: RESUMEN EJECUTIVO (GLOBAL) ---
with tab2:
    st.header("📋 Resumen Ejecutivo Global")
    if len(maduras) < 2: st.error("Insuficiente historia.")
    else:
        st.markdown(f"#### 🌍 Análisis Regional ({mes_actual})")
        df_resumen = df[df['cosecha_x'] == mes_actual]
        res_uni = df_resumen[~df_resumen['unidad'].str.lower().str.contains("nomina")].groupby('unidad')['is_fpd2'].mean().reset_index()
        if not res_uni.empty:
            mejor, peor = res_uni.loc[res_uni['is_fpd2'].idxmin()], res_uni.loc[res_uni['is_fpd2'].idxmax()]
            cr1, cr2 = st.columns(2)
            cr1.success(f"**Mejor Región:** {mejor['unidad']} ({mejor['is_fpd2']*100:.2f}%)")
            cr2.error(f"**Mayor Riesgo:** {peor['unidad']} ({peor['is_fpd2']*100:.2f}%)")

# --- PESTAÑA 3: INSIGHTS ---
with tab3:
    st.header("🎯 Insights Estratégicos")
    if len(maduras) >= 6:
        st.subheader("1. Mapa de Calor (Últimos 6 meses)")
        df_heat = df[df['cosecha_x'].isin(maduras[-6:])].groupby(['unidad', 'cosecha_x'])['is_fpd2'].mean().reset_index()
        df_heat['FPD2 %'] = df_heat['is_fpd2'] * 100
        fig_heat = px.imshow(df_heat.pivot(index='unidad', columns='cosecha_x', values='FPD2 %'), text_auto='.1f', color_continuous_scale='RdYlGn_r')
        st.plotly_chart(fig_heat, use_container_width=True)

# --- PESTAÑA 4: EXPORTAR ---
with tab4:
    st.header("📥 Centro de Descargas")
    st.markdown("Genera reportes en formato CSV basados en los filtros actuales.")

    @st.cache_data
    def convert_df(dataframe):
        return dataframe.to_csv(index=False).encode('utf-8')

    ce1, ce2 = st.columns(2)
    with ce1:
        st.subheader("1. Datos Filtrados")
        st.write(f"Registros: `{len(df_base):,}`")
        st.download_button("💾 Descargar Base Filtrada (CSV)", convert_df(df_base), f"base_fpd_{mes_actual}.csv", "text/csv", use_container_width=True)

    with ce2:
        st.subheader("2. Reporte de Sucursales")
        if not df_ranking_calc.empty:
            resumen_export = df_ranking_calc.groupby('sucursal')['is_fpd2'].agg(['count', 'sum', 'mean']).reset_index()
            resumen_export.columns = ['Sucursal', 'Créditos Totales', 'Casos FPD', 'Tasa %']
            resumen_export['Tasa %'] = (resumen_export['Tasa %'] * 100).round(2)
            st.download_button("📊 Descargar KPIs Sucursales (CSV)", convert_df(resumen_export), f"kpi_sucursales_{mes_actual}.csv", "text/csv", use_container_width=True)

    st.divider()
    st.markdown("### 👀 Vista Previa (Top 50)")
    st.dataframe(df_base.head(50), use_container_width=True)