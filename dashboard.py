import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Dashboard FPD2 Pro", layout="wide")
st.title("📊 Monitor FPD")

MESES_A_EXCLUIR = 2    
VENTANA_MESES = 24     
MIN_CREDITOS_RANKING = 5 

# --- 2. CARGA DE DATOS (Recupera Lógica de Búsqueda Inteligente v1.0) ---
@st.cache_data 
def load_data():
    archivos_locales = os.listdir('.')
    archivo_objetivo = 'fpd gemini.xlsx'
    for f in archivos_locales:
        if f.lower() in ['fpd gemini.xlsx', 'fpd gemini.csv']:
            archivo_objetivo = f
            break

    if not os.path.exists(archivo_objetivo):
        st.error(f"⚠️ Archivo no encontrado."); st.stop()
    
    try:
        if archivo_objetivo.endswith('.xlsx'):
            df = pd.read_excel(archivo_objetivo, engine='openpyxl')
        else:
            df = pd.read_csv(archivo_objetivo, encoding='latin1')
    except Exception as e:
        st.error(f"❌ Error al leer: {e}"); st.stop()

    df.columns = [str(c).lower().strip() for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]

    def find_col(dataframe, candidates, fallback_term):
        for cand in candidates:
            if cand in dataframe.columns: return cand
        possible = [c for c in dataframe.columns if fallback_term in c and 'id' not in c]
        return possible[0] if possible else None

    # Mapeo de Columnas Base
    col_cosecha = next((c for c in df.columns if 'cosecha' in c), None)
    col_fpd2 = next((c for c in df.columns if 'fpd2' in c or 'fpd' in c), None)
    col_np = next((c for c in df.columns if 'np' == c or 'np' in c.split('_')), None)
    col_monto = find_col(df, ['monto_otorgado', 'monto'], 'monto')

    df_clean = df.copy()
    df_clean['cosecha_str'] = df_clean[col_cosecha].astype(str).str.replace(r'\.0$', '', regex=True)
    df_clean['fecha_dt'] = pd.to_datetime(df_clean['cosecha_str'], format='%Y%m', errors='coerce')
    df_clean['anio'] = df_clean['fecha_dt'].dt.year.fillna(0).astype(int).astype(str)
    df_clean['mes_num'] = df_clean['fecha_dt'].dt.month.fillna(0).astype(int)
    
    mapa_meses = {1:'Ene', 2:'Feb', 3:'Mar', 4:'Abr', 5:'May', 6:'Jun', 7:'Jul', 8:'Ago', 9:'Sep', 10:'Oct', 11:'Nov', 12:'Dic', 0:'SD'}
    df_clean['mes_nombre'] = df_clean['mes_num'].map(mapa_meses)
    df_clean['is_fpd2'] = df_clean[col_fpd2].astype(str).apply(lambda x: 1 if 'FPD' in x.upper() or '1' in x else 0)
    df_clean['is_np'] = df_clean[col_np].astype(str).apply(lambda x: 1 if 'NP' in x.upper() else 0) if col_np else 0
    df_clean['monto'] = pd.to_numeric(df_clean[col_monto], errors='coerce').fillna(0)

    # Dimensiones para Filtros (Fuzzy Matching v1.0)
    c_suc = find_col(df_clean, ['sucursal', 'nombre_sucursal'], 'sucursal')
    df_clean['sucursal'] = df_clean[c_suc].fillna('Sin Dato').astype(str)
    c_uni = find_col(df_clean, ['unidad_regional', 'regional', 'unidad'], 'regional')
    df_clean['unidad'] = df_clean[c_uni].fillna('Sin Dato').astype(str)
    c_pro = find_col(df_clean, ['producto_agrupado', 'producto'], 'producto')
    df_clean['producto'] = df_clean[c_pro].fillna('Sin Dato').astype(str)
    c_ori = find_col(df_clean, ['origen2', 'origen'], 'origen')
    df_clean['origen'] = df_clean[c_ori].fillna('Sin Dato').astype(str).str.title()
    c_tip = find_col(df_clean, ['tipo_cliente', 'tipo'], 'cliente')
    df_clean['tipo_cliente'] = df_clean[c_tip].fillna('Sin Dato').astype(str)

    # Columnas específicas para Exportar (Tab 4)
    df_clean['id_credito'] = df_clean[next((c for c in df.columns if 'id_credito' in c), df.columns[0])]
    df_clean['id_producto'] = df_clean[next((c for c in df.columns if 'id_producto' in c), df.columns[0])]
    df_clean['producto_agrupado'] = df_clean['producto']
    df_clean['origen2'] = df_clean['origen']
    df_clean['cosecha'] = df_clean['cosecha_str']
    df_clean['fpd2'] = df_clean[col_fpd2]
    df_clean['cosecha_x'] = df_clean['cosecha_str']
    
    return df_clean

