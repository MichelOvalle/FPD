import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Dashboard FPD2 Pro", layout="wide")
st.title("📊 Monitor FPD")

# Configuraciones de Negocio
MESES_A_EXCLUIR = 2    
VENTANA_MESES = 24     
MIN_CREDITOS_RANKING = 5 

# --- 2. FUNCIÓN DE CARGA Y PROCESAMIENTO ---
@st.cache_data 
def load_data():
    archivo = 'fpd gemini.xlsx'
    if not os.path.exists(archivo):
        archivo = 'fpd gemini.csv'
        if not os.path.exists(archivo):
             st.error("⚠️ Archivo no encontrado.")
             st.stop()
    
    try:
        df = pd.read_excel(archivo) if archivo.endswith('.xlsx') else pd.read_csv(archivo, encoding='latin1')
    except Exception as e:
        st.error(f"Error: {e}"); st.stop()

    # Estandarización para lógica interna
    df.columns = [str(c).lower().strip() for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]

    # Identificación de columnas clave
    col_cosecha = next((c for c in df.columns if 'cosecha' in c), None)
    col_fpd = next((c for c in df.columns if 'fpd2' in c or 'fpd' in c), None)
    col_np = next((c for c in df.columns if 'np' == c or 'np' in c.split('_')), None)
    col_monto = next((c for c in df.columns if 'monto' in c), None)
    
    # Columnas para Tab 4 (Búsqueda flexible)
    col_id_cred = next((c for c in df.columns if 'id_credito' in c or 'credito' in c), col_cosecha)
    col_id_prod = next((c for c in df.columns if 'id_producto' in c), col_cosecha)
    col_prod_agrup = next((c for c in df.columns if 'producto_agrupado' in c or 'producto' in c), col_cosecha)
    col_origen2 = next((c for c in df.columns if 'origen2' in c or 'origen' in c), col_cosecha)

    df_clean = df.copy()
    
    # Fechas y Cosechas
    df_clean['cosecha_str'] = df_clean[col_cosecha].astype(str).str.replace(r'\.0$', '', regex=True)
    df_clean['fecha_dt'] = pd.to_datetime(df_clean['cosecha_str'], format='%Y%m', errors='coerce')
    df_clean['anio'] = df_clean['fecha_dt'].dt.year.fillna(0).astype(int).astype(str)
    df_clean['mes_num'] = df_clean['fecha_dt'].dt.month.fillna(0).astype(int)
    mapa_meses = {1:'Ene', 2:'Feb', 3:'Mar', 4:'Abr', 5:'May', 6:'Jun', 7:'Jul', 8:'Ago', 9:'Sep', 10:'Oct', 11:'Nov', 12:'Dic', 0:'SD'}
    df_clean['mes_nombre'] = df_clean['mes_num'].map(mapa_meses)
    
    # Lógica de FPD (Binario para cálculos)
    df_clean['is_fpd2'] = df_clean[col_fpd].astype(str).apply(lambda x: 1 if 'FPD' in x.upper() or '1' in x else 0)
    df_clean['is_np'] = df_clean[col_np].astype(str).apply(lambda x: 1 if 'NP' in x.upper() else 0) if col_np else 0
    df_clean['monto'] = pd.to_numeric(df_clean[col_monto], errors='coerce').fillna(0) if col_monto else 0

    # Normalización de dimensiones para filtros
    c_suc = next((c for c in df.columns if 'sucursal' in c), col_cosecha)
    c_uni = next((c for c in df.columns if 'unidad' in c or 'regional' in c), col_cosecha)
    c_tip = next((c for c in df.columns if 'tipo_cliente' in c or 'tipo' in c), col_cosecha)
    
    df_clean['sucursal'] = df_clean[c_suc].fillna('Sin Dato').astype(str)
    df_clean['unidad'] = df_clean[c_uni].fillna('Sin Dato').astype(str)
    df_clean['producto'] = df_clean[col_prod_agrup].fillna('Sin Dato').astype(str)
    df_clean['tipo_cliente'] = df_clean[c_tip].fillna('Sin Dato').astype(str)
    df_clean['origen'] = df_clean[col_origen2].fillna('Sin Dato').astype(str).str.title()
    df_clean['cosecha_x'] = df_clean['cosecha_str']

    # Columnas originales preservadas para Tab 4
    df_clean['id_credito'] = df_clean[col_id_cred]
    df_clean['id_producto'] = df_clean[col_id_prod]
    df_clean['producto_agrupado'] = df_clean[col_prod_agrup]
    df_clean['origen2'] = df_clean[col_origen2]
    df_clean['cosecha'] = df_clean[col_cosecha]
    df_clean['fpd2'] = df_clean[col_fpd]

    return df_clean

df = load_data()

# --- 3. TIEMPOS ---
todas = sorted(df['cosecha_x'].unique())
maduras = todas[:-MESES_A_EXCLUIR] if len(todas) > MESES_A_EXCLUIR else todas
visualizar = maduras[-VENTANA_MESES:] if len(maduras) > VENTANA_MESES else maduras
mes_actual = maduras[-1] if maduras else None
mes_anterior = maduras[-2] if len(maduras) >= 2 else None
idx = todas.index(mes_actual) if mes_actual in todas else -1
mes_siguiente = todas[idx + 1] if idx != -1 and (idx + 1) < len(todas) else None

