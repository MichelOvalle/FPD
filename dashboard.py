import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Dashboard FPD2 Pro", layout="wide")
st.title("📊 Monitor FPD")

# Configuraciones originales
MESES_A_EXCLUIR = 2    
VENTANA_MESES = 24     
MIN_CREDITOS_RANKING = 5 

# --- 2. FUNCIÓN DE CARGA (INTEGRAL v1.0) ---
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
            df = pd.read_excel(archivo, engine='openpyxl')
        else:
            df = pd.read_csv(archivo, encoding='latin1')
    except Exception as e:
        st.error(f"Error leyendo el archivo: {e}")
        st.stop()

    df.columns = [str(c).lower().strip() for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]

    # Buscador de columnas v1.0
    col_cosecha = next((c for c in df.columns if 'cosecha' in c), None)
    col_fpd2 = next((c for c in df.columns if 'fpd2' in c or 'fpd' in c), None)
    col_np = next((c for c in df.columns if 'np' == c or 'np' in c.split('_')), None) 
    col_monto = next((c for c in df.columns if 'monto' in c and 'otorgado' in c), None) or next((c for c in df.columns if 'monto' in c), None)

    if not col_cosecha or not col_fpd2:
        st.error(f"Faltan columnas clave.")
        st.stop()

    df_clean = df.copy()
    df_clean['cosecha_str'] = df_clean[col_cosecha].astype(str).str.replace(r'\.0$', '', regex=True)
    df_clean['fecha_dt'] = pd.to_datetime(df_clean['cosecha_str'], format='%Y%m', errors='coerce')
    df_clean['anio'] = df_clean['fecha_dt'].dt.year.fillna(0).astype(int).astype(str)
    df_clean['mes_num'] = df_clean['fecha_dt'].dt.month.fillna(0).astype(int)
    
    mapa_meses = {1:'Ene', 2:'Feb', 3:'Mar', 4:'Abr', 5:'May', 6:'Jun', 7:'Jul', 8:'Ago', 9:'Sep', 10:'Oct', 11:'Nov', 12:'Dic', 0:'SinDato'}
    df_clean['mes_nombre'] = df_clean['mes_num'].map(mapa_meses)
    
    df_clean['is_fpd2'] = df_clean[col_fpd2].astype(str).apply(lambda x: 1 if 'FPD' in x.upper() or '1' in x else 0)
    df_clean['is_np'] = df_clean[col_np].astype(str).apply(lambda x: 1 if 'NP' in x.upper() else 0) if col_np else 0
    df_clean['monto'] = pd.to_numeric(df_clean[col_monto], errors='coerce').fillna(0)

    def find_best_column(dataframe, candidates_priority, fallback_search_term):
        for cand in candidates_priority:
            if cand in dataframe.columns: return cand
        possible = [c for c in dataframe.columns if fallback_search_term in c and 'id' not in c]
        return possible[0] if possible else None

    # Mapeo de dimensiones v1.0
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

    # Columnas para Tab 4
    df_clean['id_credito'] = df_clean[next((c for c in df.columns if 'id_credito' in c), df.columns[0])]
    df_clean['id_producto'] = df_clean[next((c for c in df.columns if 'id_producto' in c), df.columns[0])]
    df_clean['producto_agrupado'] = df_clean['producto']
    df_clean['origen2'] = df_clean['origen']
    df_clean['cosecha'] = df_clean['cosecha_str']
    df_clean['fpd2'] = df_clean[col_fpd2]

    return df_clean

df = load_data()

# --- 3. LÓGICA TEMPORAL v1.0 ---
todas = sorted(df['cosecha_x'].unique())
maduras = todas[:-MESES_A_EXCLUIR] if len(todas) > MESES_A_EXCLUIR else todas
visualizar = maduras[-VENTANA_MESES:] if len(maduras) > VENTANA_MESES else maduras
mes_actual = maduras[-1] if maduras else None
mes_anterior = maduras[-2] if len(maduras) >= 2 else None

# Identificar cosecha siguiente (Tab 4)
idx_act = todas.index(mes_actual) if mes_actual in todas else -1
mes_siguiente = todas[idx_act + 1] if idx_act != -1 and (idx_act + 1) < len(todas) else None

# --- 4. FILTROS SIDEBAR v1.0 ---
st.sidebar.header("🎯 Filtros Generales")
sel_uni = st.sidebar.multiselect("1. Unidad Regional:", sorted(df['unidad'].unique()))
sel_suc = st.sidebar.multiselect("2. Sucursal:", sorted(df['sucursal'].unique()))
sel_pro = st.sidebar.multiselect("3. Producto Agrupado:", sorted(df['producto'].unique()))
sel_tip = st.sidebar.multiselect("4. Tipo de Cliente:", sorted(df['tipo_cliente'].unique()))

df_base = df.copy()
if sel_uni: df_base = df_base[df_base['unidad'].isin(sel_uni)]
if sel_suc: df_base = df_base[df_base['sucursal'].isin(sel_suc)]
if sel_pro: df_base = df_base[df_base['producto'].isin(sel_pro)]
if sel_tip: df_base = df_base[df_base['tipo_cliente'].isin(sel_tip)]

