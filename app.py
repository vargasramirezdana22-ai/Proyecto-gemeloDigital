"""
app.py  —  Gemelo Digital · Panadería Dora del Hoyo
====================================================
Versión 2.0 — Rediseño completo con:
  • Paleta pastel artesanal
  • Pronóstico de demanda con proyección futura
  • Parámetros enriquecidos en agregación y simulación
  • Gráficas WOW: violin, radar, histograma, sunburst
  • KPIs visuales mejorados

Ejecutar:  streamlit run app.py
"""

import math, random
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import simpy
import streamlit as st
from pulp import LpProblem, LpMinimize, LpVariable, lpSum, value, PULP_CBC_CMD

# ══════════════════════════════════════════════════════════════════════════════
# PALETA PASTEL DORA DEL HOYO
# ══════════════════════════════════════════════════════════════════════════════
C = {
    "cream":   "#FFF8EE",
    "caramel": "#F2C27A",
    "mocha":   "#C68B59",
    "dark":    "#3D1C02",
    "rose":    "#F4A7B9",
    "mint":    "#A8D8B9",
    "sky":     "#A8D1F0",
    "lavender":"#C9B8E8",
    "peach":   "#FFB7A0",
    "butter":  "#F9E4A0",
    "sage":    "#B5CDA3",
}

PROD_COLORS = {
    "Brownies":           "#F2C27A",
    "Mantecadas":         "#A8D1F0",
    "Mantecadas_Amapola": "#A8D8B9",
    "Torta_Naranja":      "#C9B8E8",
    "Pan_Maiz":           "#FFB7A0",
}
PROD_COLORS_DARK = {
    "Brownies":           "#C68B3A",
    "Mantecadas":         "#4A90C4",
    "Mantecadas_Amapola": "#5BAF7A",
    "Torta_Naranja":      "#8B6BBF",
    "Pan_Maiz":           "#E07050",
}
PROD_LABELS = {
    "Brownies":"Brownies","Mantecadas":"Mantecadas",
    "Mantecadas_Amapola":"Mant. Amapola","Torta_Naranja":"Torta Naranja","Pan_Maiz":"Pan de Maíz",
}

# ══════════════════════════════════════════════════════════════════════════════
# HELPER: hex → rgba (compatible con todas las versiones de Plotly)
# ══════════════════════════════════════════════════════════════════════════════
def hex_rgba(hex_color, alpha=0.15):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

# ══════════════════════════════════════════════════════════════════════════════
# DATOS MAESTROS
# ══════════════════════════════════════════════════════════════════════════════
PRODUCTOS = ["Brownies","Mantecadas","Mantecadas_Amapola","Torta_Naranja","Pan_Maiz"]
MESES     = ["January","February","March","April","May","June","July","August","September","October","November","December"]
MESES_ES  = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]
MESES_F   = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

DEM_HISTORICA = {
    "Brownies":           [315,804,734,541,494, 59,315,803,734,541,494, 59],
    "Mantecadas":         [125,780,432,910,275, 68,512,834,690,455,389,120],
    "Mantecadas_Amapola": [320,710,520,251,631,150,330,220,710,610,489,180],
    "Torta_Naranja":      [100,250,200,101,190, 50,100,220,200,170,180,187],
    "Pan_Maiz":           [330,140,143, 73, 83, 48, 70, 89,118, 83, 67, 87],
}
HORAS_PRODUCTO = {"Brownies":0.866,"Mantecadas":0.175,"Mantecadas_Amapola":0.175,"Torta_Naranja":0.175,"Pan_Maiz":0.312}
RUTAS = {
    "Brownies":           [("Mezclado","mezcla",12,18),("Moldeado","dosificado",8,14),("Horneado","horno",30,40),("Enfriamiento","enfriamiento",25,35),("Corte/Empaque","empaque",8,12)],
    "Mantecadas":         [("Mezclado","mezcla",12,18),("Dosificado","dosificado",16,24),("Horneado","horno",20,30),("Enfriamiento","enfriamiento",35,55),("Empaque","empaque",4,6)],
    "Mantecadas_Amapola": [("Mezclado","mezcla",12,18),("Inc. Semillas","mezcla",8,12),("Dosificado","dosificado",16,24),("Horneado","horno",20,30),("Enfriamiento","enfriamiento",36,54),("Empaque","empaque",4,6)],
    "Torta_Naranja":      [("Mezclado","mezcla",16,24),("Dosificado","dosificado",8,12),("Horneado","horno",32,48),("Enfriamiento","enfriamiento",48,72),("Desmolde","dosificado",8,12),("Empaque","empaque",8,12)],
    "Pan_Maiz":           [("Mezclado","mezcla",12,18),("Amasado","amasado",16,24),("Moldeado","dosificado",12,18),("Horneado","horno",28,42),("Enfriamiento","enfriamiento",36,54),("Empaque","empaque",4,6)],
}
TAMANO_LOTE_BASE = {"Brownies":12,"Mantecadas":10,"Mantecadas_Amapola":10,"Torta_Naranja":12,"Pan_Maiz":15}
CAPACIDAD_BASE   = {"mezcla":2,"dosificado":2,"horno":3,"enfriamiento":4,"empaque":2,"amasado":1}
PARAMS_DEFAULT   = {"Ct":4_310,"Ht":100_000,"PIt":100_000,"CRt":11_364,"COt":14_205,"CW_mas":14_204,"CW_menos":15_061,"M":1,"LR_inicial":44*4*10,"inv_seg":0.0}
INV_INICIAL = {p:0 for p in PRODUCTOS}

# ══════════════════════════════════════════════════════════════════════════════
# FUNCIONES CORE
# ══════════════════════════════════════════════════════════════════════════════

def demanda_horas_hombre(factor=1.0):
    return {mes:round(sum(DEM_HISTORICA[p][i]*HORAS_PRODUCTO[p] for p in PRODUCTOS)*factor,4)
            for i,mes in enumerate(MESES)}

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
def run_agregacion(factor_demanda=1.0, params_tuple=None):
    params=PARAMS_DEFAULT.copy()
    if params_tuple: params.update(dict(params_tuple))
    dem_h=demanda_horas_hombre(factor_demanda)
    Ct=params["Ct"]; Ht=params["Ht"]; PIt=params["PIt"]
    CRt=params["CRt"]; COt=params["COt"]; Wm=params["CW_mas"]; Wd=params["CW_menos"]
    M=params["M"]; LRi=params["LR_inicial"]
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
def run_desagregacion(prod_hh_items, factor_demanda=1.0):
    prod_hh=dict(prod_hh_items)
    mdl=LpProblem("Desagregacion",LpMinimize)
    X={(p,t):LpVariable(f"X_{p}_{t}",lowBound=0) for p in PRODUCTOS for t in MESES}
    I={(p,t):LpVariable(f"I_{p}_{t}",lowBound=0) for p in PRODUCTOS for t in MESES}
    S={(p,t):LpVariable(f"S_{p}_{t}",lowBound=0) for p in PRODUCTOS for t in MESES}
    mdl += lpSum(100_000*I[p,t]+150_000*S[p,t] for p in PRODUCTOS for t in MESES)
    for idx,t in enumerate(MESES):
        tp=MESES[idx-1] if idx>0 else None
        mdl += (lpSum(HORAS_PRODUCTO[p]*X[p,t] for p in PRODUCTOS)<=prod_hh[t],f"Cap_{t}")
        for p in PRODUCTOS:
            d=int(DEM_HISTORICA[p][idx]*factor_demanda)
            if idx==0: mdl += I[p,t]-S[p,t]==INV_INICIAL[p]+X[p,t]-d
            else:      mdl += I[p,t]-S[p,t]==I[p,tp]-S[p,tp]+X[p,t]-d
    mdl.solve(PULP_CBC_CMD(msg=False))
    resultados={}
    for p in PRODUCTOS:
        filas=[]
        for idx,t in enumerate(MESES):
            xv=round(X[p,t].varValue or 0,2); iv=round(I[p,t].varValue or 0,2)
            sv=round(S[p,t].varValue or 0,2)
            ini=INV_INICIAL[p] if idx==0 else round(I[p,MESES[idx-1]].varValue or 0,2)
            filas.append({"Mes":t,"Mes_ES":MESES_ES[idx],"Mes_F":MESES_F[idx],
                          "Demanda":int(DEM_HISTORICA[p][idx]*factor_demanda),
                          "Produccion":xv,"Inv_Ini":ini,"Inv_Fin":iv,"Backlog":sv})
        resultados[p]=pd.DataFrame(filas)
    return resultados

