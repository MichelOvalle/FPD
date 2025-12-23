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

# --- 2. CARGA DE DATOS (Lógica de búsqueda inteligente recuperada) ---
@st.cache_data 
def load_data():
    archivo = 'fpd gemini.xlsx' if os.path.exists('fpd gemini.xlsx') else 'fpd gemini.csv'
    if not os.path.exists(archivo):
        st.error("⚠️ Archivo no encontrado."); st.stop()
    
    df = pd.read_excel(archivo) if archivo.endswith('.xlsx') else pd.read_csv(archivo, encoding='latin1')
    df.columns = [str(c).lower().strip() for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]

    def find_col(dataframe, candidates, fallback):
        for cand in candidates:
            if cand in dataframe.columns: return cand
        possible = [c for c in dataframe.columns if fallback in c and 'id' not in c]
        return possible[0] if possible else None

    # Identificación de columnas
    col_cosecha = next((c for c in df.columns if 'cosecha' in c), None)
    col_fpd2 = next((c for c in df.columns if 'fpd2' in c or 'fpd' in c), None)
    col_monto = find_col(df, ['monto_otorgado', 'monto'], 'monto')
    
    df_clean = df.copy()
    df_clean['cosecha_str'] = df_clean[col_cosecha].astype(str).str.replace(r'\.0$', '', regex=True)
    df_clean['fecha_dt'] = pd.to_datetime(df_clean['cosecha_str'], format='%Y%m', errors='coerce')
    df_clean['anio'] = df_clean['fecha_dt'].dt.year.fillna(0).astype(int).astype(str)
    df_clean['mes_num'] = df_clean['fecha_dt'].dt.month.fillna(0).astype(int)
    
    # Flags de Negocio
    df_clean['is_fpd2'] = df_clean[col_fpd2].astype(str).apply(lambda x: 1 if 'FPD' in x.upper() or '1' in x else 0)
    df_clean['monto'] = pd.to_numeric(df_clean[col_monto], errors='coerce').fillna(0)

    # Dimensiones para filtros
    df_clean['sucursal'] = df_clean[find_col(df_clean, ['sucursal'], 'sucursal')].fillna('Sin Dato').astype(str)
    df_clean['unidad'] = df_clean[find_col(df_clean, ['unidad_regional', 'regional'], 'unidad')].fillna('Sin Dato').astype(str)
    df_clean['producto'] = df_clean[find_col(df_clean, ['producto_agrupado', 'producto'], 'producto')].fillna('Sin Dato').astype(str)
    df_clean['origen'] = df_clean[find_col(df_clean, ['origen2', 'origen'], 'origen')].fillna('Sin Dato').astype(str).str.title()
    df_clean['tipo_cliente'] = df_clean[find_col(df_clean, ['tipo_cliente', 'tipo'], 'cliente')].fillna('Sin Dato').astype(str)
    
    # Columnas para Tab 4
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
idx = todas.index(mes_actual) if mes_actual in todas else -1
mes_siguiente = todas[idx + 1] if idx != -1 and (idx + 1) < len(todas) else None

# --- 4. FILTROS ---
st.sidebar.header("🎯 Filtros")
sel_uni = st.sidebar.multiselect("Regional:", sorted(df['unidad'].unique()))
sel_suc = st.sidebar.multiselect("Sucursal:", sorted(df['sucursal'].unique()))

df_base = df.copy()
if sel_uni: df_base = df_base[df_base['unidad'].isin(sel_uni)]
if sel_suc: df_base = df_base[df_base['sucursal'].isin(sel_suc)]

# --- 5. PESTAÑAS ---
tab1, tab2, tab3, tab4 = st.tabs(["📉 Monitor FPD", "📋 Resumen Ejecutivo", "🎯 Insights", "📥 Exportar"])