# --- CÁLCULO CENTRALIZADO BOTTOM 10 v1.0 ---
worst_10_sucursales = []
df_ranking_calc = pd.DataFrame()
if mes_actual and not df_base.empty:
    df_ranking_base = df_base[df_base['cosecha_x'] == mes_actual].copy()
    mask_999 = df_ranking_base['sucursal'].astype(str).str.contains("999", na=False)
    mask_nomina = df_ranking_base['sucursal'].astype(str).str.lower().str.contains("nomina colaboradores", na=False)
    df_ranking_calc = df_ranking_base[~(mask_999 | mask_nomina)]
    r_calc = df_ranking_calc.groupby('sucursal')['is_fpd2'].agg(['count', 'sum', 'mean']).reset_index()
    r_clean_calc = r_calc[r_calc['count'] >= MIN_CREDITOS_RANKING]
    if not r_clean_calc.empty:
        worst_10_sucursales = r_clean_calc.sort_values('mean', ascending=False).head(10)['sucursal'].tolist()

# --- 5. PESTAÑAS ---
tab1, tab2, tab3, tab4 = st.tabs(["📉 Monitor FPD", "📋 Resumen Ejecutivo", "🎯 Insights Estratégicos", "📥 Exportar"])

# --- TAB 1: MONITOR FPD (INTEGRAL v1.0) ---
with tab1:
    if df_base.empty: st.warning("No hay datos.")
    else:
        st.markdown("### Resumen Operativo")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("1. Tendencia Global")
            d = df_base[df_base['cosecha_x'].isin(visualizar)].groupby('cosecha_x')['is_fpd2'].mean().reset_index()
            fig = px.line(d, x='cosecha_x', y='is_fpd2', markers=True, text=(d['is_fpd2']*100).map("{:.1f}%".format))
            fig.update_layout(xaxis_type='category', yaxis_title="% FPD2")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.subheader("2. Físico vs Digital")
            mask = df_base['origen'].str.contains('Fisico|Digital', case=False, na=False)
            d_comp = df_base[mask & df_base['cosecha_x'].isin(visualizar)].groupby(['cosecha_x', 'origen'])['is_fpd2'].mean().reset_index()
            fig2 = px.line(d_comp, x='cosecha_x', y='is_fpd2', color='origen', markers=True)
            fig2.update_layout(xaxis_type='category', legend=dict(orientation="h", y=-0.2))
            st.plotly_chart(fig2, use_container_width=True)

        st.divider()
        st.subheader(f"3. Ranking de Sucursales (Cosecha {mes_actual})")
        if not r_clean_calc.empty:
            rx1, rx2 = st.columns(2)
            r_clean_calc['FPD2 %'] = r_clean_calc['mean'] * 100
            conf = {"FPD2 %": st.column_config.NumberColumn(format="%.2f%%")}
            rx1.dataframe(r_clean_calc.sort_values('mean', ascending=False).head(10)[['sucursal', 'FPD2 %']], hide_index=True, column_config=conf, use_container_width=True)
            rx2.dataframe(r_clean_calc.sort_values('mean', ascending=True).head(10)[['sucursal', 'FPD2 %']], hide_index=True, column_config=conf, use_container_width=True)

        st.divider()
        st.subheader("4. Análisis Detallado YoY e Indicadores")
        cy1, cy2 = st.columns(2)
        with cy1:
            dy = df_base[df_base['anio'].isin(['2023','2024','2025'])].groupby(['mes_num','mes_nombre','anio'])['is_fpd2'].mean().reset_index()
            figy = px.line(dy.sort_values('mes_num'), x='mes_nombre', y='is_fpd2', color='anio', markers=True, title="Comparativo Anual")
            st.plotly_chart(figy, use_container_width=True)
        with cy2:
            dh = df_base[df_base['cosecha_x'].isin(visualizar)].groupby('cosecha_x')[['is_fpd2','is_np']].mean().reset_index()
            fig_dh = px.line(dh, x='cosecha_x', y=['is_fpd2', 'is_np'], markers=True, title="FPD vs No Pago (NP)")
            fig_dh.update_layout(xaxis_type='category', legend=dict(orientation="h", y=-0.2))
            st.plotly_chart(fig_dh, use_container_width=True)