@st.cache_data(show_spinner=False)
def run_simulacion_cached(plan_items, cap_items, falla, factor_t, semilla=42):
    plan_unidades=dict(plan_items); cap_recursos=dict(cap_items)
    random.seed(semilla); np.random.seed(semilla)
    lotes_data,uso_rec,sensores=[],[],[]
    def sensor_horno(env,recursos):
        while True:
            ocp=recursos["horno"].count
            temp=round(np.random.normal(160+ocp*20,5),2)
            sensores.append({"tiempo":round(env.now,1),"temperatura":temp,"horno_ocup":ocp,"horno_cola":len(recursos["horno"].queue)})
            yield env.timeout(10)
    def reg_uso(env,recursos,prod=""):
        ts=round(env.now,3)
        for nm,r in recursos.items():
            uso_rec.append({"tiempo":ts,"recurso":nm,"ocupados":r.count,"cola":len(r.queue),"capacidad":r.capacity,"producto":prod})
    def proceso_lote(env,lid,prod,tam,recursos):
        t0=env.now; esperas={}
        for etapa,rec_nm,tmin,tmax in RUTAS[prod]:
            escala=math.sqrt(tam/TAMANO_LOTE_BASE[prod])
            tp=random.uniform(tmin,tmax)*escala*factor_t
            if falla and rec_nm=="horno": tp+=random.uniform(10,30)
            reg_uso(env,recursos,prod); t_entrada=env.now
            with recursos[rec_nm].request() as req:
                yield req; esperas[etapa]=round(env.now-t_entrada,3)
                reg_uso(env,recursos,prod); yield env.timeout(tp)
            reg_uso(env,recursos,prod)
        lotes_data.append({"lote_id":lid,"producto":prod,"tamano":tam,
                           "t_creacion":round(t0,3),"t_fin":round(env.now,3),
                           "tiempo_sistema":round(env.now-t0,3),
                           "total_espera":round(sum(esperas.values()),3)})
    env=simpy.Environment()
    recursos={nm:simpy.Resource(env,capacity=cap) for nm,cap in cap_recursos.items()}
    env.process(sensor_horno(env,recursos))
    dur_mes=44*4*60; lotes=[]; ctr=[0]
    for prod,unid in plan_unidades.items():
        if unid<=0: continue
        tam=TAMANO_LOTE_BASE[prod]; n=math.ceil(unid/tam)
        tasa=dur_mes/max(n,1); ta=random.expovariate(1/max(tasa,1)); rem=unid
        for _ in range(n):
            lotes.append((round(ta,2),prod,min(tam,int(rem)))); rem-=tam
            ta+=random.expovariate(1/max(tasa,1))
    lotes.sort(key=lambda x:x[0])
    def lanzador():
        for ta,prod,tam in lotes:
            yield env.timeout(max(ta-env.now,0))
            lid=f"{prod[:3].upper()}_{ctr[0]:04d}"; ctr[0]+=1
            env.process(proceso_lote(env,lid,prod,tam,recursos))
    env.process(lanzador()); env.run(until=dur_mes*1.8)
    df_lotes=pd.DataFrame(lotes_data) if lotes_data else pd.DataFrame()
    df_uso=pd.DataFrame(uso_rec) if uso_rec else pd.DataFrame()
    df_sensores=pd.DataFrame(sensores) if sensores else pd.DataFrame()
    return df_lotes,df_uso,df_sensores

def calc_utilizacion(df_uso):
    if df_uso.empty: return pd.DataFrame()
    filas=[]
    for rec,grp in df_uso.groupby("recurso"):
        grp=grp.sort_values("tiempo").reset_index(drop=True)
        cap=grp["capacidad"].iloc[0]; t=grp["tiempo"].values; ocp=grp["ocupados"].values
        if len(t)>1 and (t[-1]-t[0])>0:
            fn=np.trapezoid if hasattr(np,"trapezoid") else np.trapz
            util=round(fn(ocp,t)/(cap*(t[-1]-t[0]))*100,2)
        else: util=0.0
        filas.append({"Recurso":rec,"Utilizacion_%":util,"Cola Prom":round(grp["cola"].mean(),3),
                      "Cola Max":int(grp["cola"].max()),"Capacidad":int(cap),
                      "Cuello Botella":util>=80 or grp["cola"].mean()>0.5})
    return pd.DataFrame(filas).sort_values("Utilizacion_%",ascending=False).reset_index(drop=True)