df = load_data()

# --- 3. TIEMPOS ---
todas = sorted(df['cosecha_x'].unique())
maduras = todas[:-MESES_A_EXCLUIR] if len(todas) > MESES_A_EXCLUIR else todas
visualizar = maduras[-VENTANA_MESES:] if len(maduras) > VENTANA_MESES else maduras
mes_actual = maduras[-1] if maduras else None
mes_anterior = maduras[-2] if len(maduras) >= 2 else None
idx_actual = todas.index(mes_actual) if mes_actual in todas else -1
mes_siguiente = todas[idx_actual + 1] if idx_actual != -1 and (idx_actual + 1) < len(todas) else None

# --- 4. FILTROS ---
st.sidebar.header("🎯 Filtros de Negocio")
sel_uni = st.sidebar.multiselect("1. Regional:", sorted(df['unidad'].unique()))
sel_suc = st.sidebar.multiselect("2. Sucursal:", sorted(df['sucursal'].unique()))
sel_pro = st.sidebar.multiselect("3. Producto:", sorted(df['producto'].unique()))
sel_tip = st.sidebar.multiselect("4. Tipo Cliente:", sorted(df['tipo_cliente'].unique()))

df_base = df.copy()
if sel_uni: df_base = df_base[df_base['unidad'].isin(sel_uni)]
if sel_suc: df_base = df_base[df_base['sucursal'].isin(sel_suc)]
if sel_pro: df_base = df_base[df_base['producto'].isin(sel_pro)]
if sel_tip: df_base = df_base[df_base['tipo_cliente'].isin(sel_tip)]

# --- 5. PESTAÑAS ---
tab1, tab2, tab3, tab4 = st.tabs(["📉 Monitor FPD", "📋 Resumen Ejecutivo", "🎯 Insights", "📥 Exportar"])

