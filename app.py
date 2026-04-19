"""
app.py  —  Gemelo Digital · Panadería Dora del Hoyo
====================================================
Versión 3.0 — Ultra-enhanced con:
  • Sidebar restructurado por módulos (7 secciones)
  • Parámetros globales: participacion_mercado, litros_por_unidad
  • Mix de demanda ajustable por producto
  • Planeación agregada enriquecida: turnos, eficiencia, ausentismo, flexibilidad
  • Desagregación con parámetros avanzados
  • Simulación con capacidades por recurso, variabilidad, espaciamiento, iteraciones
  • Gráfico combinado Producción + Inventario + Demanda
  • Paleta pastel elegante rediseñada
  • KPIs enriquecidos con litros y cobertura comercial

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
EMOJIS = {
    "Brownies":"🍫","Mantecadas":"🧁",
    "Mantecadas_Amapola":"🌸","Torta_Naranja":"🍊","Pan_Maiz":"🌽",
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
LITROS_UNIDAD_BASE = {"Brownies":0.5,"Mantecadas":0.15,"Mantecadas_Amapola":0.15,"Torta_Naranja":0.8,"Pan_Maiz":0.3}

RUTAS = {
    "Brownies":           [("Mezclado","mezcla",12,18),("Moldeado","dosificado",8,14),("Horneado","horno",30,40),("Enfriamiento","enfriamiento",25,35),("Corte/Empaque","empaque",8,12)],
    "Mantecadas":         [("Mezclado","mezcla",12,18),("Dosificado","dosificado",16,24),("Horneado","horno",20,30),("Enfriamiento","enfriamiento",35,55),("Empaque","empaque",4,6)],
    "Mantecadas_Amapola": [("Mezclado","mezcla",12,18),("Inc. Semillas","mezcla",8,12),("Dosificado","dosificado",16,24),("Horneado","horno",20,30),("Enfriamiento","enfriamiento",36,54),("Empaque","empaque",4,6)],
    "Torta_Naranja":      [("Mezclado","mezcla",16,24),("Dosificado","dosificado",8,12),("Horneado","horno",32,48),("Enfriamiento","enfriamiento",48,72),("Desmolde","dosificado",8,12),("Empaque","empaque",8,12)],
    "Pan_Maiz":           [("Mezclado","mezcla",12,18),("Amasado","amasado",16,24),("Moldeado","dosificado",12,18),("Horneado","horno",28,42),("Enfriamiento","enfriamiento",36,54),("Empaque","empaque",4,6)],
}
TAMANO_LOTE_BASE = {"Brownies":12,"Mantecadas":10,"Mantecadas_Amapola":10,"Torta_Naranja":12,"Pan_Maiz":15}
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
    mdl.solve(PULP_CBC_CMD(msg=False))
    resultados={}
    for p in PRODUCTOS:
        filas=[]
        for idx,t in enumerate(MESES):
            xv=round(X[p,t].varValue or 0,2); iv=round(I[p,t].varValue or 0,2)
            sv=round(S[p,t].varValue or 0,2)
            ini=INV_INICIAL[p] if idx==0 else round(I[p,MESES[idx-1]].varValue or 0,2)
            filas.append({"Mes":t,"Mes_ES":MESES_ES[idx],"Mes_F":MESES_F[idx],
                          "Demanda":dem_hist[p][idx],
                          "Produccion":xv,"Inv_Ini":ini,"Inv_Fin":iv,"Backlog":sv})
        resultados[p]=pd.DataFrame(filas)
    return resultados

@st.cache_data(show_spinner=False)
def run_simulacion_cached(plan_items, cap_items, falla, factor_t,
                          variabilidad=1.0, espaciamiento=1.0, semilla=42):
    plan_unidades=dict(plan_items); cap_recursos=dict(cap_items)
    random.seed(semilla); np.random.seed(semilla)
    lotes_data,uso_rec,sensores=[],[],[]

    def sensor_horno(env,recursos):
        while True:
            ocp=recursos["horno"].count
            temp=round(np.random.normal(160+ocp*20,5*variabilidad),2)
            sensores.append({"tiempo":round(env.now,1),"temperatura":temp,
                             "horno_ocup":ocp,"horno_cola":len(recursos["horno"].queue)})
            yield env.timeout(10)

    def reg_uso(env,recursos,prod=""):
        ts=round(env.now,3)
        for nm,r in recursos.items():
            uso_rec.append({"tiempo":ts,"recurso":nm,"ocupados":r.count,
                            "cola":len(r.queue),"capacidad":r.capacity,"producto":prod})

    def proceso_lote(env,lid,prod,tam,recursos):
        t0=env.now; esperas={}
        for etapa,rec_nm,tmin,tmax in RUTAS[prod]:
            escala=math.sqrt(tam/TAMANO_LOTE_BASE[prod])
            tp=random.uniform(tmin*variabilidad,tmax*variabilidad)*escala*factor_t
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
        tasa=dur_mes/max(n,1)*espaciamiento
        ta=random.expovariate(1/max(tasa,1)); rem=unid
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
    df_lotes   = pd.DataFrame(lotes_data)   if lotes_data   else pd.DataFrame()
    df_uso     = pd.DataFrame(uso_rec)      if uso_rec      else pd.DataFrame()
    df_sensores= pd.DataFrame(sensores)     if sensores     else pd.DataFrame()
    return df_lotes, df_uso, df_sensores

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

def calc_kpis(df_lotes, plan):
    if df_lotes.empty: return pd.DataFrame()
    dur=(df_lotes["t_fin"].max()-df_lotes["t_creacion"].min())/60; filas=[]
    for p in PRODUCTOS:
        sub=df_lotes[df_lotes["producto"]==p]
        if sub.empty: continue
        und=sub["tamano"].sum(); plan_und=plan.get(p,0)
        tp=round(und/max(dur,0.01),3); ct=round((sub["tiempo_sistema"]/sub["tamano"]).mean(),3)
        lt=round(sub["tiempo_sistema"].mean(),3)
        dem_avg=sum(DEM_BASE[p])/12
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
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;600;700&family=DM+Sans:wght@300;400;500;600&display=swap');

/* ── BASE ── */
html, body { background-color: #FFFDF8 !important; color: #46352A !important; }
[class*="css"], .stApp { font-family: 'DM Sans', sans-serif !important; }
.stApp { background-color: #FFFDF8 !important; }
.block-container { background-color: #FFFDF8 !important; padding-top: 1.5rem !important; }

/* ── HERO ── */
.hero {
  background: linear-gradient(135deg, #3D1C02 0%, #8B5E3C 45%, #D4A574 80%, #FCE7A8 100%);
  padding: 2.4rem 3rem 2rem;
  border-radius: 28px;
  margin-bottom: 2rem;
  box-shadow: 0 24px 70px rgba(61,28,2,0.28);
  position: relative; overflow: hidden;
}
.hero::before {
  content: "🥐";
  font-size: 13rem;
  position: absolute; right: 1.5rem; top: -2.5rem;
  opacity: 0.07; transform: rotate(-18deg);
  pointer-events: none;
}
.hero::after {
  content: "";
  position: absolute; inset: 0;
  background: radial-gradient(circle at 75% 50%, rgba(252,231,168,0.15) 0%, transparent 65%);
  border-radius: 28px;
}
.hero h1 {
  font-family: 'Cormorant Garamond', serif;
  color: #FFFDF8; font-size: 2.8rem; margin: 0;
  letter-spacing: -0.5px; font-weight: 700; position: relative; z-index: 1;
}
.hero p { color: #FCE7A8; margin: 0.45rem 0 0; font-size: 0.97rem; font-weight: 300; position: relative; z-index: 1; }
.hero .badge {
  display: inline-block;
  background: rgba(255,255,255,0.13);
  color: #FFFDF8; border: 1px solid rgba(255,255,255,0.25);
  padding: 0.25rem 0.9rem; border-radius: 20px;
  font-size: 0.78rem; margin-top: 0.8rem; margin-right: 0.45rem;
  backdrop-filter: blur(6px); position: relative; z-index: 1;
}

/* ── KPI CARDS ── */
.kpi-card {
  background: #FFFFFF;
  border-radius: 20px;
  padding: 1.3rem 1rem 1.1rem;
  box-shadow: 0 4px 22px rgba(70,53,42,0.07);
  border: 1.5px solid #EADFD7;
  text-align: center;
  transition: transform 0.22s, box-shadow 0.22s;
}
.kpi-card:hover { transform: translateY(-5px); box-shadow: 0 14px 36px rgba(70,53,42,0.14); }
.kpi-card .icon { font-size: 1.9rem; margin-bottom: 0.35rem; }
.kpi-card .val {
  font-family: 'Cormorant Garamond', serif;
  font-size: 2rem; color: #46352A; line-height: 1; margin: 0.18rem 0; font-weight: 700;
}
.kpi-card .lbl { font-size: 0.67rem; color: #B9857E; text-transform: uppercase; letter-spacing: 1.3px; font-weight: 600; }
.kpi-card .sub { font-size: 0.76rem; color: #9B7B5A; margin-top: 0.28rem; }

/* ── SECTION TITLES ── */
.sec-title {
  font-family: 'Cormorant Garamond', serif;
  font-size: 1.4rem; color: #46352A;
  border-left: 4px solid #E8C27A;
  padding-left: 0.85rem;
  margin: 1.8rem 0 0.9rem;
  font-weight: 600;
}

/* ── INFO BOX ── */
.info-box {
  background: linear-gradient(135deg, rgba(252,231,168,0.28), rgba(255,253,248,0.95));
  border: 1px solid rgba(232,194,122,0.5);
  border-radius: 14px;
  padding: 0.9rem 1.15rem;
  font-size: 0.87rem; color: #46352A;
  margin: 0.5rem 0 1rem;
}

/* ── PARAM BOX (nueva) ── */
.param-box {
  background: linear-gradient(135deg, rgba(207,228,246,0.25), rgba(255,253,248,0.95));
  border: 1px solid rgba(207,228,246,0.7);
  border-radius: 14px;
  padding: 0.9rem 1.15rem;
  font-size: 0.86rem; color: #46352A;
  margin: 0.5rem 0 1rem;
}
.param-box b { color: #4A8DB5; }

/* ── PILLS ── */
.pill-ok  { background: #CFE9D9; color: #1B5E20; padding: 0.3rem 1rem; border-radius: 20px; font-size: 0.83rem; font-weight: 600; display: inline-block; }
.pill-warn{ background: #F6C9D0; color: #880E2E; padding: 0.3rem 1rem; border-radius: 20px; font-size: 0.83rem; font-weight: 600; display: inline-block; }

/* ── SIDEBAR ── */
[data-testid="stSidebar"] > div:first-child {
  background-color: #2C1A0E !important;
}
[data-testid="stSidebar"] {
  background-color: #2C1A0E !important;
}
[data-testid="stSidebar"] * { color: #FCE7A8 !important; }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
  color: #E8C27A !important;
  font-family: 'Cormorant Garamond', serif !important;
}
[data-testid="stSidebar"] .stMarkdown p { color: #FCE7A8 !important; }
[data-testid="stSidebar"] hr { border-color: rgba(232,194,122,0.35) !important; }
[data-testid="stSidebar"] [data-baseweb="slider"] div { background: #E8C27A !important; }
[data-testid="stSidebar"] input { background: rgba(255,255,255,0.08) !important; color: #FCE7A8 !important; }
[data-testid="stSidebar"] .stExpander { border-color: rgba(232,194,122,0.3) !important; }
[data-testid="stSidebar"] .stCheckbox label { color: #FCE7A8 !important; }
[data-testid="stSidebar"] [data-baseweb="select"] { background: rgba(255,255,255,0.08) !important; }

/* ── TABS ── */
.stTabs [data-baseweb="tab-list"] {
  background: rgba(234,223,215,0.3);
  border-radius: 12px; padding: 0.2rem;
}
.stTabs [data-baseweb="tab"] {
  font-family: 'DM Sans', sans-serif;
  font-weight: 500; color: #9B7B5A;
  border-radius: 10px; padding: 0.5rem 1rem;
}
.stTabs [aria-selected="true"] {
  color: #46352A !important;
  background: white !important;
  box-shadow: 0 2px 8px rgba(70,53,42,0.12) !important;
}

/* ── EXPANDERS ── */
.streamlit-expanderHeader { color: #46352A !important; font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR — 7 MÓDULOS
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🥐 Dora del Hoyo")
    st.markdown("*Gemelo Digital v3.0*")
    st.markdown("---")
    st.markdown("<div style='font-size:0.75rem;color:#E8C27A;padding:0.3rem 0 0.6rem'>⚙️ Los parámetros globales afectan TODO el modelo. Los específicos de cada módulo solo impactan esa sección.</div>", unsafe_allow_html=True)
    st.markdown("---")

    # ── 1. PARÁMETROS GLOBALES ──────────────────────────────────────────────
    st.markdown("### 🌐 1 · Parámetros Globales")
    mes_idx              = st.selectbox("📅 Mes de análisis", range(12), index=1,
                                         format_func=lambda i: MESES_F[i])
    factor_demanda       = st.slider("📈 Impulso de demanda", 0.5, 2.0, 1.0, 0.05)
    meses_pronostico     = st.slider("🔮 Horizonte de proyección (meses)", 1, 6, 3)
    participacion_mercado= st.slider("🛒 Cobertura comercial (%)", 10, 100, 75, 5)
    litros_por_unidad    = st.slider("🧁 Litros por unidad (promedio)", 0.1, 2.0, 0.35, 0.05)
    semilla              = st.number_input("🎲 Semilla aleatoria", value=42, step=1)
    st.markdown("---")

    # ── 2. DEMANDA — MIX ───────────────────────────────────────────────────
    st.markdown("### 📊 2 · Mix de Demanda")
    with st.expander("🎛️ Ajustar participación por producto"):
        mix_brownies  = st.slider("🍫 Brownies",        0.3, 2.0, 1.0, 0.05)
        mix_mantecadas= st.slider("🧁 Mantecadas",       0.3, 2.0, 1.0, 0.05)
        mix_amapola   = st.slider("🌸 Mant. Amapola",   0.3, 2.0, 1.0, 0.05)
        mix_torta     = st.slider("🍊 Torta Naranja",   0.3, 2.0, 1.0, 0.05)
        mix_panmaiz   = st.slider("🌽 Pan de Maíz",     0.3, 2.0, 1.0, 0.05)
    MIX_FACTORS = {
        "Brownies":mix_brownies,"Mantecadas":mix_mantecadas,
        "Mantecadas_Amapola":mix_amapola,"Torta_Naranja":mix_torta,"Pan_Maiz":mix_panmaiz,
    }
    st.markdown("---")

    # ── 3. PLANEACIÓN AGREGADA ─────────────────────────────────────────────
    st.markdown("### 📋 3 · Planeación Agregada")
    with st.expander("💰 Costos"):
        ct  = st.number_input("Prod/und (Ct)",      value=4_310,   step=100)
        ht  = st.number_input("Inventario (Ht)",    value=100_000, step=1000)
        pit = st.number_input("Backlog (PIt)",      value=100_000, step=1000)
        crt = st.number_input("Hora regular (CRt)", value=11_364,  step=100)
        cot = st.number_input("Hora extra (COt)",   value=14_205,  step=100)
        cwp = st.number_input("Contratar (CW+)",    value=14_204,  step=100)
        cwm = st.number_input("Despedir (CW−)",     value=15_061,  step=100)
    with st.expander("👷 Capacidad laboral"):
        trab        = st.number_input("Trabajadores iniciales", value=10, step=1)
        turnos_dia  = st.slider("Turnos/día",   1, 3, 1)
        horas_turno = st.slider("Horas/turno",  6, 12, 8)
        dias_mes    = st.slider("Días/mes",     18, 26, 22)
    with st.expander("⚙️ Factores estratégicos"):
        eficiencia  = st.slider("Eficiencia (%)",   50, 100, 85, 1)
        ausentismo  = st.slider("Ausentismo (%)",    0,  20,  5, 1)
        flexibilidad= st.slider("Flexibilidad HH (%)", 0, 30, 10, 1)
        stock_obj   = st.slider("Stock seguridad (× demanda)", 0.0, 0.5, 0.0, 0.05)
    st.markdown("---")

    # ── 4. DESAGREGACIÓN ──────────────────────────────────────────────────
    st.markdown("### 📦 4 · Desagregación")
    with st.expander("🔧 Parámetros avanzados"):
        costo_pen_des   = st.number_input("Penalización backlog",   value=150_000, step=5000)
        costo_inv_des   = st.number_input("Costo inventario/und",   value=100_000, step=5000)
        suavizado_des   = st.slider("Suavizado producción",          0, 5000, 500, 100)
        proteccion_mix  = st.checkbox("Proteger proporciones de mix", value=False)
    st.markdown("---")

    # ── 5. SIMULACIÓN OPERATIVA ───────────────────────────────────────────
    st.markdown("### 🏭 5 · Simulación Operativa")
    with st.expander("🏗️ Capacidades por recurso"):
        mezcla_cap      = st.slider("🥣 Mezcla",        1, 6, 2)
        dosificado_cap  = st.slider("🔧 Dosificado",    1, 6, 2)
        cap_horno       = st.slider("🔥 Horno",         1, 8, 3)
        enfriamiento_cap= st.slider("❄️ Enfriamiento",  1, 8, 4)
        empaque_cap     = st.slider("📦 Empaque",       1, 6, 2)
        amasado_cap     = st.slider("👐 Amasado",       1, 4, 1)
    with st.expander("🎛️ Parámetros de simulación"):
        falla_horno     = st.checkbox("⚠️ Fallas en horno")
        doble_turno     = st.checkbox("🕐 Doble turno (−20% tiempo)")
        variabilidad    = st.slider("📉 Variabilidad tiempos",   0.5, 2.0, 1.0, 0.1)
        espaciamiento   = st.slider("📏 Espaciamiento lotes",    0.5, 2.0, 1.0, 0.1)
        iter_sim        = st.slider("🔁 Iteraciones simulación", 1, 5, 1)
    st.markdown("---")

    st.markdown("<div style='font-size:0.73rem;color:#E8C27A;'>📍 Panadería Dora del Hoyo<br>🔢 SimPy · PuLP · Streamlit v3</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PRE-CÁLCULOS GLOBALES
# ══════════════════════════════════════════════════════════════════════════════
# Demanda ajustada por mix y factor global
DEM_HIST = get_demanda_historica(MIX_FACTORS, factor_demanda)

# Capacidad laboral efectiva
factor_ef   = (eficiencia/100)*(1-ausentismo/100)*(1+flexibilidad/100)
hh_por_mes  = trab * turnos_dia * horas_turno * dias_mes * factor_ef
LR_inicial  = hh_por_mes

params_custom = {
    "Ct":ct,"Ht":ht,"PIt":pit,"CRt":crt,"COt":cot,
    "CW_mas":cwp,"CW_menos":cwm,"M":1,
    "LR_inicial":round(LR_inicial,2),"stock_obj":stock_obj,
}

dem_h = demanda_horas_hombre(DEM_HIST)

# ── Agregación ─────────────────────────────────────────────────────────────
with st.spinner("⚙️ Optimizando plan agregado..."):
    df_agr, costo = run_agregacion(
        tuple(dem_h.items()), tuple(sorted(params_custom.items()))
    )

prod_hh = dict(zip(df_agr["Mes"], df_agr["Produccion_HH"]))

# ── Desagregación ──────────────────────────────────────────────────────────
# Convertir dem_hist a serializable
dem_hist_items = tuple((p, tuple(DEM_HIST[p])) for p in PRODUCTOS)
with st.spinner("🔢 Desagregando por producto..."):
    desag = run_desagregacion(
        tuple(prod_hh.items()), dem_hist_items,
        costo_pen_des, costo_inv_des, suavizado_des, proteccion_mix
    )

# ── Simulación ─────────────────────────────────────────────────────────────
mes_nm   = MESES[mes_idx]
plan_mes = {p:int(desag[p].loc[desag[p]["Mes"]==mes_nm,"Produccion"].values[0]) for p in PRODUCTOS}
cap_rec  = {"mezcla":mezcla_cap,"dosificado":dosificado_cap,"horno":cap_horno,
            "enfriamiento":enfriamiento_cap,"empaque":empaque_cap,"amasado":amasado_cap}
factor_t = 0.80 if doble_turno else 1.0

with st.spinner("🏭 Simulando planta de producción..."):
    df_lotes,df_uso,df_sensores = run_simulacion_cached(
        tuple(plan_mes.items()), tuple(cap_rec.items()), falla_horno,
        factor_t, variabilidad, espaciamiento, int(semilla)
    )

df_kpis = calc_kpis(df_lotes, plan_mes)
df_util  = calc_utilizacion(df_uso)

# ══════════════════════════════════════════════════════════════════════════════
# HERO
# ══════════════════════════════════════════════════════════════════════════════
prod_total   = sum(desag[p]["Produccion"].sum() for p in PRODUCTOS)
litros_total = round(prod_total * litros_por_unidad, 1)
cob_comercial= round(participacion_mercado/100, 2)

st.markdown(f"""
<div class="hero">
  <h1>Gemelo Digital — Panadería Dora del Hoyo</h1>
  <p>Optimización LP · Simulación de Eventos Discretos · Análisis What-If en tiempo real</p>
  <span class="badge">📅 {MESES_F[mes_idx]}</span>
  <span class="badge">📈 Demanda ×{factor_demanda}</span>
  <span class="badge">🛒 Cobertura {participacion_mercado}%</span>
  <span class="badge">🧁 {litros_total:,.0f} L proyectados</span>
  <span class="badge">🔥 Horno: {cap_horno} est.</span>
  {"<span class='badge'>⚠️ Falla activa</span>" if falla_horno else ""}
  {"<span class='badge'>🕐 Doble turno</span>" if doble_turno else ""}
