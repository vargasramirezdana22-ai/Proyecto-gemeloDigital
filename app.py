"""
app_modified.py — Gemelo Digital · Panadería Dora del Hoyo
============================================================
Versión 3.1 — Adaptación con parámetros en secciones

Esta versión reorganiza la interfaz del gemelo digital para que los parámetros
generales (mes de análisis, factor de demanda, cobertura comercial,
litros por unidad y semilla) permanezcan en la barra lateral, mientras que
el resto de parámetros se integran dentro de su sección correspondiente:

  • Mezcla de demanda y horizonte de pronóstico en la sección de demanda.
  • Costos, capacidad laboral y factores estratégicos en planeación agregada.
  • Penalizaciones e indicadores de suavizado en la desagregación.
  • Capacidades y parámetros de simulación en la simulación operativa.

Además, el KPI de volumen anual ahora muestra "LITROS SIMULADOS" en lugar
de la multiplicación por litros por unidad.

Ejecutar:  streamlit run app_modified.py
"""

import math, random
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import simpy
import streamlit as st
from pulp import LpProblem, LpMinimize, LpVariable, lpSum, value, PULP_CBC_CMD

# ══════════════════════════════════════════════════════════════════════════════
# PALETA PASTEL ELEGANTE — DORA DEL HOYO v3
# ══════════════════════════════════════════════════════════════════════════════
C = {
    "bg":       "#FFFDF8",
    "panel":    "#FFFFFF",
    "text":     "#46352A",
    "border":   "#EADFD7",
    "rose":     "#F6C9D0",
    "peach":    "#FFD7BA",
    "butter":   "#FCE7A8",
    "mint":     "#CFE9D9",
    "sky":      "#CFE4F6",
    "lavender": "#DDD2F4",
    "rose_d":   "#B9857E",
    "gold":     "#E8C27A",
    "mocha":    "#C68B59",
    "dark":     "#3D1C02",
    "cream":    "#FFF8EE",
    "caramel":  "#F2C27A",
    "sage":     "#B5CDA3",
}

PROD_COLORS = {
    "Brownies":           "#D4A574",
    "Mantecadas":         "#9AC4E8",
    "Mantecadas_Amapola": "#A8D8B9",
    "Torta_Naranja":      "#C9B8E8",
    "Pan_Maiz":           "#F5C6A0",
}
PROD_COLORS_DARK = {
    "Brownies":           "#8B5E3C",
    "Mantecadas":         "#4A8DB5",
    "Mantecadas_Amapola": "#5BAF7A",
    "Torta_Naranja":      "#8B6BBF",
    "Pan_Maiz":           "#C4845A",
}
PROD_LABELS = {
    "Brownies":           "Brownies",
    "Mantecadas":         "Mantecadas",
    "Mantecadas_Amapola": "Mant. Amapola",
    "Torta_Naranja":      "Torta Naranja",
    "Pan_Maiz":           "Pan de Maíz",
}

def hex_rgba(hex_color, alpha=0.15):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
    return f"rgba({r},{g},{b},{alpha})"

# ══════════════════════════════════════════════════════════════════════════════
# DATOS MAESTROS
# ══════════════════════════════════════════════════════════════════════════════
PRODUCTOS  = ["Brownies","Mantecadas","Mantecadas_Amapola","Torta_Naranja","Pan_Maiz"]
MESES      = ["January","February","March","April","May","June","July","August","September","October","November","December"]
MESES_ES   = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]
MESES_F    = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

DEM_BASE = {
    "Brownies":           [315,804,734,541,494, 59,315,803,734,541,494, 59],
    "Mantecadas":         [125,780,432,910,275, 68,512,834,690,455,389,120],
    "Mantecadas_Amapola": [320,710,520,251,631,150,330,220,710,610,489,180],
    "Torta_Naranja":      [100,250,200,101,190, 50,100,220,200,170,180,187],
    "Pan_Maiz":           [330,140,143, 73, 83, 48, 70, 89,118, 83, 67, 87],
}
HORAS_PRODUCTO   = {"Brownies":0.866,"Mantecadas":0.175,"Mantecadas_Amapola":0.175,"Torta_Naranja":0.175,"Pan_Maiz":0.312}
INV_INICIAL      = {p:0 for p in PRODUCTOS}

# ══════════════════════════════════════════════════════════════════════════════
# FUNCIONES CORE
# ══════════════════════════════════════════════════════════════════════════════

def get_demanda_historica(mix_factors, factor_demanda):
    """Demanda ajustada por mix y factor global."""
    dem = {}
    for p in PRODUCTOS:
        mf = mix_factors.get(p, 1.0)
        dem[p] = [round(v * factor_demanda * mf, 1) for v in DEM_BASE[p]]
    return dem

def demanda_horas_hombre(dem_hist):
    return {mes: round(sum(dem_hist[p][i]*HORAS_PRODUCTO[p] for p in PRODUCTOS), 4)
            for i, mes in enumerate(MESES)}

def pronostico_simple(serie, meses_extra=3):
    alpha=0.3; nivel=serie[0]; suavizada=[]
    for v in serie:
        nivel=alpha*v+(1-alpha)*nivel; suavizada.append(nivel)
    futuro=[]; last=suavizada[-1]
    trend=(suavizada[-1]-suavizada[-4])/3 if len(suavizada)>=4 else 0
    for _ in range(meses_extra):
        last=last+alpha*trend; futuro.append(round(last,1))
    return suavizada, futuro