# --- TAB 1: MONITOR (RESTAURADA) ---
with tab1:
    st.markdown("### Resumen Operativo")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("1. Tendencia Global")
        dt = df_base[df_base['cosecha_x'].isin(visualizar)].groupby('cosecha_x')['is_fpd2'].mean().reset_index()
        fig1 = px.line(dt, x='cosecha_x', y='is_fpd2', markers=True, text=(dt['is_fpd2']*100).map("{:.1f}%".format))
        fig1.update_layout(xaxis_type='category', yaxis_title="% FPD")
        st.plotly_chart(fig1, use_container_width=True)
    with c2:
        st.subheader("2. Físico vs Digital")
        dfd = df_base[df_base['cosecha_x'].isin(visualizar)].groupby(['cosecha_x','origen'])['is_fpd2'].mean().reset_index()
        fig2 = px.line(dfd, x='cosecha_x', y='is_fpd2', color='origen', markers=True)
        fig2.update_layout(xaxis_type='category', legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.subheader("3. Análisis Detallado (YoY & Indicadores)")
    cy1, cy2 = st.columns(2)
    with cy1:
        dy = df_base[df_base['anio'].isin(['2023','2024','2025'])].groupby(['mes_num','mes_nombre','anio'])['is_fpd2'].mean().reset_index()
        figy = px.line(dy.sort_values('mes_num'), x='mes_nombre', y='is_fpd2', color='anio', markers=True, title="Comparativo Anual")
        st.plotly_chart(figy, use_container_width=True)
    with cy2:
        dh = df_base[df_base['cosecha_x'].isin(visualizar)].groupby('cosecha_x')[['is_fpd2','is_np']].mean().reset_index()
        figh = px.line(dh, x='cosecha_x', y=['is_fpd2','is_np'], markers=True, title="FPD vs No Pago (NP)")
        figh.update_layout(xaxis_type='category', legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(figh, use_container_width=True)

# --- TAB 2: EJECUTIVO (RESTAURADA) ---
with tab2:
    st.header("📋 Resumen Ejecutivo Global")
    df_ex = df[df['cosecha_x'] == mes_actual]
    
    # Cards Regionales
    res_uni = df_ex.groupby('unidad')['is_fpd2'].mean().reset_index()
    if not res_uni.empty:
        mj, pr = res_uni.loc[res_uni['is_fpd2'].idxmin()], res_uni.loc[res_uni['is_fpd2'].idxmax()]
        colr1, colr2 = st.columns(2)
        colr1.success(f"🟢 **Mejor Región:** {mj['unidad']} ({mj['is_fpd2']*100:.2f}%)")
        colr2.error(f"🔴 **Mayor Riesgo:** {pr['unidad']} ({pr['is_fpd2']*100:.2f}%)")

    st.divider()
    # Comparativa Deterioro
    st.markdown(f"#### Comparativa de Deterioro ({mes_anterior} vs {mes_actual})")
    df_comp = df[df['cosecha_x'].isin([mes_anterior, mes_actual])].pivot_table(index='sucursal', columns='cosecha_x', values='is_fpd2', aggfunc='mean')
    if mes_anterior in df_comp.columns and mes_actual in df_comp.columns:
        df_comp['deterioro'] = df_comp[mes_actual] - df_comp[mes_anterior]
        peor_suc = df_comp['deterioro'].idxmax()
        st.warning(f"📉 **Mayor Deterioro:** {peor_suc} (+{df_comp.loc[peor_suc, 'deterioro']*100:.1f} pts)")

    st.divider()
    # Matriz Detalle (Bottom 10)
    st.subheader("Detalle Riesgo Producto/Sucursal (Bottom 10)")
    r_calc = df_base[df_base['cosecha_x'] == mes_actual].groupby('sucursal')['is_fpd2'].agg(['count', 'mean']).reset_index()
    r_calc = r_calc[r_calc['count'] >= MIN_CREDITOS_RANKING]
    worst_10 = r_calc.sort_values('mean', ascending=False).head(10)['sucursal'].tolist()
    
    if worst_10:
        df_m = df_base[(df_base['cosecha_x'] == mes_actual) & (df_base['sucursal'].isin(worst_10))]
        p_mat = df_m.groupby(['sucursal', 'producto']).agg(FPD=('is_fpd2', 'sum'), Tot=('is_fpd2', 'count'), Tasa=('is_fpd2', 'mean')).reset_index()
        p_mat['Detalle'] = p_mat.apply(lambda r: f"{int(r['FPD'])} | {int(r['Tot'])} | {(r['Tasa']*100):.1f}%", axis=1)
        st.dataframe(p_mat.pivot(index='sucursal', columns='producto', values='Detalle').fillna("-").style.set_table_styles([
            {'selector': 'th', 'props': [('background-color', '#e0f7fa'), ('color', 'black'), ('font-weight', 'bold')]}
        ]), use_container_width=True)

# --- TAB 3: INSIGHTS (RESTAURADA) ---
with tab3:
    st.header("🎯 Insights Estratégicos")
    st.subheader("1. Sensibilidad por Monto (Volumen vs Riesgo)")
    df_monto = df[df['cosecha_x'] == mes_actual].copy()
    bins = [0, 5000, 10000, 20000, 1000000]
    df_monto['rango'] = pd.cut(df_monto['monto'], bins=bins, labels=['0-5k','5k-10k','10k-20k','>20k'])
    res_m = df_monto.groupby('rango')['is_fpd2'].agg(['mean','count']).reset_index()
    
    fig_dual = go.Figure()
    fig_dual.add_trace(go.Bar(x=res_m['rango'], y=res_m['count'], name="Volumen", marker_color='#bbdefb', yaxis='y1'))
    fig_dual.add_trace(go.Scatter(x=res_m['rango'], y=res_m['mean']*100, name="% FPD", line=dict(color='#d62728', width=3), yaxis='y2'))
    fig_dual.update_layout(yaxis=dict(title="Créditos"), yaxis2=dict(title="% FPD", overlaying='y', side='right'), legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig_dual, use_container_width=True)

    st.divider()
    st.subheader("2. Mapa de Riesgo Regional (Heatmap)")
    dh_map = df[df['cosecha_x'].isin(maduras[-6:])].pivot_table(index='unidad', columns='cosecha_x', values='is_fpd2', aggfunc='mean')
    fig_h = px.imshow(dh_map, text_auto=".1%", color_continuous_scale='RdYlGn_r')
    fig_h.update_xaxes(type='category')
    st.plotly_chart(fig_h, use_container_width=True)

# --- TAB 4: EXPORTAR (REGLAS ESTRICTAS) ---
with tab4:
    st.header("📥 Exportar Próxima Cosecha")
    if mes_siguiente:
        st.info(f"Procesando: **{mes_siguiente}**")
        df_ex_next = df[df['cosecha_x'] == mes_siguiente].copy()
        if sel_uni: df_ex_next = df_ex_next[df_ex_next['unidad'].isin(sel_uni)]
        if sel_suc: df_ex_next = df_ex_next[df_ex_next['sucursal'].isin(sel_suc)]
        
        # Filtros de Exportación
        df_final = df_ex_next[df_ex_next['is_fpd2'] == 1]
        cols = ['id_credito', 'id_producto', 'producto_agrupado', 'origen2', 'cosecha', 'sucursal', 'fpd2']
        df_csv = df_final[[c for c in cols if c in df_final.columns]]
        
        st.write(f"Casos con FPD2=1: `{len(df_csv)}`")
        st.download_button("💾 Descargar CSV", df_csv.to_csv(index=False).encode('utf-8'), f"FPD_DETALLE_{mes_siguiente}.csv", use_container_width=True)
        st.dataframe(df_csv, use_container_width=True, hide_index=True)
    else:
        st.warning("No hay cosecha siguiente disponible.")