</div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# KPIs SUPERIORES
# ══════════════════════════════════════════════════════════════════════════════
cum_avg  = df_kpis["Cumplimiento %"].mean() if not df_kpis.empty else 0
util_max = df_util["Utilizacion_%"].max()   if not df_util.empty else 0
lotes_n  = len(df_lotes) if not df_lotes.empty else 0
temp_avg = df_sensores["temperatura"].mean() if not df_sensores.empty else 0
excesos  = int((df_sensores["temperatura"]>200).sum()) if not df_sensores.empty else 0

k1,k2,k3,k4,k5,k6 = st.columns(6)
def kpi_card(col, icon, val, lbl, sub=""):
    col.markdown(f"""
    <div class="kpi-card">
      <div class="icon">{icon}</div>
      <div class="val">{val}</div>
      <div class="lbl">{lbl}</div>
      {"<div class='sub'>"+sub+"</div>" if sub else ""}
    </div>""", unsafe_allow_html=True)

kpi_card(k1,"💰",f"${costo/1e6:.1f}M","Costo Óptimo","COP · Plan anual")
kpi_card(k2,"🧁",f"{litros_total:,.0f}L","Volumen Anual",f"×{litros_por_unidad} L/und")
kpi_card(k3,"🛒",f"{participacion_mercado}%","Cobertura Comercial",f"{prod_total:,.0f} und/año")
kpi_card(k4,"✅",f"{cum_avg:.1f}%","Cumplimiento Sim.",MESES_F[mes_idx])
kpi_card(k5,"⚙️",f"{util_max:.0f}%","Util. Máx. Recurso",
         "⚠️ Cuello botella" if util_max>=80 else "✓ OK")