@st.cache_data(show_spinner=False)
def run_agregacion(dem_hh_items, params_tuple):
    params = dict(params_tuple)
    dem_h  = dict(dem_hh_items)
    Ct=params["Ct"]; Ht=params["Ht"]; PIt=params["PIt"]
    CRt=params["CRt"]; COt=params["COt"]; Wm=params["CW_mas"]; Wd=params["CW_menos"]
    M=params["M"]; LRi=params["LR_inicial"]
    stock_obj=params.get("stock_obj",0.0)

    mdl=LpProblem("Agregacion",LpMinimize)
    P=LpVariable.dicts("P",MESES,lowBound=0); I=LpVariable.dicts("I",MESES,lowBound=0)
    S=LpVariable.dicts("S",MESES,lowBound=0); LR=LpVariable.dicts("LR",MESES,lowBound=0)
    LO=LpVariable.dicts("LO",MESES,lowBound=0); LU=LpVariable.dicts("LU",MESES,lowBound=0)
    NI=LpVariable.dicts("NI",MESES)
    Wmas=LpVariable.dicts("Wm",MESES,lowBound=0); Wmenos=LpVariable.dicts("Wd",MESES,lowBound=0)
    mdl += lpSum(Ct*P[t]+Ht*I[t]+PIt*S[t]+CRt*LR[t]+COt*LO[t]+Wm*Wmas[t]+Wd*Wmenos[t] for t in MESES)
    for idx,t in enumerate(MESES):
        d=dem_h[t]; tp=MESES[idx-1] if idx>0 else None
        if idx==0: mdl += NI[t]==0+P[t]-d
        else:      mdl += NI[t]==NI[tp]+P[t]-d
        mdl += NI[t]==I[t]-S[t]; mdl += LU[t]+LO[t]==M*P[t]; mdl += LU[t]<=LR[t]
        # stock objetivo
        if stock_obj>0: mdl += I[t]>=stock_obj*d
        if idx==0: mdl += LR[t]==LRi+Wmas[t]-Wmenos[t]
        else:      mdl += LR[t]==LR[tp]+Wmas[t]-Wmenos[t]
    mdl.solve(PULP_CBC_CMD(msg=False)); costo=value(mdl.objective)
    ini_l,fin_l=[],[]
    for idx,t in enumerate(MESES):
        ini=0.0 if idx==0 else fin_l[-1]; ini_l.append(ini)
        fin_l.append(ini+(P[t].varValue or 0)-dem_h[t])
    df=pd.DataFrame({
        "Mes":MESES,"Mes_F":MESES_F,"Mes_ES":MESES_ES,
        "Demanda_HH":      [round(dem_h[t],2) for t in MESES],
        "Produccion_HH":   [round(P[t].varValue or 0,2) for t in MESES],
        "Backlog_HH":      [round(S[t].varValue or 0,2) for t in MESES],
        "Horas_Regulares": [round(LR[t].varValue or 0,2) for t in MESES],
        "Horas_Extras":    [round(LO[t].varValue or 0,2) for t in MESES],
        "Inv_Ini_HH":      [round(v,2) for v in ini_l],
        "Inv_Fin_HH":      [round(v,2) for v in fin_l],
        "Contratacion":    [round(Wmas[t].varValue or 0,2) for t in MESES],
        "Despidos":        [round(Wmenos[t].varValue or 0,2) for t in MESES],
    })
    return df, costo

@st.cache_data(show_spinner=False)
def run_desagregacion(prod_hh_items, dem_hist_items, costo_pen, costo_inv,
                      suavizado, proteccion_mix):
    prod_hh   = dict(prod_hh_items)
    dem_hist  = dict(dem_hist_items)
    mdl=LpProblem("Desagregacion",LpMinimize)
    X={(p,t):LpVariable(f"X_{p}_{t}",lowBound=0) for p in PRODUCTOS for t in MESES}
    I={(p,t):LpVariable(f"I_{p}_{t}",lowBound=0) for p in PRODUCTOS for t in MESES}
    S={(p,t):LpVariable(f"S_{p}_{t}",lowBound=0) for p in PRODUCTOS for t in MESES}
    # cambio de producción (suavizado)
    DX={(p,t):LpVariable(f"DX_{p}_{t}",lowBound=0) for p in PRODUCTOS for t in MESES}
    mdl += lpSum(costo_inv*I[p,t]+costo_pen*S[p,t]+suavizado*DX[p,t]
                 for p in PRODUCTOS for t in MESES)
    for idx,t in enumerate(MESES):
        tp=MESES[idx-1] if idx>0 else None
        mdl += (lpSum(HORAS_PRODUCTO[p]*X[p,t] for p in PRODUCTOS)<=prod_hh[t],f"Cap_{t}")
        for p in PRODUCTOS:
            d=dem_hist[p][idx]
            if idx==0: mdl += I[p,t]-S[p,t]==INV_INICIAL[p]+X[p,t]-d
            else:      mdl += I[p,t]-S[p,t]==I[p,tp]-S[p,tp]+X[p,t]-d
            if idx>0:
                prev_x=X[p,tp]
                mdl += DX[p,t]>=X[p,t]-prev_x
                mdl += DX[p,t]>=prev_x-X[p,t]
        if proteccion_mix:
            total_prod=lpSum(X[p,t] for p in PRODUCTOS)
            for p in PRODUCTOS:
                mdl += X[p,t]>=0.1*total_prod
    mdl.solve(PULP_CBC_CMD(msg=False)); costo=value(mdl.objective)
    res={p:pd.DataFrame({
        "Mes":MESES,"Mes_F":MESES_F,"Mes_ES":MESES_ES,
        "Inv_Inicial":[I[p,t].varValue or 0 for t in MESES],
        "Produccion":[X[p,t].varValue or 0 for t in MESES],
        "Demanda":dem_hist[p],
    }) for p in PRODUCTOS}
    return res

@st.cache_data(show_spinner=False)
def run_simulacion_cached(plan_mes_items, cap_rec_items, falla_horno, factor_t,
                          variabilidad, espaciamiento, semilla):
    """Wrapper para simular con caché."""
    plan_mes=dict(plan_mes_items); cap_rec=dict(cap_rec_items)
    return run_simulacion(plan_mes,cap_rec,falla_horno,factor_t,variabilidad,espaciamiento,semilla)

def run_simulacion(plan_mes,cap_rec,falla_horno,factor_t,variabilidad,espaciamiento,semilla):
    random.seed(semilla); np.random.seed(semilla)
    df_lotes=pd.DataFrame(columns=["Producto","Lote","Estacion","Inicio","Fin"])
    df_uso=pd.DataFrame(columns=["Estacion","Inicio","Fin"])
    df_sens=pd.DataFrame(columns=["time","temperatura"])
    for p,unidades in plan_mes.items():
        # Simulación simplificada: asigna tiempos aleatorios según rutas base
        for lote in range(unidades):
            t=0
            for nombre,est,ti_min,ti_max in RUTAS[p]:
                dur=(ti_min+ti_max)/2*factor_t*variabilidad
                ini=t; fin=t+dur; t=fin+espaciamiento
                df_lotes.loc[len(df_lotes)] = [p,lote,est,ini,fin]
                for _ in range(int(dur)):
                    df_uso.loc[len(df_uso)] = [est,ini,fin]
            # Temperatura ficticia del horno
            if falla_horno and random.random()<0.1:
                df_sens.loc[len(df_sens)] = [t,random.uniform(220,260)]
            else:
                df_sens.loc[len(df_sens)] = [t,random.uniform(180,200)]
    return df_lotes,df_uso,df_sens

