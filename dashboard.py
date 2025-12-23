import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Dashboard FPD2 Pro", layout="wide")
st.title("📊 Monitor FPD")

# Constantes de Negocio
MESES_A_EXCLUIR = 2    
VENTANA_MESES = 24     
MIN_CREDITOS_RANKING = 5 

# --- 2. FUNCIÓN DE CARGA ROBUSTA (Corregida para errores de Excel) ---
@st.cache_data 
def load_data():
    # Buscador de archivos (insensible a mayúsculas/minúsculas para Linux/Cloud)
    archivos_locales = os.listdir('.')
    archivo_objetivo = 'fpd gemini.xlsx'
    
    for f in archivos_locales:
        if f.lower() == 'fpd gemini.xlsx':
            archivo_objetivo = f
            break
        elif f.lower() == 'fpd gemini.csv':
            archivo_objetivo = f
            break

    if not os.path.exists(archivo_objetivo):
        st.error(f"⚠️ No se encontró el archivo. Archivos en servidor: {archivos_locales}")
        st.stop()
    
    try:
        if archivo_objetivo.endswith('.xlsx'):
            # Se agrega engine='openpyxl' para evitar el ValueError detectado
            df = pd.read_excel(archivo_objetivo, engine='openpyxl')
        else:
            df = pd.read_csv(archivo_objetivo, encoding='latin1')
    except Exception as e:
        st.error(f"❌ Error al leer el archivo: {e}")
        st.stop()

    df.columns = [str(c).lower().strip() for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]

    # Función de búsqueda de columnas (Recuperada del código base)
    def find_best_column(dataframe, candidates_priority, fallback_search_term):
        for cand in candidates_priority:
            if cand in dataframe.columns: return cand
        possible = [c for c in dataframe.columns if fallback_search_term in c and 'id' not in c]
        return possible[0] if possible else None

    # Mapeo de columnas clave
    col_cosecha = next((c for c in df.columns if 'cosecha' in c), None)
    col_fpd2 = next((c for c in df.columns if 'fpd2' in c or 'fpd' in c), None)
    col_np = next((c for c in df.columns if 'np' == c or 'np' in c.split('_')), None)
    col_monto = find_best_column(df, ['monto_otorgado', 'monto'], 'monto')

    df_clean = df.copy()
    
    # Procesamiento de Fechas
    df_clean['cosecha_str'] = df_clean[col_cosecha].astype(str).str.replace(r'\.0$', '', regex=True)
    df_clean['fecha_dt'] = pd.to_datetime(df_clean['cosecha_str'], format='%Y%m', errors='coerce')
    df_clean['anio'] = df_clean['fecha_dt'].dt.year.fillna(0).astype(int).astype(str)
    df_clean['mes_num'] = df_clean['fecha_dt'].dt.month.fillna(0).astype(int)
    
    mapa_meses = {1:'Ene', 2:'Feb', 3:'Mar', 4:'Abr', 5:'May', 6:'Jun', 7:'Jul', 8:'Ago', 9:'Sep', 10:'Oct', 11:'Nov', 12:'Dic', 0:'SD'}
    df_clean['mes_nombre'] = df_clean['mes_num'].map(mapa_meses)
    
    # Lógica de FPD y NP
    df_clean['is_fpd2'] = df_clean[col_fpd2].astype(str).apply(lambda x: 1 if 'FPD' in x.upper() or '1' in x else 0)
    df_clean['is_np'] = df_clean[col_np].astype(str).apply(lambda x: 1 if 'NP' in x.upper() else 0) if col_np else 0
    df_clean['monto'] = pd.to_numeric(df_clean[col_monto], errors='coerce').fillna(0)

    # Dimensiones normalizadas para filtros
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
    
    # Columnas para Exportación (TAB 4)
    df_clean['id_credito'] = df_clean[next((c for c in df.columns if 'id_credito' in c), df.columns[0])]
    df_clean['id_producto'] = df_clean[next((c for c in df.columns if 'id_producto' in c), df.columns[0])]
    df_clean['producto_agrupado'] = df_clean['producto']
    df_clean['origen2'] = df_clean['origen']
    df_clean['cosecha'] = df_clean['cosecha_str']
    df_clean['fpd2'] = df_clean[col_fpd2]
    df_clean['cosecha_x'] = df_clean['cosecha_str']
    
    return df_clean