kpi_card(k6,"🌡️",f"{temp_avg:.0f}°C","Temp. Horno Prom.",
         f"⚠️ {excesos} excesos" if excesos else "✓ Sin excesos")

st.markdown("<br>", unsafe_allow_html=True)

PLOT_CFG = dict(
    template="plotly_white",
    font=dict(family="DM Sans", color="#46352A"),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(255,253,248,0.5)",
)

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tabs = st.tabs(["📊 Demanda & Pronóstico","📋 Plan Agregado",
                "📦 Desagregación","🏭 Simulación","🌡️ Sensores","🔬 Escenarios"])

# ────────────────────────────────────────────────────────────────────────────
# TAB 1 — DEMANDA & PRONÓSTICO
# ────────────────────────────────────────────────────────────────────────────
with tabs[0]:
    st.markdown('<div class="sec-title">📈 Demanda histórica y pronóstico por producto</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Datos ajustados por mix de producto y factor de impulso global · Suavizado exponencial α=0.3 · Las líneas punteadas representan la proyección futura.</div>', unsafe_allow_html=True)

    # ── PARÁMETROS PROPIOS DE DEMANDA ─────────────────────────────────────
    with st.expander("🎛️ Parámetros de Demanda & Proyección — activos en esta sección", expanded=False):
        st.markdown('<div class="param-box"><b>Mix de productos:</b> cambian el peso relativo de cada producto. Simulan promociones, estacionalidad o cambios de preferencia del cliente. Solo afectan la demanda base (no costos ni producción directamente).</div>', unsafe_allow_html=True)
        pc1, pc2, pc3 = st.columns(3)
        with pc1:
            st.markdown("**🍫 Mix por producto**")
            st.metric("Brownies",      f"×{mix_brownies:.2f}")
            st.metric("Mantecadas",    f"×{mix_mantecadas:.2f}")
            st.metric("Mant. Amapola", f"×{mix_amapola:.2f}")
            st.metric("Torta Naranja", f"×{mix_torta:.2f}")
            st.metric("Pan de Maíz",   f"×{mix_panmaiz:.2f}")
        with pc2:
            st.markdown("**📈 Impulso global**")
            st.metric("Factor de demanda", f"×{factor_demanda:.2f}")
            st.metric("Horizonte pronóstico", f"{meses_pronostico} meses")
        with pc3:
            st.markdown("**📊 Resultado**")
            total_dem = sum(sum(DEM_HIST[p]) for p in PRODUCTOS)
            st.metric("Demanda total anual", f"{total_dem:,.0f} und")
            st.metric("Productos activos", f"{len(PRODUCTOS)}")
        st.caption("💡 Ajusta mix_brownies, mix_mantecadas, mix_tortas, factor_demanda y meses_pronostico en la barra lateral izquierda para modificar estos valores.")

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
            marker=dict(size=10,symbol="circle",color=PROD_COLORS[p],
                        line=dict(color=PROD_COLORS_DARK[p],width=2)),
            legendgroup=p,showlegend=False,
        ))
    fig_pro.add_vline(x=len(MESES_ES)-1,line_dash="dot",line_color="#E8C27A",
                      annotation_text="▶ Pronóstico",annotation_font_color="#E8C27A",
                      annotation_position="top right")
    fig_pro.update_layout(**PLOT_CFG,height=400,
                          title="Demanda & Proyección — Panadería Dora del Hoyo",
                          xaxis_title="Mes",yaxis_title="Unidades",
                          legend=dict(orientation="h",y=-0.22,x=0.5,xanchor="center"),
                          xaxis=dict(showgrid=True,gridcolor="#F0E8D8"),
                          yaxis=dict(showgrid=True,gridcolor="#F0E8D8"))
    st.plotly_chart(fig_pro,use_container_width=True)

    col_a,col_b=st.columns(2)
    with col_a:
        st.markdown('<div class="sec-title">🔥 Mapa de calor — Estacionalidad</div>', unsafe_allow_html=True)
        z=[[DEM_HIST[p][i] for i in range(12)] for p in PRODUCTOS]
        fig_heat=go.Figure(go.Heatmap(
            z=z,x=MESES_ES,y=[PROD_LABELS[p] for p in PRODUCTOS],
            colorscale=[[0,"#FFFDF8"],[0.3,"#FCE7A8"],[0.65,"#E8C27A"],[1,"#8B5E3C"]],
            hovertemplate="%{y}<br>%{x}: %{z:.0f} und<extra></extra>",
            text=[[f"{int(v)}" for v in row] for row in z],
            texttemplate="%{text}",textfont=dict(size=9,color="#46352A"),
        ))
        fig_heat.update_layout(**PLOT_CFG,height=250,margin=dict(t=20,b=10))
        st.plotly_chart(fig_heat,use_container_width=True)

    with col_b:
        st.markdown('<div class="sec-title">🌸 Participación anual de ventas</div>', unsafe_allow_html=True)
        totales={p:sum(DEM_HIST[p]) for p in PRODUCTOS}
        fig_pie=go.Figure(go.Pie(
            labels=[PROD_LABELS[p] for p in PRODUCTOS],
            values=list(totales.values()),hole=0.55,
            marker=dict(colors=list(PROD_COLORS.values()),line=dict(color="white",width=3)),
            textfont=dict(size=11),
            hovertemplate="%{label}<br>%{value:,.0f} und/año<br>%{percent}<extra></extra>",
        ))
        fig_pie.update_layout(**PLOT_CFG,height=250,margin=dict(t=10,b=10),
                              annotations=[dict(text="<b>Mix</b><br>anual",x=0.5,y=0.5,
                                                font=dict(size=11,color="#46352A"),showarrow=False)],
                              legend=dict(orientation="v",x=1,y=0.5,font=dict(size=11)))
        st.plotly_chart(fig_pie,use_container_width=True)

    st.markdown('<div class="sec-title">⏱️ Demanda total en Horas-Hombre por mes</div>', unsafe_allow_html=True)
    colores_hh=[C["butter"] if i!=mes_idx else C["mocha"] for i in range(12)]
    fig_hh=go.Figure()
    fig_hh.add_trace(go.Bar(x=MESES_ES,y=list(dem_h.values()),
                            marker_color=colores_hh,marker_line_color="white",marker_line_width=1.5,
                            hovertemplate="%{x}: %{y:.1f} H-H<extra></extra>",showlegend=False))
    fig_hh.add_trace(go.Scatter(x=MESES_ES,y=list(dem_h.values()),mode="lines+markers",
                                line=dict(color=C["mocha"],width=2),marker=dict(size=6),showlegend=False))
    fig_hh.add_hline(y=LR_inicial,line_dash="dash",line_color="#8B5E3C",
                     annotation_text=f"Capacidad: {LR_inicial:,.0f} H-H",
                     annotation_font_color="#8B5E3C")
    fig_hh.update_layout(**PLOT_CFG,height=270,xaxis_title="Mes",yaxis_title="H-H",
                         xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"),
                         margin=dict(t=20,b=20))
    st.plotly_chart(fig_hh,use_container_width=True)