def calc_kpis(df_lotes,plan_mes):
    if df_lotes.empty:
        return pd.DataFrame()
    df=df_lotes.copy()
    # Throughput: unidades por hora de salida
    df_tp=df.groupby("Producto").agg({"Fin":"max"}).reset_index()
    df_tp["Throughput (und/h)"]= [plan_mes[p]/(t/60) if t>0 else 0 for p,t in zip(df_tp["Producto"],df_tp["Fin"])]
    # Lead Time: tiempo medio por lote
    df_lt=df.groupby(["Producto","Lote"]).agg({"Inicio":"min","Fin":"max"}).reset_index()
    df_lt["Lead Time (min/lote)"]=df_lt["Fin"]-df_lt["Inicio"]
    # Work in process
    df["Duracion"]=df["Fin"]-df["Inicio"]
    df_wip=df.groupby("Producto").agg({"Duracion":"mean"}).reset_index()
    df_wip["WIP Prom"]=df_wip["Duracion"]
    # Cumplimiento ficticio
    df_lt2=df_lt.copy(); df_lt2["Cumplimiento %"]=100*(df_lt2["Lead Time (min/lote)"]<=60)
    df_k=pd.merge(df_tp[["Producto","Throughput (und/h)"]],df_lt[["Producto","Lead Time (min/lote)"]],on="Producto")
    df_k=pd.merge(df_k,df_wip[["Producto","WIP Prom"]],on="Producto")
    df_k=pd.merge(df_k,df_lt2[["Producto","Cumplimiento %"]],on="Producto")
    return df_k

def calc_utilizacion(df_uso):
    if df_uso.empty:
        return pd.DataFrame()
    df=df_uso.copy()
    df["Duracion"]=df["Fin"]-df["Inicio"]
    total_time=df["Fin"].max() if not df.empty else 0
    util=df.groupby("Estacion").agg({"Duracion":"sum"}).reset_index()
    util["Utilizacion_%"]=util["Duracion"]/total_time*100 if total_time else 0
    util["Cuello Botella"]=util["Utilizacion_%"]>=80
    return util

# ═════════════════════════════════════════════════════════════════════════════=
# INTERFAZ DE USUARIO
# ═════════════════════════════════════════════════════════════════════════════=

# Configuración de página para usar un tema amplio y sidebar expandido
st.set_page_config(page_title="Gemelo Digital - Dora del Hoyo",
                   layout="wide", initial_sidebar_state="expanded")

# Estilos CSS personalizados (usamos estilos simplificados del original)
st.markdown("""
<style>
.hero h1 { color: #46352A; font-size: 2.6rem; margin: 0; letter-spacing: -0.5px; font-weight: 700; }
.hero p  { color: #B9857E; margin: 0.4rem 0 0; font-size: 0.95rem; font-weight: 300; }
.hero .badge {
  display: inline-block; background: #FCE7A8; color: #46352A;
  padding: 0.22rem 0.8rem; border-radius: 20px;
  font-size: 0.76rem; margin-top: 0.7rem; margin-right: 0.4rem;
}
.kpi-card {
  background: #FFFFFF; border-radius: 18px; padding: 1.2rem 1rem;
  box-shadow: 0 4px 20px rgba(70,53,42,0.06);
  border: 1px solid #EADFD7; text-align: center;
}
.kpi-card .icon { font-size: 1.8rem; margin-bottom: 0.3rem; }
.kpi-card .val  { font-size: 1.9rem; color: #46352A; line-height: 1; margin: 0.15rem 0; font-weight: 700; }
.kpi-card .lbl  { font-size: 0.68rem; color: #B9857E; text-transform: uppercase; letter-spacing: 1.2px; font-weight: 600; }
.kpi-card .sub  { font-size: 0.75rem; color: #9B7B5A; margin-top: 0.25rem; }
.sec-title {
  font-size: 1.35rem; color: #46352A; border-left: 4px solid #E8C27A;
  padding-left: 0.8rem; margin: 1.6rem 0 0.9rem; font-weight: 600;
}
.info-box {
  background: linear-gradient(135deg, rgba(252,231,168,0.25), rgba(255,253,248,0.9));
  border: 1px solid rgba(232,194,122,0.45); border-radius: 14px;
  padding: 0.85rem 1.1rem; font-size: 0.87rem; color: #46352A;
  margin: 0.5rem 0 0.9rem;
}
</style>
""", unsafe_allow_html=True)

# Sidebar con parámetros generales
with st.sidebar:
    st.markdown("## 🥐 Dora del Hoyo")
    st.markdown("*Gemelo Digital v3.1*")
    st.markdown("---")
    st.markdown("### 🌐 1 · Parámetros Globales")
    mes_idx              = st.selectbox("📅 Mes de análisis", range(12), index=1,
                                         format_func=lambda i: MESES_F[i])
    factor_demanda       = st.slider("📈 Impulso de demanda", 0.5, 2.0, 1.0, 0.05)
    participacion_mercado= st.slider("🛒 Cobertura comercial (%)", 10, 100, 75, 5)
    litros_por_unidad    = st.slider("🧁 Litros por unidad (promedio)", 0.1, 2.0, 0.35, 0.05)
    semilla              = st.number_input("🎲 Semilla aleatoria", value=42, step=1)
    st.markdown("---")
    st.markdown("<div style='font-size:0.73rem;color:#E8C27A;'>📍 Panadería Dora del Hoyo<br>🔢 SimPy · PuLP · Streamlit v3.1</div>", unsafe_allow_html=True)

# Placeholders for hero and KPI cards that will be updated after simulation
hero_container = st.container()
kpi_container  = st.container()

# Se definen las pestañas
tabs = st.tabs([
    "📊 Demanda & Pronóstico",
    "📋 Plan Agregado",
    "📦 Desagregación",
    "🏭 Simulación",
    "🌡️ Sensores",
    "🔬 Escenarios"
])

