import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

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

    # Estandarizar nombres a minúsculas para facilitar el filtrado y selección
    df.columns = [str(c).lower().strip() for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]

    # Buscador inteligente de columnas para lógica interna
    col_cosecha = next((c for c in df.columns if 'cosecha' in c), None)
    col_fpd2 = next((c for c in df.columns if 'fpd2' in c), None)
    if not col_fpd2: col_fpd2 = next((c for c in df.columns if 'fpd' in c), None)
    col_np = next((c for c in df.columns if 'np' == c or 'np' in c.split('_')), None) 
    col_monto = next((c for c in df.columns if 'monto' in c and 'otorgado' in c), None)

    if not col_cosecha or not col_fpd2:
        st.error("Faltan columnas clave (Cosecha o FPD).")
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
    
    # Bandera binaria para lógica de cálculo
    df_clean['is_fpd2'] = df_clean[col_fpd2].astype(str).apply(lambda x: 1 if 'FPD' in x.upper() else 0)
    
    if col_monto: df_clean['monto'] = pd.to_numeric(df_clean[col_monto], errors='coerce').fillna(0)
    else: df_clean['monto'] = 0

    # Mapeo de columnas para consistencia en filtros
    def find_col(candidates, fallback):
        for cand in candidates:
            if cand in df_clean.columns: return cand
        return fallback

    df_clean['sucursal'] = df_clean[find_col(['sucursal', 'nombre_sucursal'], col_cosecha)].astype(str) # Fallback seguro
    df_clean['unidad'] = df_clean[find_col(['unidad_regional', 'regional', 'region', 'unidad'], col_cosecha)].astype(str)
    df_clean['producto'] = df_clean[find_col(['producto_agrupado', 'nombre_producto', 'producto'], col_cosecha)].astype(str)
    df_clean['cosecha_x'] = df_clean['cosecha_str']
    
    return df_clean

# Cargar DATOS
df = load_data()

# --- 3. LÓGICA DE TIEMPO ---
todas = sorted(df['cosecha_x'].unique())
maduras = todas[:-MESES_A_EXCLUIR] if len(todas) > MESES_A_EXCLUIR else todas
mes_actual = maduras[-1] if len(maduras) >= 1 else None

# Identificar Cosecha Siguiente (ej. Octubre 2025)
idx = todas.index(mes_actual) if mes_actual in todas else -1
mes_siguiente = todas[idx + 1] if idx != -1 and (idx + 1) < len(todas) else None

# --- 4. FILTROS ---
st.sidebar.header("🎯 Filtros")
sel_uni = st.sidebar.multiselect("Unidad Regional:", sorted(df['unidad'].unique()))
sel_suc = st.sidebar.multiselect("Sucursal:", sorted(df['sucursal'].unique()))

# --- 5. PESTAÑAS ---
tab1, tab2, tab3, tab4 = st.tabs(["📉 Monitor FPD", "📋 Resumen Ejecutivo", "🎯 Insights Estratégicos", "📥 Exportar"])

# (Las Tabs 1, 2 y 3 mantienen su lógica visual previa)

# --- PESTAÑA 4: EXPORTAR ---
with tab4:
    st.header("📥 Centro de Descargas")
    
    @st.cache_data
    def convert_df(dataframe):
        return dataframe.to_csv(index=False).encode('utf-8')

    st.subheader(f"🚀 Exportar Próxima Cosecha ({mes_siguiente})")
    
    if mes_siguiente:
        # 1. Filtrar por el mes solicitado
        df_sig = df[df['cosecha_x'] == mes_siguiente].copy()
        
        # 2. Aplicar filtros de negocio de la barra lateral
        if sel_uni: df_sig = df_sig[df_sig['unidad'].isin(sel_uni)]
        if sel_suc: df_sig = df_sig[df_sig['sucursal'].isin(sel_suc)]
        
        # 3. FILTRO CRÍTICO: Solo casos FPD (fpd2 = 1)
        df_sig_export = df_sig[df_sig['is_fpd2'] == 1].copy()
        
        # 4. SELECCIÓN DE COLUMNAS ESPECÍFICAS
        # Intentamos obtener los nombres reales de las columnas (por si varían ligeramente)
        cols_finales = ['id_credito', 'id_producto', 'producto_agrupado', 'origen2', 'cosecha', 'sucursal', 'fpd2']
        
        # Filtramos solo las que existan en el DataFrame para evitar errores
        available_cols = [c for c in cols_finales if c in df_sig_export.columns]
        df_final = df_sig_export[available_cols]

        if not df_final.empty:
            st.success(f"Se encontraron **{len(df_final)}** casos FPD para la cosecha {mes_siguiente}.")
            
            st.download_button(
                label=f"💾 Descargar Casos FPD {mes_siguiente} (CSV)",
                data=convert_df(df_final),
                file_name=f'detalle_fpd_proxima_{mes_siguiente}.csv',
                mime='text/csv',
                use_container_width=True
            )
            
            st.info("Columnas incluidas: " + ", ".join(available_cols))
            
            st.divider()
            st.markdown("### 👀 Vista Previa de la Exportación")
            st.dataframe(df_final.head(50), use_container_width=True)
        else:
            st.warning(f"No hay casos con FPD2=1 en la cosecha {mes_siguiente} con los filtros seleccionados.")
    else:
        st.error("No se detectó una cosecha posterior para exportar.")

    st.divider()
    st.subheader("📊 Otros Reportes")
    if mes_actual:
        st.write(f"Base General Madura ({mes_actual})")
        df_madura = df[df['cosecha_x'] == mes_actual]
        st.download_button("💾 Descargar Base Madura Completa", convert_df(df_madura), f"base_madura_{mes_actual}.csv", use_container_width=True)