# Cargar DATOS
df = load_data()

# --- 3. LÓGICA TEMPORAL ---
todas = sorted(df['cosecha_x'].unique())
maduras = todas[:-MESES_A_EXCLUIR] if len(todas) > MESES_A_EXCLUIR else todas
visualizar = maduras[-VENTANA_MESES:] if len(maduras) > VENTANA_MESES else maduras
mes_actual = maduras[-1] if maduras else None
mes_anterior = maduras[-2] if len(maduras) >= 2 else None

# Identificar cosecha siguiente (Ej: Octubre 2025)
idx_actual = todas.index(mes_actual) if mes_actual in todas else -1
mes_siguiente = todas[idx_actual + 1] if idx_actual != -1 and (idx_actual + 1) < len(todas) else None

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

# --- CÁLCULO BOTTOM 10 ---
worst_10_sucursales = []
if mes_actual and not df_base.empty:
    df_r = df_base[df_base['cosecha_x'] == mes_actual]
    r_calc = df_r[~df_r['sucursal'].str.contains("999|nomina", case=False)].groupby('sucursal')['is_fpd2'].agg(['count', 'mean']).reset_index()
    r_calc = r_calc[r_calc['count'] >= MIN_CREDITOS_RANKING]
    worst_10_sucursales = r_calc.sort_values('mean', ascending=False).head(10)['sucursal'].tolist()

# --- 5. PESTAÑAS ---
tab1, tab2, tab3, tab4 = st.tabs(["📉 Monitor FPD", "📋 Resumen Ejecutivo", "🎯 Insights", "📥 Exportar"])

# --- TAB 1: MONITOR ---
with tab1:
    st.markdown(f"### Tendencia Global ({visualizar[0]} - {visualizar[-1]})")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. Evolución % FPD2")
        d_trend = df_base[df_base['cosecha_x'].isin(visualizar)].groupby('cosecha_x')['is_fpd2'].mean().reset_index()
        fig = px.line(d_trend, x='cosecha_x', y='is_fpd2', markers=True, text=(d_trend['is_fpd2']*100).map("{:.1f}%".format))
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.subheader("2. Físico vs Digital")
        d_fd = df_base[df_base['cosecha_x'].isin(visualizar)].groupby(['cosecha_x', 'origen'])['is_fpd2'].mean().reset_index()
        fig_fd = px.line(d_fd, x='cosecha_x', y='is_fpd2', color='origen', markers=True)
        st.plotly_chart(fig_fd, use_container_width=True)
    
    st.divider()
    st.subheader(f"3. Rankings de Sucursales ({mes_actual})")
    c1, c2 = st.columns(2)
    config = {"FPD2 %": st.column_config.NumberColumn(format="%.2f%%")}
    if not r_calc.empty:
        r_calc['FPD2 %'] = r_calc['mean'] * 100
        c1.write("**Top 10 Peores Tasas**")
        c1.dataframe(r_calc.sort_values('mean', ascending=False).head(10)[['sucursal', 'FPD2 %']], hide_index=True, column_config=config, use_container_width=True)
        c2.write("**Top 10 Mejores Tasas**")
        c2.dataframe(r_calc.sort_values('mean', ascending=True).head(10)[['sucursal', 'FPD2 %']], hide_index=True, column_config=config, use_container_width=True)