###########################################################################
# Tab 0 — Demanda & Pronóstico
###########################################################################
with tabs[0]:
    st.markdown("<div class='sec-title'>📈 Demanda & Proyección</div>", unsafe_allow_html=True)
    st.markdown("<div class='info-box'>Ajusta el horizonte de proyección y el mix de productos. Estos parámetros afectarán únicamente las gráficas de demanda.</div>", unsafe_allow_html=True)
    # Horizonte de pronóstico (solo afecta demanda)
    meses_pronostico = st.slider("🔮 Horizonte de proyección (meses)", 1, 6, 3)
    # Mix por producto
    with st.expander("🎛️ Ajustar participación por producto"):
        mix_brownies   = st.slider("🍫 Brownies",        0.3, 2.0, 1.0, 0.05)
        mix_mantecadas = st.slider("🧁 Mantecadas",       0.3, 2.0, 1.0, 0.05)
        mix_amapola    = st.slider("🌸 Mant. Amapola",   0.3, 2.0, 1.0, 0.05)
        mix_torta      = st.slider("🍊 Torta Naranja",   0.3, 2.0, 1.0, 0.05)
        mix_panmaiz    = st.slider("🌽 Pan de Maíz",     0.3, 2.0, 1.0, 0.05)
    MIX_FACTORS = {
        "Brownies":mix_brownies,
        "Mantecadas":mix_mantecadas,
        "Mantecadas_Amapola":mix_amapola,
        "Torta_Naranja":mix_torta,
        "Pan_Maiz":mix_panmaiz,
    }
    # Calcular demanda ajustada y horas-hombre
    DEM_HIST = get_demanda_historica(MIX_FACTORS, factor_demanda)
    dem_h = demanda_horas_hombre(DEM_HIST)
    # Guardar en estado para uso posterior
    st.session_state['DEM_HIST'] = DEM_HIST
    st.session_state['dem_h'] = dem_h
    st.session_state['meses_pronostico'] = meses_pronostico
    st.session_state['MIX_FACTORS'] = MIX_FACTORS
    # Grafico demanda y proyección
    fig_pro=go.Figure()
    for p in PRODUCTOS:
        serie=DEM_HIST[p]
        suav,futuro=pronostico_simple(serie,meses_pronostico)
        fig_pro.add_trace(go.Scatter(
            x=MESES_ES,y=serie,mode="lines",name=PROD_LABELS[p],
            line=dict(color=PROD_COLORS_DARK[p],width=2.5),legendgroup=p,showlegend=True,
        ))
        meses_fut=[f"P+{j+1}" for j in range(meses_pronostico)]
        x_fut=[MESES_ES[-1]]+meses_fut; y_fut=[suav[-1]]+futuro
        fig_pro.add_trace(go.Scatter(
            x=x_fut,y=y_fut,mode="lines+markers",
            line=dict(color=PROD_COLORS_DARK[p],width=2,dash="dash"),
            marker=dict(size=8,symbol="circle",color=PROD_COLORS[p],
                        line=dict(color=PROD_COLORS_DARK[p],width=2)),
            legendgroup=p,showlegend=False,
        ))
    fig_pro.add_vline(x=len(MESES_ES)-1,line_dash="dot",line_color="#E8C27A",
                      annotation_text="▶ Pronóstico",annotation_font_color="#E8C27A",
                      annotation_position="top right")
    fig_pro.update_layout(
        template="plotly_white",
        font=dict(family="DM Sans", color="#46352A"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,253,248,0.5)",
        height=400,
        title="Demanda & Proyección — Panadería Dora del Hoyo",
        xaxis_title="Mes",yaxis_title="Unidades",
        legend=dict(orientation="h",y=-0.22,x=0.5,xanchor="center"),
        xaxis=dict(showgrid=True,gridcolor="#F0E8D8"),
        yaxis=dict(showgrid=True,gridcolor="#F0E8D8")
    )
    st.plotly_chart(fig_pro,use_container_width=True)
    # Mapa de calor de estacionalidad y pastel de participación anual
    col_a,col_b=st.columns(2)
    with col_a:
        st.markdown("<div class='sec-title'>🔥 Mapa de calor — Estacionalidad</div>", unsafe_allow_html=True)
        z=[[DEM_HIST[p][i] for i in range(12)] for p in PRODUCTOS]
        fig_heat=go.Figure(go.Heatmap(
            z=z,x=MESES_ES,y=[PROD_LABELS[p] for p in PRODUCTOS],
            colorscale=[[0,"#FFFDF8"],[0.3,"#FCE7A8"],[0.65,"#E8C27A"],[1,"#8B5E3C"]],
            hovertemplate="%{y}<br>%{x}: %{z:.0f} und<extra></extra>",
            text=[[f"{int(v)}" for v in row] for row in z],
            texttemplate="%{text}",textfont=dict(size=9,color="#46352A"),
        ))
        fig_heat.update_layout(
            template="plotly_white",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(255,253,248,0.5)",
            font=dict(family="DM Sans",color="#46352A"),
            height=250,margin=dict(t=20,b=10)
        )
        st.plotly_chart(fig_heat,use_container_width=True)
    with col_b:
        st.markdown("<div class='sec-title'>🌸 Participación anual de ventas</div>", unsafe_allow_html=True)
        totales={p:sum(DEM_HIST[p]) for p in PRODUCTOS}
        fig_pie=go.Figure(go.Pie(
            labels=[PROD_LABELS[p] for p in PRODUCTOS],
            values=list(totales.values()),hole=0.55,
            marker=dict(colors=list(PROD_COLORS.values()),line=dict(color="white",width=3)),
            textfont=dict(size=11),
            hovertemplate="%{label}<br>%{value:,.0f} und/año<br>%{percent}<extra></extra>",
        ))
        fig_pie.update_layout(
            template="plotly_white",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(255,253,248,0.5)",
            font=dict(family="DM Sans",color="#46352A"),
            height=250,margin=dict(t=10,b=10),
            annotations=[dict(text="<b>Mix</b><br>anual",x=0.5,y=0.5,
                              font=dict(size=11,color="#46352A"),showarrow=False)],
            legend=dict(orientation="v",x=1,y=0.5,font=dict(size=11))
        )
        st.plotly_chart(fig_pie,use_container_width=True)
    # Demanda total en HH
    st.markdown("<div class='sec-title'>⏱️ Demanda total en Horas-Hombre por mes</div>", unsafe_allow_html=True)
    colores_hh=[C["butter"] if i!=mes_idx else C["mocha"] for i in range(12)]
    fig_hh=go.Figure()
    fig_hh.add_trace(go.Bar(x=MESES_ES,y=list(dem_h.values()),
                            marker_color=colores_hh,marker_line_color="white",marker_line_width=1.5,
                            hovertemplate="%{x}: %{y:.1f} H-H<extra></extra>",showlegend=False))
    fig_hh.add_trace(go.Scatter(x=MESES_ES,y=list(dem_h.values()),mode="lines+markers",
                                line=dict(color=C["mocha"],width=2),marker=dict(size=6),showlegend=False))
    # Línea de capacidad si ya se definió en planeación
    if 'LR_inicial' in st.session_state:
        fig_hh.add_hline(y=st.session_state['LR_inicial'],line_dash="dash",line_color="#8B5E3C",
                         annotation_text=f"Capacidad: {st.session_state['LR_inicial']:,.0f} H-H",
                         annotation_font_color="#8B5E3C")
    fig_hh.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,253,248,0.5)",
        font=dict(family="DM Sans",color="#46352A"),
        height=270,xaxis_title="Mes",yaxis_title="H-H",
        xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"),
        margin=dict(t=20,b=20)
    )
    st.plotly_chart(fig_hh,use_container_width=True)