# --- 4. FILTROS ---
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

# --- 5. PESTAÑAS ---
tab1, tab2, tab3, tab4 = st.tabs(["📉 Monitor FPD", "📋 Resumen Ejecutivo", "🎯 Insights", "📥 Exportar"])

with tab1:
    st.subheader(f"Análisis de Tendencia ({visualizar[0]} - {visualizar[-1]})")
    d = df_base[df_base['cosecha_x'].isin(visualizar)].groupby('cosecha_x')['is_fpd2'].mean().reset_index()
    d['FPD2 %'] = d['is_fpd2'] * 100
    fig = px.line(d, x='cosecha_x', y='FPD2 %', markers=True, text=d['FPD2 %'].apply(lambda x: f'{x:.1f}%'))
    st.plotly_chart(fig, use_container_width=True)
    
    st.subheader(f"Ranking Sucursales (Cosecha {mes_actual})")
    df_rank = df_base[df_base['cosecha_x'] == mes_actual].groupby('sucursal')['is_fpd2'].agg(['count', 'mean']).reset_index()
    df_rank = df_rank[df_rank['count'] >= MIN_CREDITOS_RANKING].sort_values('mean', ascending=False)
    df_rank['FPD2 %'] = df_rank['mean'] * 100
    st.dataframe(df_rank[['sucursal', 'count', 'FPD2 %']].head(10), use_container_width=True, hide_index=True)

with tab2:
    st.header("📋 Resumen Ejecutivo Global")
    df_res = df[df['cosecha_x'] == mes_actual] # Global
    col1, col2 = st.columns(2)
    with col1:
        res_prod = df_res.groupby('producto')['is_fpd2'].mean().sort_values()
        st.write("**Mejor Producto:**", res_prod.index[0])
    with col2:
        st.write("**Producto Crítico:**", res_prod.index[-1])
    
    st.divider()
    st.write("**Comparativa Regional**")
    res_uni = df_res.groupby('unidad')['is_fpd2'].mean().reset_index()
    res_uni['FPD %'] = res_uni['is_fpd2'] * 100
    fig_uni = px.bar(res_uni, x='unidad', y='FPD %', color='FPD %', color_continuous_scale='RdYlGn_r')
    st.plotly_chart(fig_uni, use_container_width=True)

with tab3:
    st.header("🎯 Insights Estratégicos")
    if len(maduras) >= 6:
        df_heat = df[df['cosecha_x'].isin(maduras[-6:])].groupby(['unidad', 'cosecha_x'])['is_fpd2'].mean().reset_index()
        fig_h = px.imshow(df_heat.pivot(index='unidad', columns='cosecha_x', values='is_fpd2'), text_auto='.2%', color_continuous_scale='RdYlGn_r')
        st.plotly_chart(fig_h, use_container_width=True)
    
    # Pareto
    st.subheader("Ley de Pareto (Sucursales vs Casos FPD)")
    df_par = df[df['cosecha_x'] == mes_actual].groupby('sucursal')['is_fpd2'].sum().sort_values(ascending=False).reset_index()
    df_par['% Acum'] = df_par['is_fpd2'].cumsum() / df_par['is_fpd2'].sum() * 100
    fig_p = px.bar(df_par.head(20), x='sucursal', y='is_fpd2', text_auto=True)
    st.plotly_chart(fig_p, use_container_width=True)

with tab4:
    st.header("📥 Exportar Datos")
    if mes_siguiente:
        st.subheader(f"🚀 Cosecha Early Warning: {mes_siguiente}")
        # Filtrado según reglas del usuario
        df_exp = df[df['cosecha_x'] == mes_siguiente].copy()
        if sel_uni: df_exp = df_exp[df_exp['unidad'].isin(sel_uni)]
        if sel_suc: df_exp = df_exp[df_exp['sucursal'].isin(sel_suc)]
        
        # REGLA 1: Solo fpd2 = 1
        df_exp = df_exp[df_exp['is_fpd2'] == 1]
        
        # REGLA 2: Solo columnas solicitadas
        cols_req = ['id_credito', 'id_producto', 'producto_agrupado', 'origen2', 'cosecha', 'sucursal', 'fpd2']
        # Validar existencia
        cols_final = [c for c in cols_req if c in df_exp.columns]
        df_final = df_exp[cols_final]
        
        st.write(f"Casos detectados con FPD2=1: `{len(df_final)}`")
        
        @st.cache_data
        def to_csv(dataframe): return dataframe.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label=f"📥 Descargar Detalle FPD {mes_siguiente}",
            data=to_csv(df_final),
            file_name=f"FPD_DETALLE_{mes_siguiente}.csv",
            mime="text/csv",
            use_container_width=True
        )
        st.dataframe(df_final, use_container_width=True)
    else:
        st.warning("No hay cosecha siguiente disponible para exportar.")