with tab1:
    st.markdown(f"### Tendencia Global ({visualizar[0]} - {visualizar[-1]})")
    d_trend = df_base[df_base['cosecha_x'].isin(visualizar)].groupby('cosecha_x')['is_fpd2'].mean().reset_index()
    d_trend['FPD2 %'] = d_trend['is_fpd2'] * 100
    fig = px.line(d_trend, x='cosecha_x', y='FPD2 %', markers=True, text=d_trend['FPD2 %'].map("{:.1f}%".format))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader(f"Rankings Sucursales ({mes_actual})")
    df_r = df_base[df_base['cosecha_x'] == mes_actual].groupby('sucursal')['is_fpd2'].agg(['count', 'mean']).reset_index()
    df_r = df_r[df_r['count'] >= MIN_CREDITOS_RANKING]
    df_r['FPD2 %'] = df_r['mean'] * 100
    
    c1, c2 = st.columns(2)
    config = {"FPD2 %": st.column_config.NumberColumn(format="%.2f%%")}
    c1.write("**Top 10 Peores Tasa**")
    c1.dataframe(df_r.sort_values('mean', ascending=False).head(10)[['sucursal', 'FPD2 %']], hide_index=True, column_config=config, use_container_width=True)
    c2.write("**Top 10 Mejores Tasa**")
    c2.dataframe(df_r.sort_values('mean', ascending=True).head(10)[['sucursal', 'FPD2 %']], hide_index=True, column_config=config, use_container_width=True)

with tab2:
    st.header("📋 Resumen Ejecutivo Global")
    df_exec = df[df['cosecha_x'] == mes_actual]
    
    # Cards de Producto
    res_prod = df_exec.groupby('producto')['is_fpd2'].agg(['mean', 'count']).reset_index()
    res_prod = res_prod[res_prod['count'] >= MIN_CREDITOS_RANKING]
    promedio_g = df_exec['is_fpd2'].mean()
    
    colp1, colp2 = st.columns(2)
    p_mejor = res_prod.loc[res_prod['mean'].idxmin()]
    p_peor = res_prod.loc[res_prod['mean'].idxmax()]
    colp1.success(f"🏆 **Mejor Producto:** {p_mejor['producto']} ({p_mejor['mean']*100:.2f}%)")
    colp2.error(f"⚠️ **Mayor Riesgo:** {p_peor['producto']} ({p_peor['mean']*100:.2f}%)")

    st.divider()
    # Matriz Bottom 10 (Formato Base)
    st.subheader("Detalle Riesgo por Producto/Sucursal (Bottom 10)")
    worst_sucs = df_r.sort_values('mean', ascending=False).head(10)['sucursal'].tolist()
    df_matriz = df_base[(df_base['cosecha_x'] == mes_actual) & (df_base['sucursal'].isin(worst_sucs))]
    
    if not df_matriz.empty:
        pivot_data = df_matriz.groupby(['sucursal', 'producto']).agg(
            FPD_Casos=('is_fpd2', 'sum'),
            Total=('is_fpd2', 'count'),
            Tasa=('is_fpd2', 'mean')
        ).reset_index()
        pivot_data['Tasa'] = (pivot_data['Tasa'] * 100).map("{:.1f}%".format)
        
        table = pivot_data.pivot(index='sucursal', columns='producto', values=['FPD_Casos', 'Total', 'Tasa'])
        st.dataframe(table.style.set_table_styles([
            {'selector': 'th', 'props': [('background-color', '#e0f7fa'), ('color', 'black'), ('font-weight', 'bold')]}
        ]), use_container_width=True)

with tab4:
    st.header("📥 Exportar")
    if mes_siguiente:
        st.info(f"Cosecha detectada para exportar: **{mes_siguiente}**")
        df_exp = df[df['cosecha_x'] == mes_siguiente].copy()
        if sel_uni: df_exp = df_exp[df_exp['unidad'].isin(sel_uni)]
        if sel_suc: df_exp = df_exp[df_exp['sucursal'].isin(sel_suc)]
        
        # Filtros solicitados
        df_exp = df_exp[df_exp['is_fpd2'] == 1]
        cols = ['id_credito', 'id_producto', 'producto_agrupado', 'origen2', 'cosecha', 'sucursal', 'fpd2']
        df_final = df_exp[[c for c in cols if c in df_exp.columns]]
        
        st.write(f"Total registros fpd2=1: `{len(df_final)}`")
        st.download_button("💾 Descargar CSV", df_final.to_csv(index=False).encode('utf-8'), f"FPD_{mes_siguiente}.csv", use_container_width=True)
        st.dataframe(df_final, use_container_width=True)