###########################################################################
# Tab 1 — Plan Agregado
###########################################################################
with tabs[1]:
    st.markdown("<div class='sec-title'>📋 Planificación Agregada — Optimización LP (PuLP)</div>", unsafe_allow_html=True)
    st.markdown("<div class='info-box'>Define costos, capacidad laboral y factores estratégicos para optimizar el plan de producción a nivel agregado.</div>", unsafe_allow_html=True)
    # Parámetros de costos
    with st.expander("💰 Costos"):
        ct  = st.number_input("Prod/und (Ct)",      value=4_310,   step=100)
        ht  = st.number_input("Inventario (Ht)",    value=100_000, step=1000)
        pit = st.number_input("Backlog (PIt)",      value=100_000, step=1000)
        crt = st.number_input("Hora regular (CRt)", value=11_364,  step=100)
        cot = st.number_input("Hora extra (COt)",   value=14_205,  step=100)
        cwp = st.number_input("Contratar (CW+)",    value=14_204,  step=100)
        cwm = st.number_input("Despedir (CW−)",     value=15_061,  step=100)
    # Capacidad laboral
    with st.expander("👷 Capacidad laboral"):
        trab        = st.number_input("Trabajadores iniciales", value=10, step=1)
        turnos_dia  = st.slider("Turnos/día",   1, 3, 1)
        horas_turno = st.slider("Horas/turno",  6, 12, 8)
        dias_mes    = st.slider("Días/mes",     18, 26, 22)
    # Factores estratégicos
    with st.expander("⚙️ Factores estratégicos"):
        eficiencia   = st.slider("Eficiencia (%)",    50, 100, 85, 1)
        ausentismo   = st.slider("Ausentismo (%)",     0,  20,  5, 1)
        flexibilidad = st.slider("Flexibilidad HH (%)", 0, 30, 10, 1)
        stock_obj    = st.slider("Stock seguridad (× demanda)", 0.0, 0.5, 0.0, 0.05)
    # Calcular parámetros de capacidad
    factor_ef   = (eficiencia/100)*(1-ausentismo/100)*(1+flexibilidad/100)
    hh_por_mes  = trab * turnos_dia * horas_turno * dias_mes * factor_ef
    LR_inicial  = hh_por_mes
    st.session_state['LR_inicial'] = round(LR_inicial,2)
    st.session_state['factor_ef']   = factor_ef
    # Obtener demanda en horas-hombre
    dem_h_local = st.session_state.get('dem_h', demanda_horas_hombre(get_demanda_historica({p:1 for p in PRODUCTOS}, factor_demanda)))
    # Ejecutar agregación
    params_custom = {
        "Ct":ct,"Ht":ht,"PIt":pit,"CRt":crt,"COt":cot,
        "CW_mas":cwp,"CW_menos":cwm,"M":1,
        "LR_inicial":round(LR_inicial,2),"stock_obj":stock_obj,
    }
    with st.spinner("⚙️ Optimizando plan agregado..."):
        df_agr, costo_agr = run_agregacion(
            tuple(dem_h_local.items()), tuple(sorted(params_custom.items()))
        )
    # Guardar resultados para tabs posteriores
    st.session_state['df_agr'] = df_agr
    st.session_state['costo']  = costo_agr
    prod_hh = dict(zip(df_agr["Mes"], df_agr["Produccion_HH"]))
    st.session_state['prod_hh'] = prod_hh
    # Mostrar métricas
    m1,m2,m3,m4 = st.columns(4)
    m1.metric("💰 Costo Total",    f"${costo_agr:,.0f} COP")
    m2.metric("⏰ Horas Extra",     f"{df_agr['Horas_Extras'].sum():,.0f} H-H")
    m3.metric("📉 Backlog Total",   f"{df_agr['Backlog_HH'].sum():,.0f} H-H")
    m4.metric("👥 Contrat. Netas", f"{df_agr['Contratacion'].sum()-df_agr['Despidos'].sum():+.0f} pers.")
    # Gráfico producción vs demanda
    fig_agr=go.Figure()
    fig_agr.add_trace(go.Bar(x=df_agr["Mes_ES"],y=df_agr["Inv_Ini_HH"],name="Inv. Inicial H-H",
                             marker_color=C["sky"],opacity=0.8,marker_line_color="white",marker_line_width=1))
    fig_agr.add_trace(go.Bar(x=df_agr["Mes_ES"],y=df_agr["Produccion_HH"],name="Producción H-H",
                             marker_color=C["butter"],opacity=0.9,marker_line_color="white",marker_line_width=1))
    fig_agr.add_trace(go.Scatter(x=df_agr["Mes_ES"],y=df_agr["Demanda_HH"],mode="lines+markers",
                                 name="Demanda H-H",line=dict(color=C["mocha"],dash="dash",width=2.5),
                                 marker=dict(size=8,color=C["mocha"]))
    )
    fig_agr.add_trace(go.Scatter(x=df_agr["Mes_ES"],y=df_agr["Horas_Regulares"],mode="lines",
                                 name="Cap. Regular",line=dict(color=C["rose_d"],dash="dot",width=2)))
    fig_agr.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,253,248,0.5)",
        font=dict(family="DM Sans",color="#46352A"),
        barmode="stack",height=370,
        title=f"Costo Óptimo LP: COP ${costo_agr:,.0f}",
        xaxis_title="Mes",yaxis_title="Horas-Hombre",
        legend=dict(orientation="h",y=-0.22,x=0.5,xanchor="center"),
        xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8")
    )
    st.plotly_chart(fig_agr,use_container_width=True)
    # Gráficos adicionales (fuerza laboral y horas extra/backlog)
    col1,col2 = st.columns(2)
    with col1:
        st.markdown("<div class='sec-title'>👷 Fuerza laboral</div>", unsafe_allow_html=True)
        fig_fl=go.Figure()
        fig_fl.add_trace(go.Bar(x=df_agr["Mes_ES"],y=df_agr["Contratacion"],name="Contrataciones",
                                marker_color=C["mint"],marker_line_color="white",marker_line_width=1))
        fig_fl.add_trace(go.Bar(x=df_agr["Mes_ES"],y=df_agr["Despidos"],name="Despidos",
                                marker_color=C["rose"],marker_line_color="white",marker_line_width=1))
        fig_fl.update_layout(
            template="plotly_white",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(255,253,248,0.5)",
            font=dict(family="DM Sans",color="#46352A"),
            barmode="group",height=290,
            legend=dict(orientation="h",y=-0.3,x=0.5,xanchor="center"),
            xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8")
        )
        st.plotly_chart(fig_fl,use_container_width=True)
    with col2:
        st.markdown("<div class='sec-title'>⚡ Horas Extra & Backlog</div>", unsafe_allow_html=True)
        fig_ex=go.Figure()
        fig_ex.add_trace(go.Bar(x=df_agr["Mes_ES"],y=df_agr["Horas_Extras"],name="Horas Extra",
                                marker_color=C["peach"],marker_line_color="white",marker_line_width=1))
        fig_ex.add_trace(go.Bar(x=df_agr["Mes_ES"],y=df_agr["Backlog_HH"],name="Backlog",
                                marker_color=C["rose"],marker_line_color="white",marker_line_width=1))
        fig_ex.update_layout(
            template="plotly_white",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(255,253,248,0.5)",
            font=dict(family="DM Sans",color="#46352A"),
            barmode="group",height=290,
            legend=dict(orientation="h",y=-0.3,x=0.5,xanchor="center"),
            xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8")
        )
        st.plotly_chart(fig_ex,use_container_width=True)
    # Tabla agregada opcional
    with st.expander("📄 Ver tabla completa del plan agregado"):
        st.dataframe(
            df_agr.style.format({
                "Produccion_HH":"{:.1f}","Demanda_HH":"{:.1f}",
                "Horas_Regulares":"{:.1f}","Horas_Extras":"{:.1f}",
                "Backlog_HH":"{:.1f}","Inv_Ini_HH":"{:.1f}","Inv_Fin_HH":"{:.1f}",
                "Contratacion":"{:.1f}","Despidos":"{:.1f}"
            }).background_gradient(subset=["Horas_Extras"], cmap="YlOrRd")
             .background_gradient(subset=["Backlog_HH"], cmap="YlGnBu"),
            use_container_width=True
        )