# --- TAB 2: RESUMEN EJECUTIVO (MATRIZ Y DETALLES) ---
with tab2:
    st.header("📋 Resumen Ejecutivo Global")
    df_exec = df[df['cosecha_x'] == mes_actual]
    
    # Análisis Regional Cards
    st.markdown(f"#### Análisis Regional ({mes_actual})")
    res_uni = df_exec.groupby('unidad')['is_fpd2'].mean().reset_index()
    if not res_uni.empty:
        mj, pr = res_uni.loc[res_uni['is_fpd2'].idxmin()], res_uni.loc[res_uni['is_fpd2'].idxmax()]
        colr1, colr2 = st.columns(2)
        colr1.success(f"🟢 **Mejor Región:** {mj['unidad']} ({mj['is_fpd2']*100:.2f}%)")
        colr2.error(f"🔴 **Mayor Riesgo:** {pr['unidad']} ({pr['is_fpd2']*100:.2f}%)")

    st.divider()
    # Matriz Bottom 10 (Recuperada con formato CSS)
    st.subheader("Detalle Riesgo por Producto/Sucursal (Bottom 10)")
    if worst_10_sucursales:
        df_matriz = df_base[(df_base['cosecha_x'] == mes_actual) & (df_base['sucursal'].isin(worst_10_sucursales))]
        pivot_m = df_matriz.groupby(['sucursal', 'producto']).agg(
            FPD_Casos=('is_fpd2', 'sum'),
            Total=('is_fpd2', 'count'),
            Tasa=('is_fpd2', 'mean')
        ).reset_index()
        pivot_m['Tasa'] = (pivot_m['Tasa'] * 100).map("{:.1f}%".format)
        
        # Formatear la tabla para que se vea: (FPD | Total | %)
        pivot_m['Detalle'] = pivot_m.apply(lambda r: f"{int(r['FPD_Casos'])} | {int(r['Total'])} | {r['Tasa']}", axis=1)
        final_table = pivot_m.pivot(index='sucursal', columns='producto', values='Detalle').fillna("-")
        
        st.dataframe(final_table.style.set_table_styles([
            {'selector': 'th', 'props': [('background-color', '#e0f7fa'), ('color', 'black'), ('font-weight', 'bold')]},
            {'selector': 'tbody th', 'props': [('font-weight', 'bold'), ('color', 'black')]}
        ]), use_container_width=True)

# --- TAB 3: INSIGHTS (HEATMAP Y PARETO) ---
with tab3:
    st.header("🎯 Insights Estratégicos")
    col_i1, col_i2 = st.columns(2)
    with col_i1:
        st.subheader("1. Mapa de Riesgo Regional (6m)")
        dh = df[df['cosecha_x'].isin(maduras[-6:])].pivot_table(index='unidad', columns='cosecha_x', values='is_fpd2', aggfunc='mean')
        st.plotly_chart(px.imshow(dh, text_auto=".1%", color_continuous_scale='RdYlGn_r'), use_container_width=True)
    with col_i2:
        st.subheader("2. Concentración Pareto")
        dp = df_exec.groupby('sucursal')['is_fpd2'].sum().sort_values(ascending=False).reset_index()
        st.plotly_chart(px.bar(dp.head(20), x='sucursal', y='is_fpd2', title="Sucursales con más casos (Volumen)"), use_container_width=True)

# --- TAB 4: EXPORTAR (TU REQUERIMIENTO FINAL) ---
with tab4:
    st.header("📥 Exportar Próxima Cosecha")
    if mes_siguiente:
        st.info(f"Cosecha detectada para exportar: **{mes_siguiente}** (Ej: Octubre 2025)")
        
        df_exp = df[df['cosecha_x'] == mes_siguiente].copy()
        if sel_uni: df_exp = df_exp[df_exp['unidad'].isin(sel_uni)]
        if sel_suc: df_exp = df_exp[df_exp['sucursal'].isin(sel_suc)]
        
        # Filtros solicitados: fpd2=1
        df_final_exp = df_exp[df_exp['is_fpd2'] == 1]
        
        # Selección de las 7 columnas exactas
        cols_final = ['id_credito', 'id_producto', 'producto_agrupado', 'origen2', 'cosecha', 'sucursal', 'fpd2']
        available_cols = [c for c in cols_final if c in df_final_exp.columns]
        df_to_download = df_final_exp[available_cols]

        st.success(f"Casos encontrados con FPD2=1: **{len(df_to_download)}**")
        
        @st.cache_data
        def to_csv(dataframe): return dataframe.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label=f"💾 Descargar Casos FPD {mes_siguiente}",
            data=to_csv(df_to_download),
            file_name=f"DETALLE_FPD_{mes_siguiente}.csv",
            mime="text/csv",
            use_container_width=True
        )
        st.dataframe(df_to_download, use_container_width=True, hide_index=True)
    else:
        st.warning("No hay cosecha posterior para procesar.")