# --- TAB 2: RESUMEN EJECUTIVO (INTEGRAL v1.0) ---
with tab2:
    st.header("📋 Resumen Ejecutivo Global")
    df_ex = df[df['cosecha_x'] == mes_actual]
    
    # Cards Regionales HTML/CSS
    res_uni = df_ex.groupby('unidad')['is_fpd2'].mean().reset_index()
    if not res_uni.empty:
        mj, pr = res_uni.loc[res_uni['is_fpd2'].idxmin()], res_uni.loc[res_uni['is_fpd2'].idxmax()]
        cr1, cr2 = st.columns(2)
        cr1.markdown(f"<div style='background-color: #e8f5e9; padding: 20px; border-radius: 12px;'><h3>🟢 Mejor Región</h3><h4>{mj['unidad']}</h4><h2>{mj['is_fpd2']*100:.2f}%</h2></div>", unsafe_allow_html=True)
        cr2.markdown(f"<div style='background-color: #ffebee; padding: 20px; border-radius: 12px;'><h3>🔴 Mayor Riesgo</h3><h4>{pr['unidad']}</h4><h2>{pr['is_fpd2']*100:.2f}%</h2></div>", unsafe_allow_html=True)

    st.divider()
    # Deterioro v1.0
    st.markdown(f"#### 🏦 Comparativa de Sucursales ({mes_anterior} vs {mes_actual})")
    df_comp_s = df[df['cosecha_x'].isin([mes_anterior, mes_actual])].pivot_table(index='sucursal', columns='cosecha_x', values='is_fpd2', aggfunc='mean')
    if mes_anterior in df_comp_s.columns and mes_actual in df_comp_s.columns:
        df_comp_s['diff'] = df_comp_s[mes_actual] - df_comp_s[mes_anterior]
        peor_s = df_comp_s['diff'].idxmax()
        st.warning(f"📉 **Mayor Deterioro:** {peor_s} (Aumentó {df_comp_s.loc[peor_s, 'diff']*100:.1f} pts)")

    st.divider()
    # Matriz Detalle v1.0 (CSS exacto)
    st.markdown("#### 4. Detalle de Riesgo por Producto y Sucursal (Bottom 10)")
    if worst_10_sucursales:
        df_mat = df_base[(df_base['cosecha_x'] == mes_actual) & (df_base['sucursal'].isin(worst_10_sucursales))]
        piv = df_mat.groupby(['sucursal', 'producto']).agg(FPD=('is_fpd2', 'sum'), T=('is_fpd2', 'count'), P=('is_fpd2', 'mean')).reset_index()
        piv['Det'] = piv.apply(lambda r: f"{int(r['FPD'])} | {int(r['T'])} | {(r['P']*100):.1f}%", axis=1)
        st.dataframe(piv.pivot(index='sucursal', columns='producto', values='Det').fillna("-").style.set_table_styles([
            {'selector': 'th', 'props': [('background-color', '#e0f7fa'), ('color', 'black'), ('font-weight', 'bold'), ('font-size', '10pt')]},
            {'selector': 'tbody th', 'props': [('font-weight', 'bold'), ('color', 'black')]}
        ]), use_container_width=True)

# --- TAB 3: INSIGHTS (INTEGRAL v1.0) ---
with tab3:
    st.header("🎯 Insights Estratégicos")
    st.subheader("1. Sensibilidad por Monto (Dual Axis)")
    df_m = df[df['cosecha_x'] == mes_actual].copy()
    df_m['rango'] = pd.cut(df_m['monto'], bins=[0, 5000, 10000, 20000, 1000000], labels=['0-5k','5k-10k','10k-20k','>20k'])
    res_m = df_m.groupby('rango')['is_fpd2'].agg(['mean','count']).reset_index()
    fig_dual = go.Figure()
    fig_dual.add_trace(go.Bar(x=res_m['rango'], y=res_m['count'], name="Volumen", marker_color='#bbdefb', yaxis='y1'))
    fig_dual.add_trace(go.Scatter(x=res_m['rango'], y=res_m['mean']*100, name="% FPD", line=dict(color='#d62728', width=3), yaxis='y2'))
    fig_dual.update_layout(yaxis=dict(title="Créditos"), yaxis2=dict(title="% FPD", overlaying='y', side='right'), legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig_dual, use_container_width=True)

    st.divider()
    st.subheader("2. Mapa de Riesgo Regional (Heatmap)")
    dh = df[df['cosecha_x'].isin(maduras[-6:])].pivot_table(index='unidad', columns='cosecha_x', values='is_fpd2', aggfunc='mean')
    st.plotly_chart(px.imshow(dh, text_auto=".1%", color_continuous_scale='RdYlGn_r').update_xaxes(type='category'), use_container_width=True)

# --- TAB 4: EXPORTAR (REGLAS SOLICITADAS) ---
with tab4:
    st.header("📥 Exportar")
    if mes_siguiente:
        st.info(f"Exportando Cosecha Alerta: **{mes_siguiente}**")
        df_next = df[df['cosecha_x'] == mes_siguiente].copy()
        if sel_uni: df_next = df_next[df_next['unidad'].isin(sel_uni)]
        if sel_suc: df_next = df_next[df_next['sucursal'].isin(sel_suc)]
        
        # Filtros: fpd2=1 + Columnas específicas
        df_final = df_next[df_next['is_fpd2'] == 1]
        cols = ['id_credito', 'id_producto', 'producto_agrupado', 'origen2', 'cosecha', 'sucursal', 'fpd2']
        df_csv = df_final[[c for c in cols if c in df_final.columns]]
        
        st.write(f"Casos encontrados: `{len(df_csv)}`")
        st.download_button("💾 Descargar CSV", df_csv.to_csv(index=False).encode('utf-8'), f"FPD_DETALLE_{mes_siguiente}.csv", "text/csv", use_container_width=True)
        st.dataframe(df_csv, use_container_width=True, hide_index=True)
    else:
        st.error("No hay cosecha siguiente.")