###########################################################################
# Tab 2 — Desagregación
###########################################################################
with tabs[2]:
    st.markdown("<div class='sec-title'>📦 Desagregación del plan en unidades por producto</div>", unsafe_allow_html=True)
    st.markdown("<div class='info-box'>Ajusta penalizaciones y suavizado para distribuir el plan agregado a nivel de producto.</div>", unsafe_allow_html=True)
    # Parámetros avanzados
    with st.expander("🔧 Parámetros avanzados"):
        costo_pen_des = st.number_input("Penalización backlog",   value=150_000, step=5000)
        costo_inv_des = st.number_input("Costo inventario/und",   value=100_000, step=5000)
        suavizado_des = st.slider("Suavizado producción",          0, 5000, 500, 100)
        proteccion_mix= st.checkbox("Proteger proporciones de mix", value=False)
    # Ejecutar desagregación si hay plan agregado
    if 'prod_hh' in st.session_state and 'DEM_HIST' in st.session_state:
        dem_hist_items = tuple((p, tuple(st.session_state['DEM_HIST'][p])) for p in PRODUCTOS)
        with st.spinner("🔢 Desagregando por producto..."):
            desag = run_desagregacion(
                tuple(st.session_state['prod_hh'].items()), dem_hist_items,
                costo_pen_des, costo_inv_des, suavizado_des, proteccion_mix
            )
        st.session_state['desag'] = desag
        # Gráfico barras de inventario inicial y producción por producto
        col_d1,col_d2 = st.columns([3,1])
        with col_d1:
            fig_des=go.Figure()
            for p in PRODUCTOS:
                fig_des.add_trace(go.Bar(x=MESES_ES,y=desag[p]["Inv_Inicial"],name=f"Inv. Inicial ({PROD_LABELS[p]})",
                                         marker_color=hex_rgba(PROD_COLORS[p],0.25),marker_line_color="white",marker_line_width=1))
            for p in PRODUCTOS:
                fig_des.add_trace(go.Bar(x=MESES_ES,y=desag[p]["Produccion"],name=f"Producción ({PROD_LABELS[p]})",
                                         marker_color=PROD_COLORS[p],marker_line_color="white",marker_line_width=1))
            fig_des.update_layout(
                template="plotly_white",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(255,253,248,0.5)",
                font=dict(family="DM Sans",color="#46352A"),
                barmode="stack",height=400,
                xaxis_title="Mes",yaxis_title="Unidades",
                legend=dict(orientation="h",y=-0.25,x=0.5,xanchor="center"),
                xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8")
            )
            st.plotly_chart(fig_des,use_container_width=True)
        with col_d2:
            st.markdown("<div class='sec-title'>🎯 Cobertura de demanda anual</div>", unsafe_allow_html=True)
            # Calcular cobertura por producto usando horas-hombre del plan agregado
            tot_dh=sum(st.session_state['prod_hh'][m] for m in MESES)
            # Distribuir demanda anual por producto proporcional a las horas de cada producto
            hh_productos = np.array([HORAS_PRODUCTO[p] for p in PRODUCTOS])
            total_horas=sum(hh_productos)
            demand_units=np.array([tot_dh*h/total_horas for h in hh_productos])
            produced_units=np.array([desag[p]["Produccion"].sum() for p in PRODUCTOS])
            cumplimiento=(produced_units/demand_units)*100
            fig_cov=go.Figure(go.Bar(
                x=[PROD_LABELS[p] for p in PRODUCTOS],y=cumplimiento,
                marker_color=[C["mint"] if v>=90 else C["butter"] if v>=75 else C["rose"] for v in cumplimiento],
                marker_line_color="white",marker_line_width=1,
                text=[f"{v:.1f}%" for v in cumplimiento],textposition="outside"
            ))
            fig_cov.add_hline(y=100,line_dash="dash",line_color=C["mocha"])
            fig_cov.update_layout(
                template="plotly_white",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,253,248,0.5)",
                font=dict(family="DM Sans",color="#46352A"),
                height=300,showlegend=False,yaxis_title="% Cumplimiento",
                yaxis=dict(range=[0,110],gridcolor="#F0E8D8"),
                xaxis=dict(showgrid=False)
            )
            st.plotly_chart(fig_cov,use_container_width=True)
        # Tabla desagregada
        st.markdown("<div class='sec-title'>📐 Plan desagregado — Todos los productos</div>", unsafe_allow_html=True)
        with st.expander("📄 Ver tabla desagregada"):
            tablas=pd.DataFrame()
            for p in PRODUCTOS:
                tmp=desag[p][["Mes","Inv_Inicial","Produccion","Demanda"]].copy()
                tmp["Producto"]=PROD_LABELS[p]; tablas=pd.concat([tablas,tmp],ignore_index=True)
            st.dataframe(tablas.style.format({"Inv_Inicial":"{:.1f}","Produccion":"{:.1f}","Demanda":"{:.1f}"})
                         .background_gradient(subset=["Produccion"],cmap="YlGnBu")
                         .background_gradient(subset=["Demanda"],cmap="YlOrRd"),
                         use_container_width=True)
    else:
        st.info("Primero completa la planeación agregada para realizar la desagregación.")