def calc_kpis(df_lotes,plan):
    if df_lotes.empty: return pd.DataFrame()
    dur=(df_lotes["t_fin"].max()-df_lotes["t_creacion"].min())/60; filas=[]
    for p in PRODUCTOS:
        sub=df_lotes[df_lotes["producto"]==p]
        if sub.empty: continue
        und=sub["tamano"].sum(); plan_und=plan.get(p,0)
        tp=round(und/max(dur,0.01),3); ct=round((sub["tiempo_sistema"]/sub["tamano"]).mean(),3)
        lt=round(sub["tiempo_sistema"].mean(),3)
        dem_avg=sum(DEM_HISTORICA[p])/12
        takt=round((44*4*60)/max(dem_avg/TAMANO_LOTE_BASE[p],1),2)
        wip=round(tp*(lt/60),2)
        filas.append({"Producto":PROD_LABELS[p],"Und Producidas":und,"Plan":plan_und,
                      "Throughput (und/h)":tp,"Cycle Time (min/und)":ct,
                      "Lead Time (min/lote)":lt,"WIP Prom":wip,"Takt (min/lote)":takt,
                      "Cumplimiento %":round(min(und/max(plan_und,1)*100,100),2)})
    return pd.DataFrame(filas)

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG STREAMLIT
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Gemelo Digital · Dora del Hoyo", page_icon="🥐",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@400;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600&display=swap');
html,body,[class*="css"]{font-family:'Plus Jakarta Sans',sans-serif;background:#FFF8EE;}
.hero{background:linear-gradient(135deg,#3D1C02 0%,#C68B59 60%,#F2C27A 100%);
  padding:2rem 2.5rem 1.6rem;border-radius:20px;margin-bottom:1.5rem;
  box-shadow:0 12px 40px rgba(61,28,2,0.18);position:relative;overflow:hidden;}
.hero::before{content:"🥐";font-size:9rem;position:absolute;right:1.5rem;top:-1.5rem;
  opacity:0.1;transform:rotate(-15deg);}
.hero h1{font-family:'Fraunces',serif;color:#FFF8EE;font-size:2.2rem;margin:0;letter-spacing:-0.5px;}
.hero p{color:#F9E4A0;margin:0.35rem 0 0;font-size:0.93rem;font-weight:300;}
.hero .badge{display:inline-block;background:rgba(255,255,255,0.15);color:#FFF8EE;
  padding:0.2rem 0.7rem;border-radius:20px;font-size:0.75rem;margin-top:0.6rem;
  margin-right:0.3rem;border:1px solid rgba(255,255,255,0.25);}
.kpi-card{background:white;border-radius:16px;padding:1.1rem 1.2rem;
  box-shadow:0 4px 16px rgba(61,28,2,0.07);border:1px solid rgba(242,194,122,0.35);
  text-align:center;transition:transform 0.2s;}
.kpi-card:hover{transform:translateY(-3px);box-shadow:0 8px 24px rgba(61,28,2,0.12);}
.kpi-card .icon{font-size:1.7rem;margin-bottom:0.25rem;}
.kpi-card .val{font-family:'Fraunces',serif;font-size:1.8rem;color:#3D1C02;line-height:1;margin:0.1rem 0;}
.kpi-card .lbl{font-size:0.7rem;color:#C68B59;text-transform:uppercase;letter-spacing:1px;font-weight:600;}
.kpi-card .sub{font-size:0.76rem;color:#9B7B5A;margin-top:0.2rem;}
.sec-title{font-family:'Fraunces',serif;font-size:1.3rem;color:#3D1C02;
  border-left:4px solid #F2C27A;padding-left:0.75rem;margin:1.5rem 0 0.8rem;}
.info-box{background:linear-gradient(135deg,rgba(249,228,160,0.3),rgba(255,248,238,0.8));
  border:1px solid rgba(242,194,122,0.5);border-radius:12px;
  padding:0.8rem 1rem;font-size:0.87rem;color:#3D1C02;margin:0.5rem 0 0.8rem;}
.pill-ok{background:#A8D8B9;color:#1B5E20;padding:0.3rem 0.9rem;
  border-radius:20px;font-size:0.82rem;font-weight:600;display:inline-block;}
.pill-warn{background:#F4A7B9;color:#880E2E;padding:0.3rem 0.9rem;
  border-radius:20px;font-size:0.82rem;font-weight:600;display:inline-block;}
[data-testid="stSidebar"]{background:#3D1C02 !important;}
[data-testid="stSidebar"] label,[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,[data-testid="stSidebar"] div{color:#F9E4A0 !important;}
[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3{color:#F2C27A !important;font-family:'Fraunces',serif !important;}
[data-testid="stSidebar"] hr{border-color:#C68B5960 !important;}
.stTabs [data-baseweb="tab"]{font-family:'Plus Jakarta Sans',sans-serif;font-weight:500;color:#C68B59;}
.stTabs [aria-selected="true"]{color:#3D1C02 !important;}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🥐 Dora del Hoyo")
    st.markdown("*Gemelo Digital v2.0*")
    st.markdown("---")
    st.markdown("### 📅 Mes a simular")
    mes_idx = st.selectbox("Mes", range(12), index=1, format_func=lambda i: MESES_F[i], label_visibility="collapsed")
    st.markdown("### 📊 Demanda")
    factor_demanda   = st.slider("Factor de demanda", 0.5, 2.0, 1.0, 0.05)
    meses_pronostico = st.slider("Meses de pronóstico a proyectar", 1, 6, 3)
    st.markdown("### 🏭 Producción")
    cap_horno   = st.slider("Capacidad del horno (estaciones)", 1, 6, 3)
    falla_horno = st.checkbox("⚠️ Simular fallas en horno")
    doble_turno = st.checkbox("🕐 Doble turno (−20% tiempo)")
    semilla     = st.number_input("Semilla aleatoria", value=42, step=1)
    st.markdown("### 💰 Costos (COP)")
    with st.expander("⚙️ Configuración del modelo LP"):
        ct   = st.number_input("Costo producción/und (Ct)",    value=4_310,   step=100)
        crt  = st.number_input("Costo hora regular (CRt)",     value=11_364,  step=100)
        cot  = st.number_input("Costo hora extra (COt)",       value=14_205,  step=100)
        ht   = st.number_input("Costo mantener inv. (Ht)",     value=100_000, step=1000)
        pit  = st.number_input("Penalización backlog (PIt)",   value=100_000, step=1000)
        cwp  = st.number_input("Costo contratar (CW+)",        value=14_204,  step=100)
        cwm  = st.number_input("Costo despedir (CW−)",         value=15_061,  step=100)
        trab = st.number_input("Trabajadores iniciales",        value=10,      step=1)
    st.markdown("---")
    st.markdown("<div style='font-size:0.75rem;color:#F2C27A;'>📍 Panadería Dora del Hoyo<br>🔢 SimPy · PuLP · Streamlit</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# HERO HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(f"""
<div class="hero">
  <h1>Gemelo Digital — Panadería Dora del Hoyo</h1>
  <p>Optimización de producción · Simulación de eventos discretos · Análisis what-if</p>
  <span class="badge">📅 {MESES_F[mes_idx]}</span>
  <span class="badge">📈 Demanda ×{factor_demanda}</span>
  <span class="badge">🔥 Horno: {cap_horno} est.</span>
  {"<span class='badge'>⚠️ Falla activa</span>" if falla_horno else ""}
  {"<span class='badge'>🕐 Doble turno</span>" if doble_turno else ""}
</div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# CÁLCULOS PRINCIPALES
# ══════════════════════════════════════════════════════════════════════════════
params_custom = {**PARAMS_DEFAULT,"Ct":ct,"CRt":crt,"COt":cot,"Ht":ht,"PIt":pit,
                 "CW_mas":cwp,"CW_menos":cwm,"LR_inicial":44*4*int(trab)}

with st.spinner("⚙️ Optimizando plan agregado..."):
    df_agr, costo = run_agregacion(factor_demanda, tuple(sorted(params_custom.items())))

prod_hh = dict(zip(df_agr["Mes"], df_agr["Produccion_HH"]))

with st.spinner("🔢 Desagregando por producto..."):
    desag = run_desagregacion(tuple(prod_hh.items()), factor_demanda)

mes_nm   = MESES[mes_idx]
plan_mes = {p:int(desag[p].loc[desag[p]["Mes"]==mes_nm,"Produccion"].values[0]) for p in PRODUCTOS}
cap_rec  = {**CAPACIDAD_BASE,"horno":int(cap_horno)}
factor_t = 0.80 if doble_turno else 1.0

with st.spinner("🏭 Simulando planta de producción..."):
    df_lotes,df_uso,df_sensores = run_simulacion_cached(
        tuple(plan_mes.items()), tuple(cap_rec.items()), falla_horno, factor_t, int(semilla))

df_kpis = calc_kpis(df_lotes, plan_mes)
df_util  = calc_utilizacion(df_uso)

# ══════════════════════════════════════════════════════════════════════════════
# KPIs SUPERIORES
# ══════════════════════════════════════════════════════════════════════════════
cum_avg  = df_kpis["Cumplimiento %"].mean() if not df_kpis.empty else 0
util_max = df_util["Utilizacion_%"].max()   if not df_util.empty else 0
lotes_n  = len(df_lotes) if not df_lotes.empty else 0
temp_avg = df_sensores["temperatura"].mean() if not df_sensores.empty else 0
excesos  = int((df_sensores["temperatura"]>200).sum()) if not df_sensores.empty else 0

k1,k2,k3,k4,k5 = st.columns(5)
def kpi_card(col, icon, val, lbl, sub=""):
    col.markdown(f"""
    <div class="kpi-card">
      <div class="icon">{icon}</div>
      <div class="val">{val}</div>
      <div class="lbl">{lbl}</div>
      {"<div class='sub'>"+sub+"</div>" if sub else ""}
    </div>""", unsafe_allow_html=True)

kpi_card(k1,"💰",f"${costo/1e6:.1f}M","Costo Óptimo","COP · Plan anual")
kpi_card(k2,"📦",f"{lotes_n:,}","Lotes Simulados",MESES_F[mes_idx])
kpi_card(k3,"✅",f"{cum_avg:.1f}%","Cumplimiento","Producción vs Plan")
kpi_card(k4,"⚙️",f"{util_max:.0f}%","Util. Máx. Recurso",
         "⚠️ Cuello botella" if util_max>=80 else "✓ OK")
kpi_card(k5,"🌡️",f"{temp_avg:.0f}°C","Temp. Horno",
         f"⚠️ {excesos} excesos >200°C" if excesos else "✓ Sin excesos")

st.markdown("<br>", unsafe_allow_html=True)

PLOT_CFG = dict(template="plotly_white", font=dict(family="Plus Jakarta Sans"),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,252,245,0.5)")

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tabs = st.tabs(["📊 Demanda & Pronóstico","📋 Plan Agregado","📦 Desagregación","🏭 Simulación","🌡️ Sensores","🔬 Escenarios"])

# ────────────────────────────────────────────────────────────────────────────
# TAB 1 — DEMANDA & PRONÓSTICO
# ────────────────────────────────────────────────────────────────────────────
with tabs[0]:
    st.markdown('<div class="sec-title">📈 Demanda histórica y pronóstico por producto</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Datos históricos anuales de la panadería Dora del Hoyo · Suavizado exponencial (α=0.3) para proyección futura. Las líneas punteadas son el pronóstico.</div>', unsafe_allow_html=True)

    fig_pro = go.Figure()
    for i, p in enumerate(PRODUCTOS):
        serie=[v*factor_demanda for v in DEM_HISTORICA[p]]
        suav, futuro = pronostico_simple(serie, meses_pronostico)
        fig_pro.add_trace(go.Scatter(
            x=MESES_ES, y=serie, mode="lines", name=PROD_LABELS[p],
            line=dict(color=PROD_COLORS_DARK[p], width=2.2),
            legendgroup=p, showlegend=True,
        ))
        meses_fut=[f"P+{j+1}" for j in range(meses_pronostico)]
        x_fut=[MESES_ES[-1]]+meses_fut; y_fut=[suav[-1]]+futuro
        fig_pro.add_trace(go.Scatter(
            x=x_fut, y=y_fut, mode="lines+markers",
            line=dict(color=PROD_COLORS_DARK[p], width=2, dash="dash"),
            marker=dict(size=9, symbol="circle", color=PROD_COLORS[p],
                        line=dict(color=PROD_COLORS_DARK[p],width=2)),
            legendgroup=p, showlegend=False,
        ))
    # FIX: usar índice numérico en lugar de string categórico
    fig_pro.add_vline(x=len(MESES_ES)-1, line_dash="dot", line_color="#C68B59",
                      annotation_text="▶ Pronóstico", annotation_font_color="#C68B59",
                      annotation_position="top right")
    fig_pro.update_layout(
        **PLOT_CFG, height=400,
        title="Demanda Histórica & Proyección de Demanda — Dora del Hoyo",
        xaxis_title="Mes", yaxis_title="Unidades",
        legend=dict(orientation="h",y=-0.22,x=0.5,xanchor="center"),
        xaxis=dict(showgrid=True,gridcolor="#F0E8D8"),
        yaxis=dict(showgrid=True,gridcolor="#F0E8D8"),
    )
    st.plotly_chart(fig_pro, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown('<div class="sec-title">🔥 Mapa de calor — Estacionalidad</div>', unsafe_allow_html=True)
        z=[[DEM_HISTORICA[p][i]*factor_demanda for i in range(12)] for p in PRODUCTOS]
        fig_heat=go.Figure(go.Heatmap(
            z=z, x=MESES_ES, y=[PROD_LABELS[p] for p in PRODUCTOS],
            colorscale=[[0,"#FFF8EE"],[0.3,"#F9E4A0"],[0.65,"#F2C27A"],[1,"#C68B59"]],
            hovertemplate="%{y}<br>%{x}: %{z:.0f} und<extra></extra>",
            text=[[f"{int(v)}" for v in row] for row in z],
            texttemplate="%{text}", textfont=dict(size=9,color="#3D1C02"),
        ))
        fig_heat.update_layout(**PLOT_CFG, height=240, margin=dict(t=20,b=10))
        st.plotly_chart(fig_heat, use_container_width=True)

    with col_b:
        st.markdown('<div class="sec-title">🌸 Participación anual de ventas</div>', unsafe_allow_html=True)
        totales={p:sum(DEM_HISTORICA[p]) for p in PRODUCTOS}
        fig_pie=go.Figure(go.Pie(
            labels=[PROD_LABELS[p] for p in PRODUCTOS],
            values=list(totales.values()), hole=0.55,
            marker=dict(colors=list(PROD_COLORS.values()), line=dict(color="white",width=3)),
            textfont=dict(size=11),
            hovertemplate="%{label}<br>%{value:,} und/año<br>%{percent}<extra></extra>",
        ))
        fig_pie.update_layout(
            **PLOT_CFG, height=240, margin=dict(t=10,b=10),
            annotations=[dict(text="<b>Ventas</b><br>anuales",x=0.5,y=0.5,
                              font=dict(size=11,color="#3D1C02"),showarrow=False)],
            legend=dict(orientation="v",x=1,y=0.5,font=dict(size=11)),
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown('<div class="sec-title">⏱️ Demanda total en Horas-Hombre por mes</div>', unsafe_allow_html=True)
    dem_h_vals=demanda_horas_hombre(factor_demanda)
    colores_hh=[C["caramel"] if i!=mes_idx else C["mocha"] for i in range(12)]
    fig_hh=go.Figure()
    fig_hh.add_trace(go.Bar(x=MESES_ES, y=list(dem_h_vals.values()),
                            marker_color=colores_hh, marker_line_color="white", marker_line_width=1.5,
                            hovertemplate="%{x}: %{y:.1f} H-H<extra></extra>", showlegend=False))
    fig_hh.add_trace(go.Scatter(x=MESES_ES, y=list(dem_h_vals.values()), mode="lines+markers",
                                line=dict(color=C["mocha"],width=2), marker=dict(size=6),
                                showlegend=False))
    fig_hh.update_layout(**PLOT_CFG, height=260, xaxis_title="Mes", yaxis_title="H-H",
                         xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#F0E8D8"),
                         margin=dict(t=20,b=20))
    st.plotly_chart(fig_hh, use_container_width=True)

# ────────────────────────────────────────────────────────────────────────────
# TAB 2 — PLAN AGREGADO
# ────────────────────────────────────────────────────────────────────────────
with tabs[1]:
    st.markdown('<div class="sec-title">📋 Planeación Agregada — Optimización Lineal (PuLP)</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="info-box"><b>{int(trab)} trabajadores</b> iniciales · {int(44*4*trab):,} H-H regulares/mes · '
                f'CRt: ${crt:,} · COt: ${cot:,} · Ht: ${ht:,} COP</div>', unsafe_allow_html=True)

    m1,m2,m3,m4 = st.columns(4)
    m1.metric("💰 Costo Total", f"${costo:,.0f} COP")
    m2.metric("⏰ Horas Extra", f"{df_agr['Horas_Extras'].sum():,.0f} H-H")
    m3.metric("📉 Backlog Total", f"{df_agr['Backlog_HH'].sum():,.0f} H-H")
    m4.metric("👥 Contrat. Netas", f"{df_agr['Contratacion'].sum()-df_agr['Despidos'].sum():+.0f} pers.")

    st.markdown('<div class="sec-title">📊 Plan Agregado — Producción vs Demanda (H-H)</div>', unsafe_allow_html=True)
    fig_agr=go.Figure()
    fig_agr.add_trace(go.Bar(x=df_agr["Mes_ES"],y=df_agr["Inv_Ini_HH"],name="Inv. Inicial H-H",
                             marker_color=C["sky"],opacity=0.8,marker_line_color="white",marker_line_width=1))
    fig_agr.add_trace(go.Bar(x=df_agr["Mes_ES"],y=df_agr["Produccion_HH"],name="Producción H-H",
                             marker_color=C["caramel"],opacity=0.9,marker_line_color="white",marker_line_width=1))
    fig_agr.add_trace(go.Scatter(x=df_agr["Mes_ES"],y=df_agr["Demanda_HH"],mode="lines+markers",
                                 name="Demanda H-H",line=dict(color=C["mocha"],dash="dash",width=2.5),
                                 marker=dict(size=8,color=C["mocha"])))
    fig_agr.add_trace(go.Scatter(x=df_agr["Mes_ES"],y=df_agr["Horas_Regulares"],mode="lines",
                                 name="Cap. Regular",line=dict(color=C["rose"],dash="dot",width=2)))
    fig_agr.update_layout(**PLOT_CFG,barmode="stack",height=370,
                          title=f"Costo Óptimo LP: COP ${costo:,.0f}",
                          xaxis_title="Mes",yaxis_title="Horas-Hombre",
                          legend=dict(orientation="h",y=-0.22,x=0.5,xanchor="center"),
                          xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"))
    st.plotly_chart(fig_agr, use_container_width=True)

    col1,col2 = st.columns(2)
    with col1:
        st.markdown('<div class="sec-title">👷 Fuerza laboral</div>', unsafe_allow_html=True)
        fig_fl=go.Figure()
        fig_fl.add_trace(go.Bar(x=df_agr["Mes_ES"],y=df_agr["Contratacion"],name="Contrataciones",
                                marker_color=C["mint"],marker_line_color="white",marker_line_width=1))
        fig_fl.add_trace(go.Bar(x=df_agr["Mes_ES"],y=df_agr["Despidos"],name="Despidos",
                                marker_color=C["rose"],marker_line_color="white",marker_line_width=1))
        fig_fl.update_layout(**PLOT_CFG,barmode="group",height=290,
                             legend=dict(orientation="h",y=-0.3,x=0.5,xanchor="center"),
                             xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"))
        st.plotly_chart(fig_fl, use_container_width=True)

    with col2:
        st.markdown('<div class="sec-title">⚡ Horas Extra & Backlog</div>', unsafe_allow_html=True)
        fig_ex=go.Figure()
        fig_ex.add_trace(go.Bar(x=df_agr["Mes_ES"],y=df_agr["Horas_Extras"],name="Horas Extra",
                                marker_color=C["butter"],marker_line_color="white",marker_line_width=1))
        fig_ex.add_trace(go.Bar(x=df_agr["Mes_ES"],y=df_agr["Backlog_HH"],name="Backlog",
                                marker_color=C["rose"],marker_line_color="white",marker_line_width=1))
        fig_ex.update_layout(**PLOT_CFG,barmode="group",height=290,
                             legend=dict(orientation="h",y=-0.3,x=0.5,xanchor="center"),
                             xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"))
        st.plotly_chart(fig_ex, use_container_width=True)

    with st.expander("📄 Ver tabla completa del plan"):
        df_show=df_agr.drop(columns=["Mes","Mes_ES"]).rename(columns={"Mes_F":"Mes"})
        st.dataframe(df_show.style.format({c:"{:,.1f}" for c in df_show.columns if c!="Mes"})
                     .background_gradient(subset=["Produccion_HH","Horas_Extras"],cmap="YlOrBr"),
                     use_container_width=True)

# ────────────────────────────────────────────────────────────────────────────
# TAB 3 — DESAGREGACIÓN
# ────────────────────────────────────────────────────────────────────────────
with tabs[2]:
    st.markdown('<div class="sec-title">📦 Desagregación del plan en unidades por producto</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">El plan en H-H se convierte en unidades por producto mediante LP. La ★ marca el mes seleccionado para simulación.</div>', unsafe_allow_html=True)

    mes_resaltar=st.selectbox("Mes a resaltar ★",range(12),index=mes_idx,
                               format_func=lambda i:MESES_F[i],key="mes_desag")
    mes_nm_desag=MESES[mes_resaltar]

    fig_des=make_subplots(rows=3,cols=2,subplot_titles=[PROD_LABELS[p] for p in PRODUCTOS],
                          vertical_spacing=0.12,horizontal_spacing=0.08)
    for idx,p in enumerate(PRODUCTOS):
        r,c=idx//2+1,idx%2+1; df_p=desag[p]
        fig_des.add_trace(go.Bar(x=df_p["Mes_ES"],y=df_p["Produccion"],
                                 marker_color=PROD_COLORS[p],opacity=0.9,showlegend=False,
                                 marker_line_color="white",marker_line_width=1,
                                 hovertemplate="%{x}: %{y:.0f} und<extra></extra>"),row=r,col=c)
        fig_des.add_trace(go.Scatter(x=df_p["Mes_ES"],y=df_p["Demanda"],mode="lines+markers",
                                     line=dict(color=PROD_COLORS_DARK[p],dash="dash",width=1.5),
                                     marker=dict(size=5),showlegend=False),row=r,col=c)
        mes_row=df_p[df_p["Mes"]==mes_nm_desag]
        if not mes_row.empty:
            fig_des.add_trace(go.Scatter(x=[MESES_ES[mes_resaltar]],y=[mes_row["Produccion"].values[0]],
                                         mode="markers",marker=dict(size=14,color=C["mocha"],symbol="star"),
                                         showlegend=False),row=r,col=c)
    fig_des.update_layout(**PLOT_CFG,height=680,barmode="group",
                          title="Producción planificada vs Demanda por producto (unidades/mes)",
                          margin=dict(t=60))
    for i in range(1,4):
        for j in range(1,3):
            fig_des.update_xaxes(showgrid=False,row=i,col=j)
            fig_des.update_yaxes(gridcolor="#F0E8D8",row=i,col=j)
    st.plotly_chart(fig_des, use_container_width=True)

    st.markdown('<div class="sec-title">🎯 Cobertura de demanda anual</div>', unsafe_allow_html=True)
    prods_c,cob_vals,und_prod,und_dem=[],[],[],[]
    for p in PRODUCTOS:
        df_p=desag[p]; tot_p=df_p["Produccion"].sum(); tot_d=df_p["Demanda"].sum()
        cob=round(min(tot_p/max(tot_d,1)*100,100),1)
        prods_c.append(PROD_LABELS[p]); cob_vals.append(cob)
        und_prod.append(int(tot_p)); und_dem.append(int(tot_d))

    col_cob1,col_cob2=st.columns([2,1])
    with col_cob1:
        fig_cob=go.Figure()
        fig_cob.add_trace(go.Bar(y=prods_c,x=cob_vals,orientation="h",
                                  marker=dict(color=list(PROD_COLORS.values()),line=dict(color="white",width=2)),
                                  text=[f"{v:.1f}%" for v in cob_vals],textposition="inside",
                                  textfont=dict(color="#3D1C02",size=12),
                                  hovertemplate="%{y}: %{x:.1f}%<extra></extra>"))
        fig_cob.add_vline(x=100,line_dash="dash",line_color=C["mocha"],
                          annotation_text="Meta 100%",annotation_font_color=C["mocha"])
        fig_cob.update_layout(**PLOT_CFG,height=270,xaxis_title="Cobertura (%)",
                              xaxis=dict(range=[0,115]),yaxis=dict(showgrid=False),
                              margin=dict(t=20,b=20),showlegend=False)
        st.plotly_chart(fig_cob, use_container_width=True)
    with col_cob2:
        df_cob=pd.DataFrame({"Producto":prods_c,"Producido":und_prod,"Demanda":und_dem,"Cob %":cob_vals})
        st.dataframe(df_cob.style.format({"Producido":"{:,.0f}","Demanda":"{:,.0f}","Cob %":"{:.1f}%"})
                     .background_gradient(subset=["Cob %"],cmap="YlGn"),
                     use_container_width=True,height=270)

    st.markdown('<div class="sec-title">📦 Inventario final proyectado</div>', unsafe_allow_html=True)
    fig_inv=go.Figure()
    for p in PRODUCTOS:
        # FIX: usar hex_rgba en lugar de hex+"28"
        fig_inv.add_trace(go.Scatter(x=desag[p]["Mes_ES"],y=desag[p]["Inv_Fin"],
                                     name=PROD_LABELS[p],mode="lines+markers",
                                     line=dict(color=PROD_COLORS_DARK[p],width=2),
                                     marker=dict(size=7,color=PROD_COLORS[p],
                                                 line=dict(color=PROD_COLORS_DARK[p],width=1.5)),
                                     fill="tozeroy",fillcolor=hex_rgba(PROD_COLORS[p],0.16)))
    fig_inv.update_layout(**PLOT_CFG,height=280,xaxis_title="Mes",yaxis_title="Unidades en inventario",
                          legend=dict(orientation="h",y=-0.28,x=0.5,xanchor="center"),
                          xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"))
    st.plotly_chart(fig_inv, use_container_width=True)

# ────────────────────────────────────────────────────────────────────────────
# TAB 4 — SIMULACIÓN
# ────────────────────────────────────────────────────────────────────────────
with tabs[3]:
    st.markdown(f'<div class="sec-title">🏭 Simulación de Planta — {MESES_F[mes_idx]}</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Simulación SimPy · Rutas: Mezclado → Dosificado/Moldeado → Horneado → Enfriamiento → Empaque · Tiempos estocásticos por producto.</div>', unsafe_allow_html=True)

    st.markdown('<div class="sec-title">🗓️ Plan del mes (unidades a producir)</div>', unsafe_allow_html=True)
    cols_p=st.columns(5)
    EMOJIS={"Brownies":"🍫","Mantecadas":"🧁","Mantecadas_Amapola":"🌸","Torta_Naranja":"🍊","Pan_Maiz":"🌽"}
    for i,(p,u) in enumerate(plan_mes.items()):
        with cols_p[i]:
            hh_req=round(u*HORAS_PRODUCTO[p],1)
            st.markdown(f"""
            <div class="kpi-card" style="background:{PROD_COLORS[p]}35;border-color:{PROD_COLORS_DARK[p]}50">
              <div class="icon">{EMOJIS[p]}</div>
              <div class="val" style="font-size:1.5rem">{u:,}</div>
              <div class="lbl">{PROD_LABELS[p]}</div>
              <div class="sub">{hh_req} H-H</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if not df_kpis.empty:
        st.markdown('<div class="sec-title">✅ Cumplimiento del plan por producto</div>', unsafe_allow_html=True)
        fig_cum=go.Figure()
        for i,row in df_kpis.iterrows():
            p_key=[p for p in PRODUCTOS if PROD_LABELS[p]==row["Producto"]]
            p_key=p_key[0] if p_key else PRODUCTOS[i%len(PRODUCTOS)]
            fig_cum.add_trace(go.Bar(
                x=[row["Cumplimiento %"]], y=[row["Producto"]], orientation="h",
                marker=dict(color=PROD_COLORS[p_key], line=dict(color=PROD_COLORS_DARK[p_key],width=1.5)),
                text=f"{row['Cumplimiento %']:.1f}%", textposition="inside",
                textfont=dict(color="#3D1C02",size=12), showlegend=False,
                hovertemplate=f"<b>{row['Producto']}</b><br>Prod: {row['Und Producidas']:,.0f}<br>Plan: {row['Plan']:,.0f}<extra></extra>",
            ))
        fig_cum.add_vline(x=100,line_dash="dash",line_color=C["mocha"],annotation_text="Meta 100%")
        fig_cum.update_layout(**PLOT_CFG,height=250,xaxis=dict(range=[0,115]),
                              yaxis=dict(showgrid=False),xaxis_title="Cumplimiento (%)",
                              margin=dict(t=20,b=20),title="Cumplimiento del Plan por Producto")
        st.plotly_chart(fig_cum, use_container_width=True)

        col_t1,col_t2=st.columns(2)
        with col_t1:
            st.markdown('<div class="sec-title">⚡ Throughput (und/h)</div>', unsafe_allow_html=True)
            prods_kpi=[PROD_LABELS[p] for p in PRODUCTOS if PROD_LABELS[p] in df_kpis["Producto"].values]
            colores_kpi=[PROD_COLORS[p] for p in PRODUCTOS if PROD_LABELS[p] in df_kpis["Producto"].values]
            fig_tp=go.Figure(go.Bar(
                x=prods_kpi, y=df_kpis["Throughput (und/h)"].values,
                marker_color=colores_kpi, marker_line_color="white", marker_line_width=2,
                text=[f"{v:.1f}" for v in df_kpis["Throughput (und/h)"].values], textposition="outside",
            ))
            fig_tp.update_layout(**PLOT_CFG,height=270,yaxis_title="und/h",showlegend=False,
                                 xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"),margin=dict(t=40))
            st.plotly_chart(fig_tp, use_container_width=True)

        with col_t2:
            st.markdown('<div class="sec-title">⏱️ Lead Time (min/lote)</div>', unsafe_allow_html=True)
            fig_lt=go.Figure(go.Bar(
                x=prods_kpi, y=df_kpis["Lead Time (min/lote)"].values,
                marker_color=[PROD_COLORS_DARK[p] for p in PRODUCTOS if PROD_LABELS[p] in df_kpis["Producto"].values],
                marker_line_color="white", marker_line_width=2,
                text=[f"{v:.0f}" for v in df_kpis["Lead Time (min/lote)"].values], textposition="outside",
            ))
            fig_lt.update_layout(**PLOT_CFG,height=270,yaxis_title="min/lote",showlegend=False,
                                 xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"),margin=dict(t=40))
            st.plotly_chart(fig_lt, use_container_width=True)

    if not df_util.empty:
        st.markdown('<div class="sec-title">⚙️ Utilización de Recursos & Cuellos de Botella</div>', unsafe_allow_html=True)
        cuellos=df_util[df_util["Cuello Botella"]]
        if not cuellos.empty:
            for _,row in cuellos.iterrows():
                st.markdown(f'<div class="pill-warn">⚠️ Cuello: <b>{row["Recurso"]}</b> — {row["Utilizacion_%"]:.1f}% · Cola prom: {row["Cola Prom"]:.2f}</div><br>',unsafe_allow_html=True)
        else:
            st.markdown('<div class="pill-ok">✅ Sin cuellos de botella detectados</div><br>',unsafe_allow_html=True)

        REC_LABELS={"mezcla":"🥣 Mezcla","dosificado":"🔧 Dosificado","horno":"🔥 Horno",
                    "enfriamiento":"❄️ Enfriamiento","empaque":"📦 Empaque","amasado":"👐 Amasado"}
        rec_lb=[REC_LABELS.get(r,r) for r in df_util["Recurso"]]
        col_util=[C["rose"] if u>=80 else C["butter"] if u>=60 else C["mint"] for u in df_util["Utilizacion_%"]]
        fig_util_g=make_subplots(rows=1,cols=2,subplot_titles=["Utilización (%)","Cola Promedio"])
        fig_util_g.add_trace(go.Bar(x=rec_lb,y=df_util["Utilizacion_%"],marker_color=col_util,
                                    marker_line_color="white",marker_line_width=2,
                                    text=[f"{v:.0f}%" for v in df_util["Utilizacion_%"]],
                                    textposition="outside",showlegend=False),row=1,col=1)
        fig_util_g.add_trace(go.Bar(x=rec_lb,y=df_util["Cola Prom"],marker_color=C["lavender"],
                                    marker_line_color="white",marker_line_width=2,
                                    text=[f"{v:.2f}" for v in df_util["Cola Prom"]],
                                    textposition="outside",showlegend=False),row=1,col=2)
        fig_util_g.add_hline(y=80,line_dash="dash",line_color=C["rose"],annotation_text="⚠ 80%",row=1,col=1)
        fig_util_g.update_layout(**PLOT_CFG,height=310)
        fig_util_g.update_xaxes(showgrid=False); fig_util_g.update_yaxes(gridcolor="#F0E8D8")
        st.plotly_chart(fig_util_g, use_container_width=True)

    if not df_lotes.empty:
        st.markdown('<div class="sec-title">📅 Diagrama de Gantt — Flujo de lotes de producción</div>', unsafe_allow_html=True)
        n_gantt=min(60,len(df_lotes)); sub=df_lotes.head(n_gantt).reset_index(drop=True)
        fig_gantt=go.Figure()
        for _,row in sub.iterrows():
            fig_gantt.add_trace(go.Bar(
                x=[row["tiempo_sistema"]],y=[row["lote_id"]],base=[row["t_creacion"]],
                orientation="h",marker_color=PROD_COLORS.get(row["producto"],"#ccc"),
                opacity=0.85,showlegend=False,marker_line_color="white",marker_line_width=0.5,
                hovertemplate=(f"<b>{PROD_LABELS.get(row['producto'],row['producto'])}</b><br>"
                               f"Inicio: {row['t_creacion']:.0f} min<br>Duración: {row['tiempo_sistema']:.1f} min<extra></extra>"),
            ))
        for p,c in PROD_COLORS.items():
            fig_gantt.add_trace(go.Bar(x=[None],y=[None],marker_color=c,name=PROD_LABELS[p]))
        fig_gantt.update_layout(**PLOT_CFG,barmode="overlay",height=max(370,n_gantt*8),
                                title=f"Gantt — Primeros {n_gantt} lotes",xaxis_title="Tiempo simulado (min)",
                                legend=dict(orientation="h",y=-0.1,x=0.5,xanchor="center"),
                                yaxis=dict(showticklabels=False))
        st.plotly_chart(fig_gantt, use_container_width=True)

        st.markdown('<div class="sec-title">🎻 Distribución de tiempos en sistema por producto</div>', unsafe_allow_html=True)
        fig_violin=go.Figure()
        for p in PRODUCTOS:
            sub_v=df_lotes[df_lotes["producto"]==p]["tiempo_sistema"]
            if len(sub_v)<3: continue
            fig_violin.add_trace(go.Violin(y=sub_v,name=PROD_LABELS[p],box_visible=True,
                                           meanline_visible=True,fillcolor=PROD_COLORS[p],
                                           line_color=PROD_COLORS_DARK[p],opacity=0.8))
        fig_violin.update_layout(**PLOT_CFG,height=310,yaxis_title="Tiempo en sistema (min)",
                                 showlegend=False,violinmode="overlay")
        st.plotly_chart(fig_violin, use_container_width=True)

        with st.expander("📊 Ver tabla completa de KPIs"):
            if not df_kpis.empty:
                st.dataframe(df_kpis.style.format({c:"{:,.2f}" for c in df_kpis.columns if c!="Producto"})
                             .background_gradient(subset=["Cumplimiento %"],cmap="YlGn"),
                             use_container_width=True)

# ────────────────────────────────────────────────────────────────────────────
# TAB 5 — SENSORES
# ────────────────────────────────────────────────────────────────────────────
with tabs[4]:
    st.markdown('<div class="sec-title">🌡️ Sensores Virtuales — Monitor del Horno</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">El gemelo digital simula sensores IoT del horno de la panadería: temperatura en tiempo real, ocupación y alertas de exceso térmico. Límite operativo: 200°C.</div>', unsafe_allow_html=True)

    if not df_sensores.empty:
        s1,s2,s3,s4=st.columns(4)
        s1.metric("🌡️ Temp. mínima",  f"{df_sensores['temperatura'].min():.1f} °C")
        s2.metric("🔥 Temp. máxima",  f"{df_sensores['temperatura'].max():.1f} °C")
        s3.metric("📊 Temp. promedio",f"{df_sensores['temperatura'].mean():.1f} °C")
        s4.metric("⚠️ Excesos >200°C",excesos,
                  delta="Revisar horno" if excesos else "Operación normal",
                  delta_color="inverse" if excesos else "off")

        fig_temp=go.Figure()
        # FIX: usar hex_rgba en lugar de hex+"35" y hex+"22"
        fig_temp.add_hrect(y0=150,y1=200,fillcolor=hex_rgba(C["mint"],0.21),line_width=0,
                           annotation_text="Zona operativa óptima",annotation_font_color=C["sage"])
        fig_temp.add_trace(go.Scatter(x=df_sensores["tiempo"],y=df_sensores["temperatura"],
                                      mode="lines",name="Temperatura",fill="tozeroy",
                                      fillcolor=hex_rgba(C["peach"],0.13),
                                      line=dict(color=C["mocha"],width=1.8)))
        if len(df_sensores)>10:
            mm=df_sensores["temperatura"].rolling(5,min_periods=1).mean()
            fig_temp.add_trace(go.Scatter(x=df_sensores["tiempo"],y=mm,mode="lines",
                                          name="Media móvil",line=dict(color=C["rose"],width=2,dash="dot")))
        fig_temp.add_hline(y=200,line_dash="dash",line_color="#C0392B",
                           annotation_text="⚠ Límite 200°C",annotation_font_color="#C0392B")
        fig_temp.update_layout(**PLOT_CFG,height=310,xaxis_title="Tiempo simulado (min)",
                               yaxis_title="°C",title="Temperatura del Horno — Tiempo Real Simulado",
                               legend=dict(orientation="h",y=-0.22,x=0.5,xanchor="center"),
                               xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"))
        st.plotly_chart(fig_temp, use_container_width=True)

        col_s1,col_s2=st.columns(2)
        with col_s1:
            fig_ocup=go.Figure()
            fig_ocup.add_trace(go.Scatter(x=df_sensores["tiempo"],y=df_sensores["horno_ocup"],
                                          mode="lines",fill="tozeroy",fillcolor=hex_rgba(C["sky"],0.25),
                                          line=dict(color="#4A90C4",width=2),name="Ocupación"))
            fig_ocup.add_hline(y=cap_horno,line_dash="dot",line_color=C["mocha"],
                               annotation_text=f"Cap. máx: {cap_horno}")
            fig_ocup.update_layout(**PLOT_CFG,height=250,title="Ocupación del Horno",
                                   xaxis_title="min",yaxis_title="Estaciones activas",
                                   xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"),
                                   showlegend=False)
            st.plotly_chart(fig_ocup, use_container_width=True)

        with col_s2:
            fig_hist=go.Figure()
            fig_hist.add_trace(go.Histogram(x=df_sensores["temperatura"],nbinsx=35,
                                            marker_color=C["caramel"],opacity=0.85,
                                            marker_line_color="white",marker_line_width=1))
            fig_hist.add_vline(x=200,line_dash="dash",line_color="#C0392B",annotation_text="200°C")
            fig_hist.add_vline(x=df_sensores["temperatura"].mean(),line_dash="dot",
                               line_color=C["mocha"],
                               annotation_text=f"Prom:{df_sensores['temperatura'].mean():.0f}°C")
            fig_hist.update_layout(**PLOT_CFG,height=250,title="Distribución de Temperatura",
                                   xaxis_title="°C",yaxis_title="Frecuencia",showlegend=False,
                                   xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"))
            st.plotly_chart(fig_hist, use_container_width=True)
    else:
        st.info("Sin datos de sensores.")

# ────────────────────────────────────────────────────────────────────────────
# TAB 6 — ESCENARIOS WHAT-IF
# ────────────────────────────────────────────────────────────────────────────
with tabs[5]:
    st.markdown('<div class="sec-title">🔬 Análisis de Escenarios What-If</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Compara múltiples configuraciones de planta para identificar la estrategia óptima de producción en la panadería Dora del Hoyo.</div>', unsafe_allow_html=True)

    ESCENARIOS_DEF={
        "Base":               {"fd":1.0,"falla":False,"ft":1.0, "cap_delta":0},
        "Demanda +20%":       {"fd":1.2,"falla":False,"ft":1.0, "cap_delta":0},
        "Demanda −20%":       {"fd":0.8,"falla":False,"ft":1.0, "cap_delta":0},
        "Falla en horno":     {"fd":1.0,"falla":True, "ft":1.0, "cap_delta":0},
        "Capacidad reducida": {"fd":1.0,"falla":False,"ft":1.0, "cap_delta":-1},
        "Capacidad ampliada": {"fd":1.0,"falla":False,"ft":1.0, "cap_delta":+1},
        "Doble turno":        {"fd":1.0,"falla":False,"ft":0.80,"cap_delta":0},
        "Optimizado":         {"fd":1.0,"falla":False,"ft":0.85,"cap_delta":+1},
    }
    ESC_ICONS={"Base":"🏠","Demanda +20%":"📈","Demanda −20%":"📉","Falla en horno":"⚠️",
               "Capacidad reducida":"⬇️","Capacidad ampliada":"⬆️","Doble turno":"🕐","Optimizado":"🚀"}

    escenarios_sel=st.multiselect("Selecciona escenarios a comparar",
                                   list(ESCENARIOS_DEF.keys()),
                                   default=["Base","Demanda +20%","Falla en horno","Doble turno","Optimizado"])

    if st.button("🚀 Comparar escenarios seleccionados",type="primary"):
        filas_esc=[]; prog=st.progress(0)
        for i,nm in enumerate(escenarios_sel):
            prog.progress((i+1)/len(escenarios_sel),text=f"Simulando: {nm}...")
            cfg=ESCENARIOS_DEF[nm]
            plan_esc={p:max(int(u*cfg["fd"]),0) for p,u in plan_mes.items()}
            cap_esc={**CAPACIDAD_BASE,"horno":max(cap_horno+cfg["cap_delta"],1)}
            df_l,df_u,_=run_simulacion_cached(
                tuple(plan_esc.items()),tuple(cap_esc.items()),cfg["falla"],cfg["ft"],int(semilla))
            k=calc_kpis(df_l,plan_esc); u=calc_utilizacion(df_u)
            fila={"Escenario":ESC_ICONS.get(nm,"")+" "+nm}
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

        st.markdown('<div class="sec-title">📊 Resultados comparativos</div>', unsafe_allow_html=True)
        num_cols=[c for c in df_comp.columns if c not in ["Escenario"] and df_comp[c].dtype!="object"]
        st.dataframe(df_comp.style.format({c:"{:,.2f}" for c in num_cols})
                     .background_gradient(subset=["Cumplimiento %"] if "Cumplimiento %" in df_comp.columns else [],
                                          cmap="YlGn"),
                     use_container_width=True)

        if len(df_comp)>1:
            col_e1,col_e2=st.columns(2)
            with col_e1:
                st.markdown('<div class="sec-title">✅ Cumplimiento por escenario</div>', unsafe_allow_html=True)
                if "Cumplimiento %" in df_comp.columns:
                    col_c=[C["mint"] if v>=90 else C["butter"] if v>=70 else C["rose"] for v in df_comp["Cumplimiento %"]]
                    fig_ec=go.Figure(go.Bar(x=df_comp["Escenario"],y=df_comp["Cumplimiento %"],
                                           marker_color=col_c,marker_line_color="white",marker_line_width=2,
                                           text=[f"{v:.1f}%" for v in df_comp["Cumplimiento %"]],textposition="outside"))
                    fig_ec.add_hline(y=100,line_dash="dash",line_color=C["mocha"])
                    fig_ec.update_layout(**PLOT_CFG,height=290,yaxis_title="%",showlegend=False,
                                         xaxis=dict(showgrid=False,tickangle=-25),yaxis=dict(gridcolor="#F0E8D8"),
                                         margin=dict(t=30,b=80))
                    st.plotly_chart(fig_ec, use_container_width=True)

            with col_e2:
                st.markdown('<div class="sec-title">⚙️ Utilización máxima</div>', unsafe_allow_html=True)
                if "Util. max %" in df_comp.columns:
                    col_u=[C["rose"] if v>=80 else C["butter"] if v>=60 else C["mint"] for v in df_comp["Util. max %"]]
                    fig_eu=go.Figure(go.Bar(x=df_comp["Escenario"],y=df_comp["Util. max %"],
                                           marker_color=col_u,marker_line_color="white",marker_line_width=2,
                                           text=[f"{v:.0f}%" for v in df_comp["Util. max %"]],textposition="outside"))
                    fig_eu.add_hline(y=80,line_dash="dash",line_color=C["rose"],annotation_text="⚠ 80%")
                    fig_eu.update_layout(**PLOT_CFG,height=290,yaxis_title="%",showlegend=False,
                                         xaxis=dict(showgrid=False,tickangle=-25),yaxis=dict(gridcolor="#F0E8D8"),
                                         margin=dict(t=30,b=80))
                    st.plotly_chart(fig_eu, use_container_width=True)

            # Radar chart
            st.markdown('<div class="sec-title">🕸️ Radar comparativo de escenarios</div>', unsafe_allow_html=True)
            cols_radar=[c for c in df_comp.columns if c not in ["Escenario","Cuellos botella"]
                        and df_comp[c].dtype!="object"]
            if len(cols_radar)>=3:
                df_norm=df_comp[cols_radar].copy()
                for c in df_norm.columns:
                    rng=df_norm[c].max()-df_norm[c].min()
                    df_norm[c]=(df_norm[c]-df_norm[c].min())/rng if rng else 0.5

                COLORES_R=[C["caramel"],C["sky"],C["rose"],C["mint"],C["lavender"],C["peach"],C["butter"],C["sage"]]
                RGBA_R=[
                    hex_rgba(C["caramel"],0.15), hex_rgba(C["sky"],0.15),
                    hex_rgba(C["rose"],0.15),    hex_rgba(C["mint"],0.15),
                    hex_rgba(C["lavender"],0.15),hex_rgba(C["peach"],0.15),
                    hex_rgba(C["butter"],0.15),  hex_rgba(C["sage"],0.15),
                ]

                fig_radar=go.Figure()
                for i,row in df_comp.iterrows():
                    vals=[df_norm.loc[i,c] for c in cols_radar]
                    fig_radar.add_trace(go.Scatterpolar(
                        r=vals+[vals[0]], theta=cols_radar+[cols_radar[0]],
                        fill="toself", name=row["Escenario"],
                        line=dict(color=COLORES_R[i%len(COLORES_R)],width=2),
                        fillcolor=RGBA_R[i%len(RGBA_R)],
                    ))
                fig_radar.update_layout(
                    **PLOT_CFG, height=430,
                    polar=dict(radialaxis=dict(visible=True,range=[0,1],gridcolor="#E8D5B0",linecolor="#E8D5B0"),
                               angularaxis=dict(gridcolor="#E8D5B0")),
                    title="Comparación normalizada de escenarios",
                    legend=dict(orientation="h",y=-0.15,x=0.5,xanchor="center"),
                )
                st.plotly_chart(fig_radar, use_container_width=True)
    else:
        st.markdown("""
        <div class="info-box" style="text-align:center;padding:2rem;">
          <div style="font-size:2.5rem">🔬</div>
          <b>Selecciona escenarios y haz clic en Comparar</b><br>
          <span style="font-size:0.85rem;color:#9B7B5A;">Se simulará cada escenario y se compararán KPIs lado a lado</span>
        </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown(f"""
<div style='text-align:center;color:#C68B59;font-size:0.82rem;
     font-family:Plus Jakarta Sans,sans-serif;padding:0.4rem 0 1rem'>
  🥐 <b>Gemelo Digital — Panadería Dora del Hoyo</b> &nbsp;·&nbsp;
  Planeación Agregada · Desagregación LP · Simulación SimPy · Streamlit
</div>""", unsafe_allow_html=True)