# ────────────────────────────────────────────────────────────────────────────
# TAB 2 — PLAN AGREGADO
# ────────────────────────────────────────────────────────────────────────────
with tabs[1]:
    st.markdown('<div class="sec-title">📋 Planeación Agregada — Optimización LP (PuLP)</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="info-box"><b>{trab} trabajadores</b> · {turnos_dia} turno(s)/día · {horas_turno}h/turno · {dias_mes} días/mes<br>'
                f'Eficiencia efectiva: <b>{factor_ef*100:.1f}%</b> → Capacidad: <b>{LR_inicial:,.0f} H-H/mes</b> · Stock seguridad: {stock_obj*100:.0f}%</div>',
                unsafe_allow_html=True)

    # ── PARÁMETROS PROPIOS DE AGREGACIÓN ──────────────────────────────────
    with st.expander("⚙️ Parámetros de Planeación Agregada — activos en esta sección", expanded=False):
        st.markdown('<div class="param-box"><b>Corazón matemático del modelo (optimización LP):</b> Los costos penalizan producción, inventario y backlog. La capacidad laboral determina las horas-hombre disponibles. Los factores estratégicos ajustan la realidad operativa.</div>', unsafe_allow_html=True)
        pa1, pa2, pa3 = st.columns(3)
        with pa1:
            st.markdown("**💰 Costos (COP)**")
            st.metric("Prod/und (Ct)",      f"${ct:,}")
            st.metric("Inventario (Ht)",    f"${ht:,}")
            st.metric("Backlog (PIt)",      f"${pit:,}")
            st.metric("Hora regular (CRt)", f"${crt:,}")
            st.metric("Hora extra (COt)",   f"${cot:,}")
            st.metric("Contratar (CW+)",    f"${cwp:,}")
            st.metric("Despedir (CW−)",     f"${cwm:,}")
        with pa2:
            st.markdown("**👷 Capacidad Laboral**")
            st.metric("Trabajadores",   f"{trab}")
            st.metric("Turnos/día",     f"{turnos_dia}")
            st.metric("Horas/turno",    f"{horas_turno}h")
            st.metric("Días/mes",       f"{dias_mes}")
            st.metric("Cap. efectiva",  f"{LR_inicial:,.0f} H-H/mes")
        with pa3:
            st.markdown("**⚡ Factores Estratégicos**")
            st.metric("Eficiencia",          f"{eficiencia}%")
            st.metric("Ausentismo",          f"{ausentismo}%")
            st.metric("Flexibilidad HH",     f"{flexibilidad}%")
            st.metric("Stock seguridad",     f"{stock_obj*100:.0f}% demanda")
            st.metric("Factor efectivo total", f"{factor_ef*100:.1f}%")
        st.caption("💡 Modifica estos parámetros en la barra lateral sección '3 · Planeación Agregada'.")

    m1,m2,m3,m4=st.columns(4)
    m1.metric("💰 Costo Total",    f"${costo:,.0f} COP")
    m2.metric("⏰ Horas Extra",     f"{df_agr['Horas_Extras'].sum():,.0f} H-H")
    m3.metric("📉 Backlog Total",   f"{df_agr['Backlog_HH'].sum():,.0f} H-H")
    m4.metric("👥 Contrat. Netas", f"{df_agr['Contratacion'].sum()-df_agr['Despidos'].sum():+.0f} pers.")

    st.markdown('<div class="sec-title">📊 Producción vs Demanda (H-H)</div>', unsafe_allow_html=True)
    fig_agr=go.Figure()
    fig_agr.add_trace(go.Bar(x=df_agr["Mes_ES"],y=df_agr["Inv_Ini_HH"],name="Inv. Inicial H-H",
                             marker_color=C["sky"],opacity=0.8,marker_line_color="white",marker_line_width=1))
    fig_agr.add_trace(go.Bar(x=df_agr["Mes_ES"],y=df_agr["Produccion_HH"],name="Producción H-H",
                             marker_color=C["butter"],opacity=0.9,marker_line_color="white",marker_line_width=1))
    fig_agr.add_trace(go.Scatter(x=df_agr["Mes_ES"],y=df_agr["Demanda_HH"],mode="lines+markers",
                                 name="Demanda H-H",line=dict(color=C["mocha"],dash="dash",width=2.5),
                                 marker=dict(size=8,color=C["mocha"])))
    fig_agr.add_trace(go.Scatter(x=df_agr["Mes_ES"],y=df_agr["Horas_Regulares"],mode="lines",
                                 name="Cap. Regular",line=dict(color=C["rose_d"],dash="dot",width=2)))
    fig_agr.update_layout(**PLOT_CFG,barmode="stack",height=370,
                          title=f"Costo Óptimo LP: COP ${costo:,.0f}",
                          xaxis_title="Mes",yaxis_title="Horas-Hombre",
                          legend=dict(orientation="h",y=-0.22,x=0.5,xanchor="center"),
                          xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"))
    st.plotly_chart(fig_agr,use_container_width=True)

    col1,col2=st.columns(2)
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
        st.plotly_chart(fig_fl,use_container_width=True)

    with col2:
        st.markdown('<div class="sec-title">⚡ Horas Extra & Backlog</div>', unsafe_allow_html=True)
        fig_ex=go.Figure()
        fig_ex.add_trace(go.Bar(x=df_agr["Mes_ES"],y=df_agr["Horas_Extras"],name="Horas Extra",
                                marker_color=C["peach"],marker_line_color="white",marker_line_width=1))
        fig_ex.add_trace(go.Bar(x=df_agr["Mes_ES"],y=df_agr["Backlog_HH"],name="Backlog",
                                marker_color=C["rose"],marker_line_color="white",marker_line_width=1))
        fig_ex.update_layout(**PLOT_CFG,barmode="group",height=290,
                             legend=dict(orientation="h",y=-0.3,x=0.5,xanchor="center"),
                             xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"))
        st.plotly_chart(fig_ex,use_container_width=True)

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
    st.markdown(f'<div class="info-box">Plan en H-H convertido a unidades via LP · Suavizado: {suavizado_des} · '
                f'Penalización backlog: ${costo_pen_des:,} · Inventario: ${costo_inv_des:,}</div>', unsafe_allow_html=True)

    # ── PARÁMETROS PROPIOS DE DESAGREGACIÓN ───────────────────────────────
    with st.expander("🔧 Parámetros de Desagregación — activos en esta sección", expanded=False):
        st.markdown('<div class="param-box"><b>Baja el plan agregado a nivel de producto individual:</b> aquí decides si priorizas servicio (bajo backlog) o eficiencia de inventario, y si quieres estabilidad o agresividad en los cambios de producción.</div>', unsafe_allow_html=True)
        pd1, pd2 = st.columns(2)
        with pd1:
            st.markdown("**📦 Penalizaciones**")
            st.metric("Penalización backlog", f"${costo_pen_des:,}", help="Mayor valor → prioriza cumplir demanda")
            st.metric("Costo inventario/und", f"${costo_inv_des:,}", help="Mayor valor → reduce inventario")
            st.metric("Suavizado producción", f"{suavizado_des}", help="Mayor valor → evita cambios bruscos")
        with pd2:
            st.markdown("**🎯 Estrategia**")
            _ratio = costo_pen_des / max(costo_inv_des, 1)
            st.metric("Ratio backlog/inventario", f"{_ratio:.1f}×",
                      delta="Orientado a servicio" if _ratio > 1 else "Orientado a inventario")
            st.metric("Protección de mix", "✓ Activa" if proteccion_mix else "✗ Libre")
        st.caption("💡 Modifica estos parámetros en la barra lateral sección '4 · Desagregación'.")

    mes_resaltar=st.selectbox("Mes a resaltar ★",range(12),index=mes_idx,format_func=lambda i:MESES_F[i],key="mes_desag")
    mes_nm_desag=MESES[mes_resaltar]

    # ── GRÁFICO CONSOLIDADO: TODOS LOS PRODUCTOS ─────────────────────────
    st.markdown('<div class="sec-title">🌟 Vista Global — Producción, Inventario & Demanda (todos los productos)</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Consolidado anual de los tres flujos críticos del negocio para <b>todos los productos</b>. Compara la producción total vs demanda total y observa el comportamiento del inventario mes a mes.</div>', unsafe_allow_html=True)

    # Calcular consolidados
    meses_es = MESES_ES
    prod_total_mes   = [sum(desag[p].loc[desag[p]["Mes"]==m,"Produccion"].values[0] for p in PRODUCTOS) for m in MESES]
    dem_total_mes    = [sum(desag[p].loc[desag[p]["Mes"]==m,"Demanda"].values[0]    for p in PRODUCTOS) for m in MESES]
    inv_total_mes    = [sum(desag[p].loc[desag[p]["Mes"]==m,"Inv_Fin"].values[0]    for p in PRODUCTOS) for m in MESES]
    backlog_total    = [sum(desag[p].loc[desag[p]["Mes"]==m,"Backlog"].values[0]    for p in PRODUCTOS) for m in MESES]

    fig_global = make_subplots(
        rows=3, cols=1,
        row_heights=[0.45, 0.28, 0.27],
        shared_xaxes=True,
        vertical_spacing=0.06,
        subplot_titles=[
            "📦 Producción vs Demanda Total (unidades)",
            "🗄️ Inventario Final Consolidado",
            "⚠️ Backlog Total",
        ]
    )

    # ── Fila 1: Producción (barras) + Demanda (línea) ──
    colores_meses = [C["gold"] if i==mes_idx else C["butter"] for i in range(12)]
    fig_global.add_trace(go.Bar(
        x=meses_es, y=prod_total_mes,
        name="Producción", marker_color=colores_meses, opacity=0.88,
        marker_line_color=C["mocha"], marker_line_width=1.2,
        hovertemplate="%{x}: <b>%{y:,.0f} und</b> producidas<extra></extra>",
    ), row=1, col=1)
    fig_global.add_trace(go.Scatter(
        x=meses_es, y=dem_total_mes,
        name="Demanda", mode="lines+markers",
        line=dict(color=C["rose_d"], width=3, dash="dash"),
        marker=dict(size=9, color=C["rose"], line=dict(color=C["rose_d"], width=2)),
        hovertemplate="%{x}: <b>%{y:,.0f} und</b> demanda<extra></extra>",
    ), row=1, col=1)
    # Brecha fill
    fig_global.add_trace(go.Scatter(
        x=meses_es, y=prod_total_mes,
        fill=None, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip",
    ), row=1, col=1)
    fig_global.add_trace(go.Scatter(
        x=meses_es, y=dem_total_mes,
        fill="tonexty", fillcolor=hex_rgba(C["rose"], 0.12),
        mode="lines", line=dict(width=0), name="Brecha", showlegend=True, hoverinfo="skip",
    ), row=1, col=1)
    # Marker mes seleccionado
    fig_global.add_trace(go.Scatter(
        x=[meses_es[mes_idx]], y=[prod_total_mes[mes_idx]],
        mode="markers", marker=dict(size=18, color=C["gold"], symbol="star",
                                     line=dict(color=C["mocha"], width=2)),
        name=f"★ {MESES_F[mes_idx]}", showlegend=True,
    ), row=1, col=1)

    # ── Fila 2: Inventario ──
    fig_global.add_trace(go.Scatter(
        x=meses_es, y=inv_total_mes,
        fill="tozeroy", mode="lines+markers",
        fillcolor=hex_rgba(C["mint"], 0.38),
        line=dict(color="#5BAF7A", width=2.5),
        marker=dict(size=8, color="#5BAF7A", line=dict(color="#2D7A4F", width=1.5)),
        name="Inventario Final",
        hovertemplate="%{x}: <b>%{y:,.0f} und</b> en inventario<extra></extra>",
    ), row=2, col=1)

    # ── Fila 3: Backlog ──
    colores_bl = [C["rose"] if v > 0 else C["mint"] for v in backlog_total]
    fig_global.add_trace(go.Bar(
        x=meses_es, y=backlog_total,
        name="Backlog", marker_color=colores_bl, opacity=0.85,
        marker_line_color="white", marker_line_width=1,
        hovertemplate="%{x}: <b>%{y:,.0f} und</b> backlog<extra></extra>",
    ), row=3, col=1)

    fig_global.update_layout(
        **PLOT_CFG, height=620, barmode="group",
        title=dict(text="Flujos de Producción, Inventario & Demanda — Vista Anual Consolidada",
                   font=dict(family="Cormorant Garamond", size=16, color="#46352A")),
        legend=dict(orientation="h", y=-0.08, x=0.5, xanchor="center",
                    bgcolor="rgba(255,253,248,0.8)", bordercolor=C["border"], borderwidth=1),
        margin=dict(t=70, b=20),
    )
    fig_global.update_xaxes(showgrid=False)
    fig_global.update_yaxes(gridcolor="#F0E8D8", row=1, col=1, title_text="Unidades")
    fig_global.update_yaxes(gridcolor="#F0E8D8", row=2, col=1, title_text="Und inv.")
    fig_global.update_yaxes(gridcolor="#F0E8D8", row=3, col=1, title_text="Und backlog")
    st.plotly_chart(fig_global, use_container_width=True)

    # ── Métricas resumen rápido ──────────────────────────────────────────
    mg1, mg2, mg3, mg4 = st.columns(4)
    mg1.metric("📦 Producción total anual",  f"{sum(prod_total_mes):,.0f} und")
    mg2.metric("📈 Demanda total anual",     f"{sum(dem_total_mes):,.0f} und")
    mg3.metric("🗄️ Inv. promedio mensual",   f"{sum(inv_total_mes)/12:,.0f} und")
    mg4.metric("⚠️ Backlog total",           f"{sum(backlog_total):,.0f} und",
               delta="OK" if sum(backlog_total)==0 else f"⚠️ {sum(backlog_total):,.0f}")

    st.markdown("---")

    # ── Gráfico COMBINADO: Producción + Inventario + Demanda ──────────────
    st.markdown('<div class="sec-title">📊 Análisis por producto — Producción · Inventario · Demanda</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Vista detallada de los tres flujos críticos para un producto específico: qué se produce, qué queda en inventario y cuánto se demanda, mes a mes.</div>', unsafe_allow_html=True)

    prod_sel_combo = st.selectbox("Producto a analizar", PRODUCTOS, format_func=lambda p: PROD_LABELS[p], key="combo_prod")
    df_combo = desag[prod_sel_combo]
    pc = PROD_COLORS[prod_sel_combo]; pcd = PROD_COLORS_DARK[prod_sel_combo]

    fig_combo = make_subplots(
        rows=2, cols=1, row_heights=[0.65, 0.35],
        shared_xaxes=True, vertical_spacing=0.08,
        subplot_titles=[f"Producción & Demanda — {PROD_LABELS[prod_sel_combo]}",
                        "Inventario Final"]
    )
    # Barras de producción
    fig_combo.add_trace(go.Bar(
        x=df_combo["Mes_ES"], y=df_combo["Produccion"],
        name="Producción", marker_color=pc, opacity=0.85,
        marker_line_color=pcd, marker_line_width=1.5,
        hovertemplate="%{x}: <b>%{y:.0f} und</b> producidas<extra></extra>",
    ), row=1, col=1)
    # Línea de demanda
    fig_combo.add_trace(go.Scatter(
        x=df_combo["Mes_ES"], y=df_combo["Demanda"],
        name="Demanda", mode="lines+markers",
        line=dict(color=pcd, width=2.5, dash="dash"),
        marker=dict(size=9, color=pc, line=dict(color=pcd, width=2)),
        hovertemplate="%{x}: <b>%{y:.0f} und</b> demanda<extra></extra>",
    ), row=1, col=1)
    # Brecha (fill entre producción y demanda)
    fig_combo.add_trace(go.Scatter(
        x=df_combo["Mes_ES"], y=df_combo["Produccion"],
        fill=None, mode="lines", line=dict(width=0),
        showlegend=False, hoverinfo="skip",
    ), row=1, col=1)
    fig_combo.add_trace(go.Scatter(
        x=df_combo["Mes_ES"], y=df_combo["Demanda"],
        fill="tonexty",
        fillcolor=hex_rgba(pc, 0.18),
        mode="lines", line=dict(width=0),
        name="Brecha", showlegend=True,
        hoverinfo="skip",
    ), row=1, col=1)
    # Resaltar mes seleccionado
    mes_row_c = df_combo[df_combo["Mes"]==mes_nm_desag]
    if not mes_row_c.empty:
        fig_combo.add_trace(go.Scatter(
            x=[MESES_ES[mes_resaltar]], y=[mes_row_c["Produccion"].values[0]],
            mode="markers", marker=dict(size=16, color=C["gold"], symbol="star",
                                         line=dict(color=pcd, width=2)),
            name=f"★ {MESES_F[mes_resaltar]}", showlegend=True,
        ), row=1, col=1)
    # Inventario final (área)
    fig_combo.add_trace(go.Scatter(
        x=df_combo["Mes_ES"], y=df_combo["Inv_Fin"],
        fill="tozeroy", mode="lines+markers",
        fillcolor=hex_rgba(C["mint"], 0.35),
        line=dict(color="#5BAF7A", width=2),
        marker=dict(size=7, color="#5BAF7A"),
        name="Inventario Final",
        hovertemplate="%{x}: %{y:.0f} und en inventario<extra></extra>",
    ), row=2, col=1)
    # Backlog
    if df_combo["Backlog"].sum() > 0:
        fig_combo.add_trace(go.Bar(
            x=df_combo["Mes_ES"], y=df_combo["Backlog"],
            name="Backlog", marker_color=C["rose"], opacity=0.8,
            hovertemplate="%{x}: %{y:.0f} und backlog<extra></extra>",
        ), row=2, col=1)
    fig_combo.update_layout(
        **PLOT_CFG, height=500, barmode="group",
        legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center"),
        margin=dict(t=60, b=20),
    )
    fig_combo.update_xaxes(showgrid=False)
    fig_combo.update_yaxes(gridcolor="#F0E8D8", row=1, col=1)
    fig_combo.update_yaxes(gridcolor="#F0E8D8", row=2, col=1)
    st.plotly_chart(fig_combo, use_container_width=True)

    # ── Subgráficas por producto ──────────────────────────────────────────
    st.markdown('<div class="sec-title">📐 Plan desagregado — Todos los productos</div>', unsafe_allow_html=True)
    fig_des=make_subplots(rows=3,cols=2,
                          subplot_titles=[PROD_LABELS[p] for p in PRODUCTOS],
                          vertical_spacing=0.12,horizontal_spacing=0.08)
    for idx,p in enumerate(PRODUCTOS):
        r,c=idx//2+1,idx%2+1; df_p=desag[p]
        fig_des.add_trace(go.Bar(x=df_p["Mes_ES"],y=df_p["Produccion"],
                                 marker_color=PROD_COLORS[p],opacity=0.88,showlegend=False,
                                 marker_line_color="white",marker_line_width=1),row=r,col=c)
        fig_des.add_trace(go.Scatter(x=df_p["Mes_ES"],y=df_p["Demanda"],mode="lines+markers",
                                     line=dict(color=PROD_COLORS_DARK[p],dash="dash",width=1.5),
                                     marker=dict(size=5),showlegend=False),row=r,col=c)
        mes_row=df_p[df_p["Mes"]==mes_nm_desag]
        if not mes_row.empty:
            fig_des.add_trace(go.Scatter(x=[MESES_ES[mes_resaltar]],
                                         y=[mes_row["Produccion"].values[0]],
                                         mode="markers",marker=dict(size=14,color=C["gold"],symbol="star"),
                                         showlegend=False),row=r,col=c)
    fig_des.update_layout(**PLOT_CFG,height=680,barmode="group",margin=dict(t=60))
    for i in range(1,4):
        for j in range(1,3):
            fig_des.update_xaxes(showgrid=False,row=i,col=j)
            fig_des.update_yaxes(gridcolor="#F0E8D8",row=i,col=j)
    st.plotly_chart(fig_des,use_container_width=True)

    # ── Cobertura & inventario ──────────────────────────────────────────
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
                                  marker=dict(color=list(PROD_COLORS.values()),
                                              line=dict(color=list(PROD_COLORS_DARK.values()),width=1.5)),
                                  text=[f"{v:.1f}%" for v in cob_vals],textposition="inside",
                                  textfont=dict(color="#46352A",size=12)))
        fig_cob.add_vline(x=100,line_dash="dash",line_color=C["mocha"],
                          annotation_text="Meta 100%",annotation_font_color=C["mocha"])
        fig_cob.update_layout(**PLOT_CFG,height=280,xaxis_title="Cobertura (%)",
                              xaxis=dict(range=[0,115]),yaxis=dict(showgrid=False),
                              margin=dict(t=20,b=20),showlegend=False)
        st.plotly_chart(fig_cob,use_container_width=True)
    with col_cob2:
        df_cob=pd.DataFrame({"Producto":prods_c,"Producido":und_prod,"Demanda":und_dem,"Cob %":cob_vals})
        st.dataframe(df_cob.style.format({"Producido":"{:,.0f}","Demanda":"{:,.0f}","Cob %":"{:.1f}%"})
                     .background_gradient(subset=["Cob %"],cmap="YlGn"),
                     use_container_width=True,height=280)

    st.markdown('<div class="sec-title">📦 Inventario final proyectado — todos los productos</div>', unsafe_allow_html=True)
    fig_inv=go.Figure()
    for p in PRODUCTOS:
        fig_inv.add_trace(go.Scatter(x=desag[p]["Mes_ES"],y=desag[p]["Inv_Fin"],
                                     name=PROD_LABELS[p],mode="lines+markers",
                                     line=dict(color=PROD_COLORS_DARK[p],width=2),
                                     marker=dict(size=7,color=PROD_COLORS[p],
                                                 line=dict(color=PROD_COLORS_DARK[p],width=1.5)),
                                     fill="tozeroy",fillcolor=hex_rgba(PROD_COLORS[p],0.16)))
    fig_inv.update_layout(**PLOT_CFG,height=280,xaxis_title="Mes",yaxis_title="Unidades en inventario",
                          legend=dict(orientation="h",y=-0.28,x=0.5,xanchor="center"),
                          xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"))
    st.plotly_chart(fig_inv,use_container_width=True)

# ────────────────────────────────────────────────────────────────────────────
# TAB 4 — SIMULACIÓN
# ────────────────────────────────────────────────────────────────────────────
with tabs[3]:
    st.markdown(f'<div class="sec-title">🏭 Simulación de Planta — {MESES_F[mes_idx]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="info-box">SimPy · Variabilidad: {variabilidad}× · Espaciamiento lotes: {espaciamiento}× · '
                f'Capacidades: Mezcla={mezcla_cap} | Dosificado={dosificado_cap} | Horno={cap_horno} | '
                f'Enfriamiento={enfriamiento_cap} | Empaque={empaque_cap} | Amasado={amasado_cap}</div>', unsafe_allow_html=True)

    # ── PARÁMETROS PROPIOS DE SIMULACIÓN ──────────────────────────────────
    with st.expander("🏗️ Parámetros de Simulación Operativa — activos en esta sección", expanded=False):
        st.markdown('<div class="param-box"><b>Gemelo digital de la planta:</b> simula cuellos de botella, tiempos reales, saturación y comportamiento dinámico. Aquí vive lo más potente del modelo.</div>', unsafe_allow_html=True)
        ps1, ps2, ps3 = st.columns(3)
        with ps1:
            st.markdown("**🏗️ Capacidades por recurso**")
            st.metric("🥣 Mezcla",        f"{mezcla_cap} est.")
            st.metric("🔧 Dosificado",    f"{dosificado_cap} est.")
            st.metric("🔥 Horno",         f"{cap_horno} est.", delta="⚠️ Crítico" if cap_horno <= 2 else "OK")
            st.metric("❄️ Enfriamiento",  f"{enfriamiento_cap} est.")
            st.metric("📦 Empaque",       f"{empaque_cap} est.")
            st.metric("👐 Amasado",       f"{amasado_cap} est.")
        with ps2:
            st.markdown("**⏱️ Tiempos & Lógica**")
            st.metric("Variabilidad tiempos",  f"{variabilidad}×")
            st.metric("Espaciamiento lotes",   f"{espaciamiento}×")
            st.metric("Iteraciones",           f"{iter_sim}")
            st.metric("Fallas en horno",       "⚠️ SÍ" if falla_horno else "✓ NO")
            st.metric("Doble turno",           "🕐 SÍ (−20%)" if doble_turno else "✓ NO")
        with ps3:
            st.markdown("**📊 Mes simulado**")
            st.metric("Mes de análisis", MESES_F[mes_idx])
            st.metric("Plan total und.", f"{sum(plan_mes.values()):,}")
            st.metric("Semilla aleatoria", f"{int(semilla)}")
        st.caption("💡 Modifica estos parámetros en la barra lateral sección '5 · Simulación Operativa'.")

    st.markdown('<div class="sec-title">🗓️ Plan del mes (unidades a producir)</div>', unsafe_allow_html=True)
    cols_p=st.columns(5)
    for i,(p,u) in enumerate(plan_mes.items()):
        with cols_p[i]:
            hh_req=round(u*HORAS_PRODUCTO[p],1)
            lit=round(u*LITROS_UNIDAD_BASE[p],1)
            st.markdown(f"""
            <div class="kpi-card" style="background:{PROD_COLORS[p]}30;border-color:{PROD_COLORS_DARK[p]}60">
              <div class="icon">{EMOJIS[p]}</div>
              <div class="val" style="font-size:1.5rem">{u:,}</div>
              <div class="lbl">{PROD_LABELS[p]}</div>
              <div class="sub">{hh_req} H-H · {lit}L</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if not df_kpis.empty:
        st.markdown('<div class="sec-title">✅ Cumplimiento del plan</div>', unsafe_allow_html=True)
        fig_cum=go.Figure()
        for i,row in df_kpis.iterrows():
            p_key=[p for p in PRODUCTOS if PROD_LABELS[p]==row["Producto"]]
            p_key=p_key[0] if p_key else PRODUCTOS[i%len(PRODUCTOS)]
            fig_cum.add_trace(go.Bar(
                x=[row["Cumplimiento %"]],y=[row["Producto"]],orientation="h",
                marker=dict(color=PROD_COLORS[p_key],line=dict(color=PROD_COLORS_DARK[p_key],width=1.5)),
                text=f"{row['Cumplimiento %']:.1f}%",textposition="inside",
                textfont=dict(color="#46352A",size=12),showlegend=False,
                hovertemplate=f"<b>{row['Producto']}</b><br>Prod: {row['Und Producidas']:,.0f}<br>Plan: {row['Plan']:,.0f}<extra></extra>",
            ))
        fig_cum.add_vline(x=100,line_dash="dash",line_color=C["mocha"],annotation_text="Meta 100%")
        fig_cum.update_layout(**PLOT_CFG,height=250,xaxis=dict(range=[0,115]),
                              yaxis=dict(showgrid=False),xaxis_title="Cumplimiento (%)",
                              margin=dict(t=20,b=20),title="Cumplimiento del Plan por Producto")
        st.plotly_chart(fig_cum,use_container_width=True)

        col_t1,col_t2=st.columns(2)
        with col_t1:
            st.markdown('<div class="sec-title">⚡ Throughput (und/h)</div>', unsafe_allow_html=True)
            prods_kpi=[PROD_LABELS[p] for p in PRODUCTOS if PROD_LABELS[p] in df_kpis["Producto"].values]
            colores_kpi=[PROD_COLORS[p] for p in PRODUCTOS if PROD_LABELS[p] in df_kpis["Producto"].values]
            fig_tp=go.Figure(go.Bar(
                x=prods_kpi,y=df_kpis["Throughput (und/h)"].values,
                marker_color=colores_kpi,marker_line_color="white",marker_line_width=2,
                text=[f"{v:.1f}" for v in df_kpis["Throughput (und/h)"].values],textposition="outside",
            ))
            fig_tp.update_layout(**PLOT_CFG,height=270,yaxis_title="und/h",showlegend=False,
                                 xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"),margin=dict(t=40))
            st.plotly_chart(fig_tp,use_container_width=True)

        with col_t2:
            st.markdown('<div class="sec-title">⏱️ Lead Time (min/lote)</div>', unsafe_allow_html=True)
            fig_lt=go.Figure(go.Bar(
                x=prods_kpi,y=df_kpis["Lead Time (min/lote)"].values,
                marker_color=[PROD_COLORS_DARK[p] for p in PRODUCTOS if PROD_LABELS[p] in df_kpis["Producto"].values],
                marker_line_color="white",marker_line_width=2,
                text=[f"{v:.0f}" for v in df_kpis["Lead Time (min/lote)"].values],textposition="outside",
            ))
            fig_lt.update_layout(**PLOT_CFG,height=270,yaxis_title="min/lote",showlegend=False,
                                 xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"),margin=dict(t=40))
            st.plotly_chart(fig_lt,use_container_width=True)

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
        fig_util_g.add_hline(y=80,line_dash="dash",line_color=C["rose_d"],annotation_text="⚠ 80%",row=1,col=1)
        fig_util_g.update_layout(**PLOT_CFG,height=310)
        fig_util_g.update_xaxes(showgrid=False); fig_util_g.update_yaxes(gridcolor="#F0E8D8")
        st.plotly_chart(fig_util_g,use_container_width=True)

    if not df_lotes.empty:
        st.markdown('<div class="sec-title">📅 Diagrama de Gantt — Flujo de lotes</div>', unsafe_allow_html=True)
        n_gantt=min(60,len(df_lotes)); sub=df_lotes.head(n_gantt).reset_index(drop=True)
        fig_gantt=go.Figure()
        for _,row in sub.iterrows():
            fig_gantt.add_trace(go.Bar(
                x=[row["tiempo_sistema"]],y=[row["lote_id"]],base=[row["t_creacion"]],
                orientation="h",marker_color=PROD_COLORS.get(row["producto"],"#ccc"),
                opacity=0.85,showlegend=False,marker_line_color="white",marker_line_width=0.5,
                hovertemplate=(f"<b>{PROD_LABELS.get(row['producto'],row['producto'])}</b><br>"
                               f"Inicio: {row['t_creacion']:.0f} min<br>"
                               f"Duración: {row['tiempo_sistema']:.1f} min<extra></extra>"),
            ))
        for p,c in PROD_COLORS.items():
            fig_gantt.add_trace(go.Bar(x=[None],y=[None],marker_color=c,name=PROD_LABELS[p]))
        fig_gantt.update_layout(**PLOT_CFG,barmode="overlay",
                                height=max(370,n_gantt*8),
                                title=f"Gantt — Primeros {n_gantt} lotes",
                                xaxis_title="Tiempo simulado (min)",
                                legend=dict(orientation="h",y=-0.1,x=0.5,xanchor="center"),
                                yaxis=dict(showticklabels=False))
        st.plotly_chart(fig_gantt,use_container_width=True)

        st.markdown('<div class="sec-title">🎻 Distribución de tiempos en sistema por producto</div>', unsafe_allow_html=True)
        fig_violin=go.Figure()
        for p in PRODUCTOS:
            sub_v=df_lotes[df_lotes["producto"]==p]["tiempo_sistema"]
            if len(sub_v)<3: continue
            fig_violin.add_trace(go.Violin(y=sub_v,name=PROD_LABELS[p],box_visible=True,
                                           meanline_visible=True,fillcolor=PROD_COLORS[p],
                                           line_color=PROD_COLORS_DARK[p],opacity=0.82))
        fig_violin.update_layout(**PLOT_CFG,height=310,yaxis_title="Tiempo en sistema (min)",
                                 showlegend=False,violinmode="overlay")
        st.plotly_chart(fig_violin,use_container_width=True)

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
    st.markdown(f'<div class="info-box">Gemelo digital IoT · Variabilidad térmica: ×{variabilidad} · '
                f'Capacidad del horno: {cap_horno} estaciones · Límite operativo: 200°C</div>', unsafe_allow_html=True)

    if not df_sensores.empty:
        s1,s2,s3,s4=st.columns(4)
        s1.metric("🌡️ Temp. mínima",  f"{df_sensores['temperatura'].min():.1f} °C")
        s2.metric("🔥 Temp. máxima",  f"{df_sensores['temperatura'].max():.1f} °C")
        s3.metric("📊 Temp. promedio",f"{df_sensores['temperatura'].mean():.1f} °C")
        s4.metric("⚠️ Excesos >200°C",excesos,
                  delta="Revisar horno" if excesos else "Operación normal",
                  delta_color="inverse" if excesos else "off")

        fig_temp=go.Figure()
        fig_temp.add_hrect(y0=150,y1=200,fillcolor=hex_rgba(C["mint"],0.21),line_width=0,
                           annotation_text="Zona operativa óptima",annotation_font_color=C["sage"])
        fig_temp.add_trace(go.Scatter(x=df_sensores["tiempo"],y=df_sensores["temperatura"],
                                      mode="lines",name="Temperatura",fill="tozeroy",
                                      fillcolor=hex_rgba(C["peach"],0.13),
                                      line=dict(color=C["mocha"],width=1.8)))
        if len(df_sensores)>10:
            mm=df_sensores["temperatura"].rolling(5,min_periods=1).mean()
            fig_temp.add_trace(go.Scatter(x=df_sensores["tiempo"],y=mm,mode="lines",
                                          name="Media móvil",line=dict(color=C["rose_d"],width=2,dash="dot")))
        fig_temp.add_hline(y=200,line_dash="dash",line_color="#C0392B",
                           annotation_text="⚠ Límite 200°C",annotation_font_color="#C0392B")
        fig_temp.update_layout(**PLOT_CFG,height=310,xaxis_title="Tiempo simulado (min)",
                               yaxis_title="°C",title="Temperatura del Horno — Monitoreo Simulado",
                               legend=dict(orientation="h",y=-0.22,x=0.5,xanchor="center"),
                               xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"))
        st.plotly_chart(fig_temp,use_container_width=True)

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
            st.plotly_chart(fig_ocup,use_container_width=True)

        with col_s2:
            fig_hist=go.Figure()
            fig_hist.add_trace(go.Histogram(x=df_sensores["temperatura"],nbinsx=35,
                                            marker_color=C["butter"],opacity=0.85,
                                            marker_line_color="white",marker_line_width=1))
            fig_hist.add_vline(x=200,line_dash="dash",line_color="#C0392B",annotation_text="200°C")
            fig_hist.add_vline(x=df_sensores["temperatura"].mean(),line_dash="dot",
                               line_color=C["mocha"],
                               annotation_text=f"Prom:{df_sensores['temperatura'].mean():.0f}°C")
            fig_hist.update_layout(**PLOT_CFG,height=250,title="Distribución de Temperatura",
                                   xaxis_title="°C",yaxis_title="Frecuencia",showlegend=False,
                                   xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"))
            st.plotly_chart(fig_hist,use_container_width=True)
    else:
        st.info("Sin datos de sensores.")

# ────────────────────────────────────────────────────────────────────────────
# TAB 6 — ESCENARIOS
# ────────────────────────────────────────────────────────────────────────────
with tabs[5]:
    st.markdown('<div class="sec-title">🔬 Análisis de Escenarios What-If</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Compara múltiples configuraciones de planta para identificar la estrategia óptima. Cada escenario simula condiciones distintas de demanda, capacidad y operación.</div>', unsafe_allow_html=True)

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
        filas_esc=[]; prog=st.progress(0)
        for i,nm in enumerate(escenarios_sel):
            prog.progress((i+1)/len(escenarios_sel),text=f"Simulando: {nm}...")
            cfg=ESCENARIOS_DEF[nm]
            plan_esc={p:max(int(u*cfg["fd"]),0) for p,u in plan_mes.items()}
            cap_esc={**cap_rec,"horno":max(cap_horno+cfg["cap_delta"],1)}
            df_l,df_u,_=run_simulacion_cached(
                tuple(plan_esc.items()),tuple(cap_esc.items()),cfg["falla"],cfg["ft"],
                cfg["var"],espaciamiento,int(semilla))
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
                    fig_ec.update_layout(**PLOT_CFG,height=300,yaxis_title="%",showlegend=False,
                                         xaxis=dict(showgrid=False,tickangle=-25),yaxis=dict(gridcolor="#F0E8D8"),
                                         margin=dict(t=30,b=90))
                    st.plotly_chart(fig_ec,use_container_width=True)

            with col_e2:
                st.markdown('<div class="sec-title">⚙️ Utilización máxima</div>', unsafe_allow_html=True)
                if "Util. max %" in df_comp.columns:
                    col_u=[C["rose"] if v>=80 else C["butter"] if v>=60 else C["mint"] for v in df_comp["Util. max %"]]
                    fig_eu=go.Figure(go.Bar(x=df_comp["Escenario"],y=df_comp["Util. max %"],
                                           marker_color=col_u,marker_line_color="white",marker_line_width=2,
                                           text=[f"{v:.0f}%" for v in df_comp["Util. max %"]],textposition="outside"))
                    fig_eu.add_hline(y=80,line_dash="dash",line_color=C["rose_d"],annotation_text="⚠ 80%")
                    fig_eu.update_layout(**PLOT_CFG,height=300,yaxis_title="%",showlegend=False,
                                         xaxis=dict(showgrid=False,tickangle=-25),yaxis=dict(gridcolor="#F0E8D8"),
                                         margin=dict(t=30,b=90))
                    st.plotly_chart(fig_eu,use_container_width=True)

            # Radar
            st.markdown('<div class="sec-title">🕸️ Radar comparativo de escenarios</div>', unsafe_allow_html=True)
            cols_radar=[c for c in df_comp.columns if c not in ["Escenario","Cuellos botella"]
                        and df_comp[c].dtype!="object"]
            if len(cols_radar)>=3:
                df_norm=df_comp[cols_radar].copy()
                for c in df_norm.columns:
                    rng=df_norm[c].max()-df_norm[c].min()
                    df_norm[c]=(df_norm[c]-df_norm[c].min())/rng if rng else 0.5

                COLORES_R=list(PROD_COLORS.values())+[C["rose"],C["sky"],C["lavender"]]
                RGBA_R=[hex_rgba(x,0.15) for x in COLORES_R]
                fig_radar=go.Figure()
                for i,row in df_comp.iterrows():
                    vals=[df_norm.loc[i,c] for c in cols_radar]
                    fig_radar.add_trace(go.Scatterpolar(
                        r=vals+[vals[0]],theta=cols_radar+[cols_radar[0]],
                        fill="toself",name=row["Escenario"],
                        line=dict(color=COLORES_R[i%len(COLORES_R)],width=2),
                        fillcolor=RGBA_R[i%len(RGBA_R)],
                    ))
                fig_radar.update_layout(
                    **PLOT_CFG,height=440,
                    polar=dict(radialaxis=dict(visible=True,range=[0,1],gridcolor="#E8D5B0",linecolor="#E8D5B0"),
                               angularaxis=dict(gridcolor="#E8D5B0")),
                    title="Comparación normalizada de escenarios",
                    legend=dict(orientation="h",y=-0.15,x=0.5,xanchor="center"),
                )
                st.plotly_chart(fig_radar,use_container_width=True)
    else:
        st.markdown("""
        <div class="info-box" style="text-align:center;padding:2rem;">
          <div style="font-size:2.5rem">🔬</div>
          <b>Selecciona escenarios y haz clic en Comparar</b><br>
          <span style="font-size:0.85rem;color:#9B7B5A;">Se simulará cada configuración y se compararán KPIs lado a lado</span>
        </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown(f"""
<div style='text-align:center;color:#B9857E;font-size:0.82rem;
     font-family:DM Sans,sans-serif;padding:0.4rem 0 1rem'>
  🥐 <b>Gemelo Digital — Panadería Dora del Hoyo v3.0</b> &nbsp;·&nbsp;
  LP Agregada · Desagregación · SimPy · Streamlit
</div>""", unsafe_allow_html=True)