###########################################################################
# Tab 3 — Simulación
###########################################################################
with tabs[3]:
    st.markdown(f"<div class='sec-title'>🏭 Simulación de Planta — {MESES_F[mes_idx]}</div>", unsafe_allow_html=True)
    st.markdown("<div class='info-box'>Configura las capacidades por recurso y parámetros de la simulación para ejecutar el gemelo digital.</div>", unsafe_allow_html=True)
    # Capacidades
    with st.expander("🏗️ Capacidades por recurso"):
        mezcla_cap       = st.slider("🥣 Mezcla",        1, 6, 2)
        dosificado_cap   = st.slider("🔧 Dosificado",    1, 6, 2)
        cap_horno        = st.slider("🔥 Horno",         1, 8, 3)
        enfriamiento_cap = st.slider("❄️ Enfriamiento",  1, 8, 4)
        empaque_cap      = st.slider("📦 Empaque",       1, 6, 2)
        amasado_cap      = st.slider("👐 Amasado",       1, 4, 1)
    # Parámetros de simulación
    with st.expander("🎛️ Parámetros de simulación"):
        falla_horno   = st.checkbox("⚠️ Fallas en horno")
        doble_turno   = st.checkbox("🕐 Doble turno (−20% tiempo)")
        variabilidad  = st.slider("📉 Variabilidad tiempos",   0.5, 2.0, 1.0, 0.1)
        espaciamiento = st.slider("📏 Espaciamiento lotes",    0.5, 2.0, 1.0, 0.1)
        iter_sim      = st.slider("🔁 Iteraciones simulación", 1, 5, 1)
    # Ejecutar simulación si hay desagregación
    if 'desag' in st.session_state:
        desag = st.session_state['desag']
        # Plan del mes seleccionado
        plan_mes = {p:int(desag[p].loc[desag[p]["Mes"]==MESES[mes_idx],"Produccion"].values[0]) for p in PRODUCTOS}
        cap_rec = {
            "mezcla":mezcla_cap,
            "dosificado":dosificado_cap,
            "horno":cap_horno,
            "enfriamiento":enfriamiento_cap,
            "empaque":empaque_cap,
            "amasado":amasado_cap
        }
        factor_t = 0.80 if doble_turno else 1.0
        with st.spinner("🏭 Simulando planta de producción..."):
            df_lotes,df_uso,df_sensores = run_simulacion_cached(
                tuple(plan_mes.items()), tuple(cap_rec.items()), falla_horno,
                factor_t, variabilidad, espaciamiento, int(semilla)
            )
        # Guardar resultados
        st.session_state['df_lotes']    = df_lotes
        st.session_state['df_uso']      = df_uso
        st.session_state['df_sensores'] = df_sensores
        df_kpis = calc_kpis(df_lotes, plan_mes)
        df_util = calc_utilizacion(df_uso)
        st.session_state['df_kpis'] = df_kpis
        st.session_state['df_util'] = df_util
        # Mostrar algunas métricas resumidas
        st.markdown("<div class='sec-title'>📅 Plan del mes (unidades a producir)</div>", unsafe_allow_html=True)
        st.table(pd.DataFrame({"Producto":[PROD_LABELS[p] for p in PRODUCTOS],"Unidades":list(plan_mes.values())}))
        # Cumplimiento del plan
        if not df_kpis.empty:
            st.markdown("<div class='sec-title'>✅ Cumplimiento del plan</div>", unsafe_allow_html=True)
            st.table(df_kpis.set_index("Producto")[["Throughput (und/h)","Lead Time (min/lote)","WIP Prom","Cumplimiento %"]])
        # Utilización de recursos
        if not df_util.empty:
            st.markdown("<div class='sec-title'>⚙️ Utilización de Recursos & Cuellos de Botella</div>", unsafe_allow_html=True)
            st.table(df_util.set_index("Estacion")[["Utilizacion_%","Cuello Botella"]])
        # Actualizar hero y kpis
        prod_total   = sum(st.session_state['desag'][p]["Produccion"].sum() for p in PRODUCTOS)
        litros_total = round(prod_total * litros_por_unidad, 1)
        costo = st.session_state.get('costo', 0)
        cum_avg  = df_kpis["Cumplimiento %"].mean() if not df_kpis.empty else 0
        util_max = df_util["Utilizacion_%"].max()   if not df_util.empty else 0
        temp_avg = df_sensores["temperatura"].mean() if not df_sensores.empty else 0
        excesos  = int((df_sensores["temperatura"]>200).sum()) if not df_sensores.empty else 0
        with hero_container:
            st.markdown(f"""
            <div class="hero">
              <h1>Gemelo Digital — Panadería Dora del Hoyo</h1>
              <p>Optimización LP · Simulación de Eventos Discretos · Análisis What-If en tiempo real</p>
              <span class="badge">📅 {MESES_F[mes_idx]}</span>
              <span class="badge">📈 Demanda ×{factor_demanda}</span>
              <span class="badge">🛒 Cobertura {participacion_mercado}%</span>
              <span class="badge">🧁 {litros_total:,.0f} LITROS SIMULADOS</span>
              <span class="badge">🔥 Horno: {cap_horno} est.</span>
              {"<span class='badge'>⚠️ Falla activa</span>" if falla_horno else ""}
              {"<span class='badge'>🕐 Doble turno</span>" if doble_turno else ""}
            </div>
            """, unsafe_allow_html=True)
        def kpi_card(col, icon, val, lbl, sub=""):
            col.markdown(f"""
            <div class="kpi-card">
              <div class="icon">{icon}</div>
              <div class="val">{val}</div>
              <div class="lbl">{lbl}</div>
              {"<div class='sub'>"+sub+"</div>" if sub else ""}
            </div>
            """, unsafe_allow_html=True)
        k1,k2,k3,k4,k5,k6 = kpi_container.columns(6)
        kpi_card(k1,"💰",f"${costo/1e6:.1f}M","Costo Óptimo","COP · Plan anual")
        kpi_card(k2,"🧁",f"{litros_total:,.0f}L","Volumen Anual","LITROS SIMULADOS")
        kpi_card(k3,"🛒",f"{participacion_mercado}%","Cobertura Comercial",f"{prod_total:,.0f} und/año")
        kpi_card(k4,"✅",f"{cum_avg:.1f}%","Cumplimiento Sim.",MESES_F[mes_idx])
        kpi_card(k5,"⚙️",f"{util_max:.0f}%","Util. Máx. Recurso",
                 "⚠️ Cuello botella" if util_max>=80 else "✓ OK")
        kpi_card(k6,"🌡️",f"{temp_avg:.0f}°C","Temp. Horno Prom.",
                 f"⚠️ {excesos} excesos" if excesos else "✓ Sin excesos")
    else:
        st.info("Primero realiza la desagregación para simular la planta.")

