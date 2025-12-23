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
        st.error(f"Faltan columnas clave.")
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
        return None

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
    
    df_clean['cosecha_x'] = df_clean['cosecha_str']
    return df_clean

# Cargar DATOS
df = load_data()

# --- 3. LÓGICA DE COSECHAS (MADURAS Y SIGUIENTE) ---
todas = sorted(df['cosecha_x'].unique())
maduras = todas[:-MESES_A_EXCLUIR] if len(todas) > MESES_A_EXCLUIR else todas

# Definición de meses clave
mes_actual = maduras[-1] if len(maduras) >= 1 else None

# Identificar la "Siguiente Cosecha" (La primera de las excluidas)
# Si todas=[202508, 202509, 202510, 202511], maduras=[202508, 202509], mes_siguiente=202510
indice_actual = todas.index(mes_actual) if mes_actual in todas else -1
mes_siguiente = todas[indice_actual + 1] if indice_actual != -1 and (indice_actual + 1) < len(todas) else None

# --- 4. FILTROS ---
st.sidebar.header("🎯 Filtros")
sel_uni = st.sidebar.multiselect("Unidad Regional:", sorted(df['unidad'].unique()))
sel_suc = st.sidebar.multiselect("Sucursal:", sorted(df['sucursal'].unique()))

df_base = df.copy()
if sel_uni: df_base = df_base[df_base['unidad'].isin(sel_uni)]
if sel_suc: df_base = df_base[df_base['sucursal'].isin(sel_suc)]

# --- 5. PESTAÑAS ---
tab1, tab2, tab3, tab4 = st.tabs(["📉 Monitor FPD", "📋 Resumen Ejecutivo", "🎯 Insights Estratégicos", "📥 Exportar"])

# ... (Tab 1, 2 y 3 se mantienen igual que en tu versión anterior) ...

# --- PESTAÑA 4: EXPORTAR ---
with tab4:
    st.header("📥 Centro de Descargas")
    
    @st.cache_data
    def convert_df(dataframe):
        return dataframe.to_csv(index=False).encode('utf-8')

    # SECCIÓN NUEVA: EXPORTAR COSECHA ESPECÍFICA
    st.subheader(f"🚀 Exportar Próxima Cosecha")
    if mes_siguiente:
        st.info(f"La siguiente cosecha detectada es: **{mes_siguiente}**. Esta cosecha aún no se considera 'madura' para el dashboard principal.")
        
        # Filtramos la base original por el mes siguiente y los filtros de la sidebar
        df_sig = df[df['cosecha_x'] == mes_siguiente].copy()
        if sel_uni: df_sig = df_sig[df_sig['unidad'].isin(sel_uni)]
        if sel_suc: df_sig = df_sig[df_sig['sucursal'].isin(sel_suc)]
        
        col_s1, col_s2 = st.columns([1, 2])
        with col_s1:
            st.metric("Créditos en esta cosecha", len(df_sig))
        
        with col_s2:
            st.download_button(
                label=f"💾 Descargar Cosecha {mes_siguiente} (CSV)",
                data=convert_df(df_sig),
                file_name=f'cosecha_proxima_{mes_siguiente}.csv',
                mime='text/csv',
                use_container_width=True
            )
    else:
        st.warning("No se detectó una cosecha posterior a la actual en el archivo cargado.")

    st.divider()

    # SECCIÓN: DESCARGAS GENERALES
    st.subheader("📊 Reportes de Análisis Actual")
    ce1, ce2 = st.columns(2)
    with ce1:
        st.write(f"**Base Filtrada (Periodo Madurez)**")
        st.download_button("💾 Descargar Base Completa (CSV)", convert_df(df_base[df_base['cosecha_x'].isin(maduras)]), f"base_madura_{mes_actual}.csv", "text/csv", use_container_width=True)

    with ce2:
        st.write(f"**Resumen por Sucursal ({mes_actual})**")
        if mes_actual:
            resumen_export = df_base[df_base['cosecha_x'] == mes_actual].groupby('sucursal')['is_fpd2'].agg(['count', 'sum', 'mean']).reset_index()
            resumen_export.columns = ['Sucursal', 'Total', 'FPD', 'Tasa %']
            resumen_export['Tasa %'] = (resumen_export['Tasa %'] * 100).round(2)
            st.download_button("📊 Descargar KPIs (CSV)", convert_df(resumen_export), f"kpi_sucursales_{mes_actual}.csv", "text/csv", use_container_width=True)

    st.divider()
    st.markdown(f"### 👀 Vista Previa Cosecha {mes_siguiente if mes_siguiente else ''}")
    if mes_siguiente:
        st.dataframe(df_sig.head(50), use_container_width=True)