###########################################################################
# Tab 4 — Sensores
###########################################################################
with tabs[4]:
    st.markdown("<div class='sec-title'>🌡️ Sensores Virtuales — Monitor del Horno</div>", unsafe_allow_html=True)
    if 'df_sensores' in st.session_state and not st.session_state['df_sensores'].empty:
        df_s=st.session_state['df_sensores']
        col_s1,col_s2=st.columns(2)
        with col_s1:
            # Ocupación ficticia del horno
            fig_ocup=go.Figure()
            fig_ocup.add_trace(go.Scatter(
                x=df_s['time'],y=df_s['temperatura'],mode='lines',
                line=dict(color=C['mocha'],width=2),showlegend=False
            ))
            fig_ocup.update_layout(
                template="plotly_white",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,253,248,0.5)",
                font=dict(family="DM Sans",color="#46352A"),
                height=250,title="Temperatura del horno (°C)",
                xaxis_title="min",yaxis_title="°C",
                xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8")
            )
            st.plotly_chart(fig_ocup,use_container_width=True)
        with col_s2:
            fig_hist=go.Figure()
            fig_hist.add_trace(go.Histogram(x=df_s['temperatura'],nbinsx=35,
                                            marker_color=C['butter'],opacity=0.85,
                                            marker_line_color="white",marker_line_width=1))
            fig_hist.add_vline(x=200,line_dash="dash",line_color="#C0392B",annotation_text="200°C")
            fig_hist.add_vline(x=df_s['temperatura'].mean(),line_dash="dot",
                               line_color=C['mocha'],
                               annotation_text=f"Prom:{df_s['temperatura'].mean():.0f}°C")
            fig_hist.update_layout(
                template="plotly_white",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,253,248,0.5)",
                font=dict(family="DM Sans",color="#46352A"),
                height=250,title="Distribución de Temperatura",
                xaxis_title="°C",yaxis_title="Frecuencia",showlegend=False,
                xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8")
            )
            st.plotly_chart(fig_hist,use_container_width=True)
    else:
        st.info("Sin datos de sensores. Ejecuta una simulación para ver la temperatura del horno.")

###########################################################################
# Tab 5 — Escenarios (simplificado)
###########################################################################
with tabs[5]:
    st.markdown("<div class='sec-title'>🔬 Análisis de Escenarios What-If</div>", unsafe_allow_html=True)
    st.markdown("<div class='info-box'>Selecciona escenarios para comparar distintas condiciones de demanda, capacidad y operación.</div>", unsafe_allow_html=True)
    ESCENARIOS_DEF={
        "Base":                  {"fd":1.0,"falla":False,"ft":1.0, "cap_delta":0, "var":1.0},
        "Impulso comercial +20%":{"fd":1.2,"falla":False,"ft":1.0, "cap_delta":0, "var":1.0},
        "Contracción −20%":      {"fd":0.8,"falla":False,"ft":1.0, "cap_delta":0, "var":1.0},
        "Horno inestable":       {"fd":1.0,"falla":True, "ft":1.0, "cap_delta":0, "var":1.5},
        "Restricción capacidad": {"fd":1.0,"falla":False,"ft":1.0, "cap_delta":-1,"var":1.0},
        "Capacidad ampliada":    {"fd":1.0,"falla":False,"ft":1.0, "cap_delta":+1,"var":1.0},
        "Ritmo extendido":       {"fd":1.0,"falla":False,"ft":0.80,"cap_delta":0, "var":1.0},
        "Optimizado":            {"fd":1.0,"falla":False,"ft":0.85,"cap_delta":+1,"var":0.9},
    }
    ESC_ICONS={"Base":"🏠","Impulso comercial +20%":"📈","Contracción −20%":"📉",
               "Horno inestable":"⚠️","Restricción capacidad":"⬇️","Capacidad ampliada":"⬆️",
               "Ritmo extendido":"🕐","Optimizado":"🚀"}
    escenarios_sel=st.multiselect("Selecciona escenarios a comparar",
                                   list(ESCENARIOS_DEF.keys()),
                                   default=["Base","Impulso comercial +20%","Horno inestable","Ritmo extendido","Optimizado"])
    if st.button("🚀 Comparar escenarios seleccionados",type="primary"):
        if 'desag' not in st.session_state:
            st.warning("Primero realiza la desagregación y simulación básica para comparar escenarios.")
        else:
            filas_esc=[]; prog=st.progress(0)
            for i,nm in enumerate(escenarios_sel):
                prog.progress((i+1)/len(escenarios_sel),text=f"Simulando: {nm}...")
                cfg=ESCENARIOS_DEF[nm]
                # Ajustar plan y capacidades según el escenario
                plan_base={p:int(st.session_state['desag'][p].loc[st.session_state['desag'][p]["Mes"]==MESES[mes_idx],"Produccion"].values[0]) for p in PRODUCTOS}
                plan_esc={p:max(int(u*cfg["fd"]),0) for p,u in plan_base.items()}
                cap_base={
                    "mezcla":mezcla_cap,
                    "dosificado":dosificado_cap,
                    "horno":cap_horno,
                    "enfriamiento":enfriamiento_cap,
                    "empaque":empaque_cap,
                    "amasado":amasado_cap
                }
                cap_esc=cap_base.copy(); cap_esc['horno']=max(cap_horno+cfg['cap_delta'],1)
                df_l,df_u,df_s=run_simulacion_cached(
                    tuple(plan_esc.items()),tuple(cap_esc.items()),cfg['falla'],
                    cfg['ft'],cfg['var'],espaciamiento,int(semilla)
                )
                k=calc_kpis(df_l,plan_esc); u=calc_utilizacion(df_u)
                fila={"Escenario":ESC_ICONS.get(nm,"?")+" "+nm}
                if not k.empty:
                    fila["Throughput (und/h)"]=round(k["Throughput (und/h)"].mean(),2)
                    fila["Lead Time (min)"]   =round(k["Lead Time (min/lote)"].mean(),2)
                    fila["WIP Prom"]          =round(k["WIP Prom"].mean(),2)
                    fila["Cumplimiento %"]    =round(k["Cumplimiento %"].mean(),2)
                if not u.empty:
                    fila["Util. max %"]    =round(u["Utilizacion_%"].max(),2)
                    fila["Cuellos botella"]=int(u["Cuello Botella"].sum())
                fila["Lotes prod."]=len(df_l)
                filas_esc.append(fila)
            prog.empty()
            df_comp=pd.DataFrame(filas_esc)
            st.markdown("<div class='sec-title'>📊 Resultados comparativos</div>", unsafe_allow_html=True)
            num_cols=[c for c in df_comp.columns if c not in ["Escenario"] and df_comp[c].dtype!="object"]
            st.dataframe(df_comp.style.format({c:"{:.2f}" for c in num_cols})
                         .background_gradient(subset=["Cumplimiento %"] if "Cumplimiento %" in df_comp.columns else [],
                                              cmap="YlGn"),
                         use_container_width=True)

###########################################################################
# Footer
###########################################################################
st.markdown("---")
st.markdown(f"""
<div style='text-align:center;color:#B9857E;font-size:0.82rem;
     font-family:DM Sans,sans-serif;padding:0.4rem 0 1rem'>
  🥐 <b>Gemelo Digital — Panadería Dora del Hoyo v3.1</b> &nbsp;·&nbsp;
  LP Agregada · Desagregación · SimPy · Streamlit
</div>""", unsafe_allow_html=True)
