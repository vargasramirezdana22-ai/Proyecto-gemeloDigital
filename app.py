"""
app.py  —  Gemelo Digital · Panadería Dora del Hoyo  v4.0
===========================================================
MEJORAS v4.0:
  • Paleta pastel elegante tipo panadería aplicada en TODOS los elementos
  • Parámetros globales en barra lateral izquierda (afectan todo el modelo)
  • Parámetros específicos dentro de cada pestaña (expanders)
  • Gráfico combinado Producción + Inventario + Demanda en Desagregación
  • Simulación con gráfico adicional Producción/Inventario/Demanda
  • KPIs enriquecidos con litros y cobertura comercial
  • Escenarios con radar, barras comparativas y tabla detallada

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
# PALETA PASTEL ELEGANTE — DORA DEL HOYO v4
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
    "sidebar_bg": "#2C1A0E",
    "sidebar_text": "#FCE7A8",
    "sidebar_acc": "#E8C27A",
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
    "Brownies":           "🍫 Brownies",
    "Mantecadas":         "🧁 Mantecadas",
    "Mantecadas_Amapola": "🌸 Mant. Amapola",
    "Torta_Naranja":      "🍊 Torta Naranja",
    "Pan_Maiz":           "🌽 Pan de Maíz",
}
PROD_LABELS_SHORT = {
    "Brownies": "Brownies","Mantecadas": "Mantecadas",
    "Mantecadas_Amapola": "M. Amapola",
    "Torta_Naranja": "T. Naranja","Pan_Maiz": "Pan Maíz",
}

def hex_rgba(hex_color, alpha=0.15):
    h = hex_color.lstrip("#")
    r,g,b = int(h[0:2],16),int(h[2:4],16),int(h[4:6],16)
    return f"rgba({r},{g},{b},{alpha})"

# ══════════════════════════════════════════════════════════════════════════════
# DATOS MAESTROS
# ══════════════════════════════════════════════════════════════════════════════
PRODUCTOS = ["Brownies","Mantecadas","Mantecadas_Amapola","Torta_Naranja","Pan_Maiz"]
MESES     = ["January","February","March","April","May","June",
             "July","August","September","October","November","December"]
MESES_ES  = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]
MESES_F   = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

DEM_BASE = {
    "Brownies":           [315,804,734,541,494, 59,315,803,734,541,494, 59],
    "Mantecadas":         [125,780,432,910,275, 68,512,834,690,455,389,120],
    "Mantecadas_Amapola": [320,710,520,251,631,150,330,220,710,610,489,180],
    "Torta_Naranja":      [100,250,200,101,190, 50,100,220,200,170,180,187],
    "Pan_Maiz":           [330,140,143, 73, 83, 48, 70, 89,118, 83, 67, 87],
}
HORAS_PRODUCTO = {
    "Brownies":0.866,"Mantecadas":0.175,"Mantecadas_Amapola":0.175,
    "Torta_Naranja":0.175,"Pan_Maiz":0.312,
}
RUTAS = {
    "Brownies":           [("Mezclado","mezcla",12,18),("Moldeado","dosificado",8,14),
                           ("Horneado","horno",30,40),("Enfriamiento","enfriamiento",25,35),
                           ("Corte/Empaque","empaque",8,12)],
    "Mantecadas":         [("Mezclado","mezcla",12,18),("Dosificado","dosificado",16,24),
                           ("Horneado","horno",20,30),("Enfriamiento","enfriamiento",35,55),
                           ("Empaque","empaque",4,6)],
    "Mantecadas_Amapola": [("Mezclado","mezcla",12,18),("Inc. Semillas","mezcla",8,12),
                           ("Dosificado","dosificado",16,24),("Horneado","horno",20,30),
                           ("Enfriamiento","enfriamiento",36,54),("Empaque","empaque",4,6)],
    "Torta_Naranja":      [("Mezclado","mezcla",16,24),("Dosificado","dosificado",8,12),
                           ("Horneado","horno",32,48),("Enfriamiento","enfriamiento",48,72),
                           ("Desmolde","dosificado",8,12),("Empaque","empaque",8,12)],
    "Pan_Maiz":           [("Mezclado","mezcla",12,18),("Amasado","amasado",16,24),
                           ("Moldeado","dosificado",12,18),("Horneado","horno",28,42),
                           ("Enfriamiento","enfriamiento",36,54),("Empaque","empaque",4,6)],
}
TAMANO_LOTE_BASE = {"Brownies":12,"Mantecadas":10,"Mantecadas_Amapola":10,"Torta_Naranja":12,"Pan_Maiz":15}
INV_INICIAL      = {p:0 for p in PRODUCTOS}

# ══════════════════════════════════════════════════════════════════════════════
# FUNCIONES CORE
# ══════════════════════════════════════════════════════════════════════════════
def get_demanda(mix_factors, factor_demanda):
    return {p:[round(v*factor_demanda*mix_factors.get(p,1.0),1) for v in DEM_BASE[p]]
            for p in PRODUCTOS}

def dem_horas_hombre(dem_hist):
    return {mes:round(sum(dem_hist[p][i]*HORAS_PRODUCTO[p] for p in PRODUCTOS),4)
            for i,mes in enumerate(MESES)}

def pronostico_simple(serie, meses_extra=3):
    alpha=0.3; nivel=serie[0]; suav=[]
    for v in serie: nivel=alpha*v+(1-alpha)*nivel; suav.append(nivel)
    futuro=[]; last=suav[-1]
    trend=(suav[-1]-suav[-4])/3 if len(suav)>=4 else 0
    for _ in range(meses_extra): last+=alpha*trend; futuro.append(round(last,1))
    return suav, futuro

@st.cache_data(show_spinner=False)
def run_agregacion(dem_hh_items, params_tuple):
    params=dict(params_tuple); dem_h=dict(dem_hh_items)
    Ct=params["Ct"]; Ht=params["Ht"]; PIt=params["PIt"]
    CRt=params["CRt"]; COt=params["COt"]; Wm=params["CW_mas"]; Wd=params["CW_menos"]
    M=params["M"]; LRi=params["LR_inicial"]; stock_obj=params.get("stock_obj",0.0)
    mdl=LpProblem("Agr",LpMinimize)
    P=LpVariable.dicts("P",MESES,lowBound=0); Iv=LpVariable.dicts("I",MESES,lowBound=0)
    S=LpVariable.dicts("S",MESES,lowBound=0); LR=LpVariable.dicts("LR",MESES,lowBound=0)
    LO=LpVariable.dicts("LO",MESES,lowBound=0); LU=LpVariable.dicts("LU",MESES,lowBound=0)
    NI=LpVariable.dicts("NI",MESES)
    Wmas=LpVariable.dicts("Wm",MESES,lowBound=0); Wmenos=LpVariable.dicts("Wd",MESES,lowBound=0)
    mdl+=lpSum(Ct*P[t]+Ht*Iv[t]+PIt*S[t]+CRt*LR[t]+COt*LO[t]+Wm*Wmas[t]+Wd*Wmenos[t] for t in MESES)
    for idx,t in enumerate(MESES):
        d=dem_h[t]; tp=MESES[idx-1] if idx>0 else None
        mdl+=(NI[t]==P[t]-d) if idx==0 else (NI[t]==NI[tp]+P[t]-d)
        mdl+=NI[t]==Iv[t]-S[t]; mdl+=LU[t]+LO[t]==M*P[t]; mdl+=LU[t]<=LR[t]
        if stock_obj>0: mdl+=Iv[t]>=stock_obj*d
        mdl+=(LR[t]==LRi+Wmas[t]-Wmenos[t]) if idx==0 else (LR[t]==LR[tp]+Wmas[t]-Wmenos[t])
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
def run_desagregacion(prod_hh_items, dem_hist_items, costo_pen, costo_inv, suavizado, proteccion_mix):
    prod_hh=dict(prod_hh_items); dem_hist=dict(dem_hist_items)
    mdl=LpProblem("Desag",LpMinimize)
    X={(p,t):LpVariable(f"X_{p}_{t}",lowBound=0) for p in PRODUCTOS for t in MESES}
    Iv={(p,t):LpVariable(f"I_{p}_{t}",lowBound=0) for p in PRODUCTOS for t in MESES}
    S={(p,t):LpVariable(f"S_{p}_{t}",lowBound=0) for p in PRODUCTOS for t in MESES}
    DX={(p,t):LpVariable(f"DX_{p}_{t}",lowBound=0) for p in PRODUCTOS for t in MESES}
    mdl+=lpSum(costo_inv*Iv[p,t]+costo_pen*S[p,t]+suavizado*DX[p,t]
               for p in PRODUCTOS for t in MESES)
    for idx,t in enumerate(MESES):
        tp=MESES[idx-1] if idx>0 else None
        mdl+=(lpSum(HORAS_PRODUCTO[p]*X[p,t] for p in PRODUCTOS)<=prod_hh[t],f"Cap_{t}")
        for p in PRODUCTOS:
            d=dem_hist[p][idx]
            if idx==0: mdl+=Iv[p,t]-S[p,t]==INV_INICIAL[p]+X[p,t]-d
            else:      mdl+=Iv[p,t]-S[p,t]==Iv[p,tp]-S[p,tp]+X[p,t]-d
            if idx>0:
                mdl+=DX[p,t]>=X[p,t]-X[p,tp]; mdl+=DX[p,t]>=X[p,tp]-X[p,t]
    mdl.solve(PULP_CBC_CMD(msg=False))
    resultados={}
    for p in PRODUCTOS:
        filas=[]
        for idx,t in enumerate(MESES):
            xv=round(X[p,t].varValue or 0,2); iv=round(Iv[p,t].varValue or 0,2)
            sv=round(S[p,t].varValue or 0,2)
            ini=INV_INICIAL[p] if idx==0 else round(Iv[p,MESES[idx-1]].varValue or 0,2)
            filas.append({"Mes":t,"Mes_ES":MESES_ES[idx],"Mes_F":MESES_F[idx],
                          "Demanda":dem_hist[p][idx],"Produccion":xv,
                          "Inv_Ini":ini,"Inv_Fin":iv,"Backlog":sv})
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
            reg_uso(env,recursos,prod); t_e=env.now
            with recursos[rec_nm].request() as req:
                yield req; esperas[etapa]=round(env.now-t_e,3)
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
        tasa=dur_mes/max(n,1)*espaciamiento; ta=random.expovariate(1/max(tasa,1)); rem=unid
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
    return (pd.DataFrame(lotes_data) if lotes_data else pd.DataFrame(),
            pd.DataFrame(uso_rec)    if uso_rec    else pd.DataFrame(),
            pd.DataFrame(sensores)   if sensores   else pd.DataFrame())

def calc_utilizacion(df_uso):
    if df_uso.empty: return pd.DataFrame()
    filas=[]
    for rec,grp in df_uso.groupby("recurso"):
        grp=grp.sort_values("tiempo").reset_index(drop=True)
        cap=grp["capacidad"].iloc[0]; t=grp["tiempo"].values; ocp=grp["ocupados"].values
        fn=np.trapezoid if hasattr(np,"trapezoid") else np.trapz
        util=round(fn(ocp,t)/(cap*(t[-1]-t[0]))*100,2) if len(t)>1 and t[-1]>t[0] else 0.0
        filas.append({"Recurso":rec,"Utilizacion_%":util,
                      "Cola Prom":round(grp["cola"].mean(),3),
                      "Cola Max":int(grp["cola"].max()),"Capacidad":int(cap),
                      "Cuello Botella":util>=80 or grp["cola"].mean()>0.5})
    return pd.DataFrame(filas).sort_values("Utilizacion_%",ascending=False).reset_index(drop=True)

def calc_kpis(df_lotes, plan):
    if df_lotes.empty: return pd.DataFrame()
    dur=(df_lotes["t_fin"].max()-df_lotes["t_creacion"].min())/60; filas=[]
    for p in PRODUCTOS:
        sub=df_lotes[df_lotes["producto"]==p]
        if sub.empty: continue
        und=sub["tamano"].sum(); pu=plan.get(p,0)
        tp=round(und/max(dur,0.01),3); ct_=round((sub["tiempo_sistema"]/sub["tamano"]).mean(),3)
        lt=round(sub["tiempo_sistema"].mean(),3)
        takt=round((44*4*60)/max((sum(DEM_BASE[p])/12)/TAMANO_LOTE_BASE[p],1),2)
        filas.append({"Producto":PROD_LABELS_SHORT[p],"Und Prod.":und,"Plan":pu,
                      "Throughput (und/h)":tp,"Cycle Time (min/und)":ct_,
                      "Lead Time (min/lote)":lt,"WIP Prom":round(tp*(lt/60),2),
                      "Takt (min/lote)":takt,
                      "Cumplimiento %":round(min(und/max(pu,1)*100,100),2)})
    return pd.DataFrame(filas)

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN STREAMLIT & CSS COMPLETO
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Gemelo Digital · Dora del Hoyo",
                   page_icon="🥐", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;600;700&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
  font-family: 'DM Sans', sans-serif;
  background-color: #FFFDF8 !important;
  color: #46352A !important;
}

/* ── HERO BANNER ─────────────────────────────────────────── */
.hero {
  background: linear-gradient(135deg, #46352A 0%, #8B5E3C 45%, #D4A574 80%, #FCE7A8 100%);
  padding: 2.2rem 3rem 1.8rem; border-radius: 24px; margin-bottom: 1.8rem;
  box-shadow: 0 20px 60px rgba(70,53,42,0.22); position:relative; overflow:hidden;
}
.hero::before { content:"🥐"; font-size:11rem; position:absolute; right:2rem; top:-2rem;
  opacity:0.08; transform:rotate(-20deg); pointer-events:none; }
.hero h1 { font-family:'Cormorant Garamond',serif; color:#FFFDF8; font-size:2.6rem;
  margin:0; letter-spacing:-0.5px; font-weight:700; }
.hero p  { color:#FCE7A8; margin:0.4rem 0 0; font-size:0.95rem; font-weight:300; }
.hero .badge { display:inline-block; background:rgba(255,255,255,0.12); color:#FFFDF8;
  border:1px solid rgba(255,255,255,0.22); padding:0.22rem 0.8rem; border-radius:20px;
  font-size:0.76rem; margin-top:0.7rem; margin-right:0.4rem; backdrop-filter:blur(4px); }

/* ── KPI CARDS ────────────────────────────────────────────── */
.kpi-card { background:#FFFFFF; border-radius:18px; padding:1.1rem 0.9rem;
  box-shadow:0 4px 20px rgba(70,53,42,0.07); border:1px solid #EADFD7;
  text-align:center; transition:transform 0.25s,box-shadow 0.25s; }
.kpi-card:hover { transform:translateY(-4px); box-shadow:0 12px 32px rgba(70,53,42,0.13); }
.kpi-card .icon { font-size:1.8rem; margin-bottom:0.3rem; }
.kpi-card .val  { font-family:'Cormorant Garamond',serif; font-size:1.9rem;
  color:#46352A; line-height:1; margin:0.15rem 0; font-weight:700; }
.kpi-card .lbl  { font-size:0.67rem; color:#B9857E; text-transform:uppercase;
  letter-spacing:1.2px; font-weight:600; }
.kpi-card .sub  { font-size:0.74rem; color:#9B7B5A; margin-top:0.25rem; }

/* ── SECTION TITLES ──────────────────────────────────────── */
.sec-title { font-family:'Cormorant Garamond',serif; font-size:1.35rem; color:#46352A;
  border-left:4px solid #E8C27A; padding-left:0.8rem;
  margin:1.6rem 0 0.9rem; font-weight:600; }

/* ── INFO BOX ─────────────────────────────────────────────── */
.info-box { background:linear-gradient(135deg,rgba(252,231,168,0.25),rgba(255,253,248,0.9));
  border:1px solid rgba(232,194,122,0.45); border-radius:14px;
  padding:0.85rem 1.1rem; font-size:0.87rem; color:#46352A; margin:0.5rem 0 0.9rem; }

/* ── PARAM BOX (parámetros en pestaña) ───────────────────── */
.param-box { background:linear-gradient(135deg,rgba(207,228,246,0.3),rgba(255,253,248,0.95));
  border:1px solid rgba(154,196,232,0.5); border-radius:14px;
  padding:1rem 1.2rem; margin:0.6rem 0 1rem; }
.param-box-title { font-family:'Cormorant Garamond',serif; font-size:1.1rem;
  color:#4A8DB5; font-weight:600; margin-bottom:0.5rem; }

/* ── PILLS ───────────────────────────────────────────────── */
.pill-ok   { background:#CFE9D9; color:#1B5E20; padding:0.3rem 1rem;
  border-radius:20px; font-size:0.83rem; font-weight:600; display:inline-block; }
.pill-warn { background:#F6C9D0; color:#880E2E; padding:0.3rem 1rem;
  border-radius:20px; font-size:0.83rem; font-weight:600; display:inline-block; }

/* ── SIDEBAR ─────────────────────────────────────────────── */
[data-testid="stSidebar"] { background:#2C1A0E !important; }
[data-testid="stSidebar"] *   { color:#FCE7A8 !important; }
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3  { color:#E8C27A !important;
  font-family:'Cormorant Garamond',serif !important; }
[data-testid="stSidebar"] hr  { border-color:rgba(232,194,122,0.3) !important; }
[data-testid="stSidebar"] .stSlider > div { background:transparent !important; }
[data-testid="stSidebar"] .stSlider [data-baseweb="slider"] div[role="slider"] {
  background:#E8C27A !important; }
[data-testid="stSidebar"] input { background:rgba(255,255,255,0.08) !important;
  color:#FCE7A8 !important; border-color:rgba(232,194,122,0.4) !important; }

/* ── TABS ────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
  background:linear-gradient(to right,#FFF8EE,#FFFDF8);
  border-radius:12px; padding:4px 8px; gap:4px;
  border:1px solid #EADFD7;
}
.stTabs [data-baseweb="tab"] {
  font-family:'DM Sans',sans-serif; font-weight:500; color:#9B7B5A;
  border-radius:10px; padding:0.45rem 1.1rem; transition:all 0.2s;
  background:transparent !important; border:none !important;
}
.stTabs [aria-selected="true"] {
  color:#46352A !important; background:#FCE7A8 !important;
  box-shadow:0 2px 8px rgba(70,53,42,0.12) !important;
}

/* ── BUTTONS ─────────────────────────────────────────────── */
.stButton > button[kind="primary"] {
  background:linear-gradient(135deg,#C68B59,#E8C27A) !important;
  color:#FFFDF8 !important; border:none !important; border-radius:12px !important;
  font-family:'DM Sans',sans-serif !important; font-weight:600 !important;
  box-shadow:0 4px 16px rgba(198,139,89,0.35) !important;
}
.stButton > button { border-radius:10px !important; font-family:'DM Sans',sans-serif !important; }

/* ── EXPANDERS ───────────────────────────────────────────── */
[data-testid="stExpander"] { background:#FFFFFF !important;
  border:1px solid #EADFD7 !important; border-radius:14px !important; }
[data-testid="stExpander"] summary { background:#FFF8EE !important;
  border-radius:14px !important; color:#46352A !important;
  font-family:'DM Sans',sans-serif !important; }

/* ── METRICS ─────────────────────────────────────────────── */
[data-testid="stMetric"] { background:#FFFFFF; border-radius:14px;
  padding:0.8rem 1rem; border:1px solid #EADFD7;
  box-shadow:0 2px 10px rgba(70,53,42,0.05); }
[data-testid="stMetricLabel"] { color:#9B7B5A !important; font-size:0.8rem !important; }
[data-testid="stMetricValue"] { color:#46352A !important; font-family:'Cormorant Garamond',serif !important; }

/* ── DATAFRAMES ──────────────────────────────────────────── */
[data-testid="stDataFrame"] { border-radius:12px !important; overflow:hidden !important;
  border:1px solid #EADFD7 !important; }

/* ── NUMBER INPUT ─────────────────────────────────────────── */
.stNumberInput input { border-color:#EADFD7 !important; border-radius:8px !important;
  background:#FFF8EE !important; color:#46352A !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PLOT BASE CONFIG
# ══════════════════════════════════════════════════════════════════════════════
PLOT_CFG = dict(
    template="plotly_white",
    font=dict(family="DM Sans", color="#46352A", size=12),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(255,253,248,0.5)",
)

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR — PARÁMETROS GLOBALES (afectan TODO el modelo)
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🥐 Dora del Hoyo")
    st.markdown("*Gemelo Digital v4.0*")
    st.markdown("---")
    st.markdown("### 🌐 Parámetros Globales")
    st.markdown("<small style='color:#E8C27A'>Estos controles afectan **todo** el modelo</small>", unsafe_allow_html=True)
    st.markdown("")

    mes_idx = st.selectbox("📅 Mes de análisis", range(12), index=1,
                            format_func=lambda i: MESES_F[i])
    factor_demanda = st.slider("📈 Impulso de demanda", 0.5, 2.0, 1.0, 0.05,
                                help="Multiplica la demanda histórica de todos los productos")
    meses_pronostico = st.slider("🔮 Horizonte de proyección (meses)", 1, 6, 3,
                                  help="Cuántos meses hacia adelante proyectar en la gráfica de demanda")
    participacion_mercado = st.slider("🛒 Cobertura comercial (%)", 10, 100, 75, 5,
                                       help="Porcentaje del mercado que se está capturando")
    litros_por_unidad = st.slider("🧁 Litros por unidad (promedio)", 0.1, 2.0, 0.35, 0.05,
                                   help="Convierte unidades producidas a volumen en litros")
    semilla = st.number_input("🎲 Semilla aleatoria", value=42, step=1,
                               help="Controla la aleatoriedad de la simulación para reproducibilidad")

    st.markdown("---")
    st.markdown("<div style='font-size:0.72rem;color:#E8C27A;line-height:1.6'>"
                "📍 Panadería Dora del Hoyo<br>"
                "🔢 SimPy · PuLP · Streamlit v4<br>"
                "📊 Gemelo Digital — S&OP</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PRE-CÁLCULO CON PARÁMETROS POR DEFECTO
# (los parámetros específicos se leerán dentro de cada tab)
# ══════════════════════════════════════════════════════════════════════════════
# Mix inicial (1.0 = sin cambio)
MIX_DEFAULT = {p: 1.0 for p in PRODUCTOS}
DEM_HIST_DEFAULT = get_demanda(MIX_DEFAULT, factor_demanda)
dem_h_default    = dem_horas_hombre(DEM_HIST_DEFAULT)

# Capacidad laboral por defecto
hh_por_mes_default = 10 * 1 * 8 * 22 * (0.85 * 0.95 * 1.10)
params_default = {"Ct":4310,"Ht":100000,"PIt":100000,"CRt":11364,"COt":14205,
                  "CW_mas":14204,"CW_menos":15061,"M":1,
                  "LR_inicial":round(hh_por_mes_default,2),"stock_obj":0.0}

with st.spinner("⚙️ Calculando plan inicial..."):
    df_agr, costo = run_agregacion(
        tuple(dem_h_default.items()), tuple(sorted(params_default.items()))
    )

prod_hh = dict(zip(df_agr["Mes"], df_agr["Produccion_HH"]))
dem_hist_items_default = tuple((p, tuple(DEM_HIST_DEFAULT[p])) for p in PRODUCTOS)

with st.spinner("🔢 Desagregando..."):
    desag = run_desagregacion(
        tuple(prod_hh.items()), dem_hist_items_default, 150000, 100000, 500, False
    )

mes_nm    = MESES[mes_idx]
plan_mes  = {p:int(desag[p].loc[desag[p]["Mes"]==mes_nm,"Produccion"].values[0]) for p in PRODUCTOS}
cap_rec   = {"mezcla":2,"dosificado":2,"horno":3,"enfriamiento":4,"empaque":2,"amasado":1}

with st.spinner("🏭 Simulando planta..."):
    df_lotes, df_uso, df_sensores = run_simulacion_cached(
        tuple(plan_mes.items()), tuple(cap_rec.items()),
        False, 1.0, 1.0, 1.0, int(semilla)
    )

df_kpis = calc_kpis(df_lotes, plan_mes)
df_util = calc_utilizacion(df_uso)

# ══════════════════════════════════════════════════════════════════════════════
# HERO & KPIs GLOBALES
# ══════════════════════════════════════════════════════════════════════════════
prod_total    = sum(desag[p]["Produccion"].sum() for p in PRODUCTOS)
litros_total  = round(prod_total * litros_por_unidad, 1)
cum_avg       = df_kpis["Cumplimiento %"].mean() if not df_kpis.empty else 0
util_max      = df_util["Utilizacion_%"].max()   if not df_util.empty else 0
temp_avg      = df_sensores["temperatura"].mean() if not df_sensores.empty else 0
excesos       = int((df_sensores["temperatura"]>200).sum()) if not df_sensores.empty else 0

st.markdown(f"""
<div class="hero">
  <h1>Gemelo Digital — Panadería Dora del Hoyo</h1>
  <p>Optimización LP · Simulación de Eventos Discretos · Análisis What-If en tiempo real</p>
  <span class="badge">📅 {MESES_F[mes_idx]}</span>
  <span class="badge">📈 Demanda ×{factor_demanda}</span>
  <span class="badge">🛒 Cobertura {participacion_mercado}%</span>
  <span class="badge">🧁 {litros_total:,.0f} L proyectados</span>
  <span class="badge">🔥 Horno: {cap_rec['horno']} est.</span>
  <span class="badge">💰 COP ${costo/1e6:.1f}M</span>
</div>""", unsafe_allow_html=True)

def kpi_html(col, icon, val, lbl, sub=""):
    col.markdown(f"""<div class="kpi-card">
      <div class="icon">{icon}</div>
      <div class="val">{val}</div>
      <div class="lbl">{lbl}</div>
      {"<div class='sub'>"+sub+"</div>" if sub else ""}
    </div>""", unsafe_allow_html=True)

k1,k2,k3,k4,k5,k6 = st.columns(6)
kpi_html(k1,"💰",f"${costo/1e6:.1f}M","Costo Óptimo","COP · Plan anual")
kpi_html(k2,"🧁",f"{litros_total:,.0f}L","Volumen Anual",f"×{litros_por_unidad} L/und")
kpi_html(k3,"🛒",f"{participacion_mercado}%","Cobertura Comercial",f"{prod_total:,.0f} und/año")
kpi_html(k4,"✅",f"{cum_avg:.1f}%","Cumplimiento Sim.",MESES_F[mes_idx])
kpi_html(k5,"⚙️",f"{util_max:.0f}%","Util. Máx. Recurso",
         "⚠️ Cuello botella" if util_max>=80 else "✓ OK")
kpi_html(k6,"🌡️",f"{temp_avg:.0f}°C","Temp. Horno Prom.",
         f"⚠️ {excesos} excesos" if excesos else "✓ Sin excesos")

st.markdown("<br>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tabs = st.tabs(["📊 Demanda & Pronóstico","📋 Plan Agregado",
                "📦 Desagregación","🏭 Simulación","🌡️ Sensores","🔬 Escenarios"])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — DEMANDA & PRONÓSTICO
# Parámetros propios: mix por producto, horizonte de proyección (ya en sidebar)
# ─────────────────────────────────────────────────────────────────────────────
with tabs[0]:
    st.markdown('<div class="sec-title">📊 Demanda histórica y pronóstico por producto</div>',
                unsafe_allow_html=True)

    # ── Parámetros específicos de Demanda ────────────────────────────────────
    with st.expander("🎛️ Parámetros de Demanda — Mix por producto", expanded=False):
        st.markdown('<div class="param-box"><div class="param-box-title">🍞 Ajustar participación por producto</div>'
                    'Modifica el peso relativo de cada producto. '
                    'Valores > 1.0 simulan promociones o mayor preferencia; < 1.0 contracción.</div>',
                    unsafe_allow_html=True)
        c1,c2,c3,c4,c5 = st.columns(5)
        mix_br = c1.slider("🍫 Brownies",        0.3,2.0,1.0,0.05)
        mix_ma = c2.slider("🧁 Mantecadas",       0.3,2.0,1.0,0.05)
        mix_am = c3.slider("🌸 M. Amapola",      0.3,2.0,1.0,0.05)
        mix_to = c4.slider("🍊 Torta Naranja",   0.3,2.0,1.0,0.05)
        mix_pm = c5.slider("🌽 Pan de Maíz",     0.3,2.0,1.0,0.05)

    MIX = {"Brownies":mix_br,"Mantecadas":mix_ma,"Mantecadas_Amapola":mix_am,
           "Torta_Naranja":mix_to,"Pan_Maiz":mix_pm}
    DEM_HIST = get_demanda(MIX, factor_demanda)
    dem_h    = dem_horas_hombre(DEM_HIST)

    st.markdown(f'<div class="info-box">Datos ajustados por mix de producto × impulso global <b>×{factor_demanda}</b> · '
                f'Proyección: <b>{meses_pronostico} meses</b> · '
                f'Suavizado exponencial α=0.3</div>', unsafe_allow_html=True)

    # ── Gráfica principal: series + pronóstico ───────────────────────────────
    fig_pro = go.Figure()
    for p in PRODUCTOS:
        serie=DEM_HIST[p]; suav,futuro=pronostico_simple(serie,meses_pronostico)
        fig_pro.add_trace(go.Scatter(x=MESES_ES,y=serie,mode="lines",name=PROD_LABELS_SHORT[p],
            line=dict(color=PROD_COLORS_DARK[p],width=2.5),legendgroup=p))
        x_fut=[MESES_ES[-1]]+[f"P+{j+1}" for j in range(meses_pronostico)]
        fig_pro.add_trace(go.Scatter(x=x_fut,y=[suav[-1]]+futuro,mode="lines+markers",
            line=dict(color=PROD_COLORS_DARK[p],width=2,dash="dash"),
            marker=dict(size=10,color=PROD_COLORS[p],line=dict(color=PROD_COLORS_DARK[p],width=2)),
            legendgroup=p,showlegend=False))
    fig_pro.add_vline(x=len(MESES_ES)-1,line_dash="dot",line_color=C["gold"],
                      annotation_text="▶ Pronóstico",annotation_font_color=C["gold"])
    fig_pro.add_vline(x=mes_idx,line_dash="dash",line_color=C["mocha"],
                      annotation_text=f"★ {MESES_F[mes_idx]}",
                      annotation_font_color=C["mocha"],annotation_position="top")
    fig_pro.update_layout(**PLOT_CFG,height=420,
        title="Demanda & Proyección — Panadería Dora del Hoyo",
        xaxis_title="Mes",yaxis_title="Unidades",
        legend=dict(orientation="h",y=-0.22,x=0.5,xanchor="center"),
        xaxis=dict(gridcolor="#F0E8D8"),yaxis=dict(gridcolor="#F0E8D8"))
    st.plotly_chart(fig_pro,use_container_width=True)

    col_a,col_b = st.columns(2)
    with col_a:
        st.markdown('<div class="sec-title">🔥 Mapa de calor — Estacionalidad</div>',unsafe_allow_html=True)
        z=[[DEM_HIST[p][i] for i in range(12)] for p in PRODUCTOS]
        fig_heat=go.Figure(go.Heatmap(z=z,x=MESES_ES,
            y=[PROD_LABELS_SHORT[p] for p in PRODUCTOS],
            colorscale=[[0,"#FFFDF8"],[0.3,"#FCE7A8"],[0.65,"#E8C27A"],[1,"#8B5E3C"]],
            hovertemplate="%{y}<br>%{x}: %{z:.0f} und<extra></extra>",
            text=[[f"{int(v)}" for v in row] for row in z],
            texttemplate="%{text}",textfont=dict(size=9,color="#46352A")))
        fig_heat.update_layout(**PLOT_CFG,height=260,margin=dict(t=20,b=10))
        st.plotly_chart(fig_heat,use_container_width=True)

    with col_b:
        st.markdown('<div class="sec-title">🌸 Participación anual de ventas</div>',unsafe_allow_html=True)
        tot={p:sum(DEM_HIST[p]) for p in PRODUCTOS}
        fig_pie=go.Figure(go.Pie(
            labels=[PROD_LABELS_SHORT[p] for p in PRODUCTOS],values=list(tot.values()),
            hole=0.55,marker=dict(colors=list(PROD_COLORS.values()),line=dict(color="white",width=3)),
            textfont=dict(size=11),
            hovertemplate="%{label}<br>%{value:,.0f} und/año<br>%{percent}<extra></extra>"))
        fig_pie.update_layout(**PLOT_CFG,height=260,margin=dict(t=10,b=10),
            annotations=[dict(text="<b>Mix</b><br>anual",x=0.5,y=0.5,
                              font=dict(size=11,color="#46352A"),showarrow=False)],
            legend=dict(orientation="v",x=1,y=0.5,font=dict(size=11)))
        st.plotly_chart(fig_pie,use_container_width=True)

    st.markdown('<div class="sec-title">⏱️ Demanda total en Horas-Hombre por mes</div>',unsafe_allow_html=True)
    lr_ref = hh_por_mes_default
    cols_hh=[C["butter"] if i!=mes_idx else C["mocha"] for i in range(12)]
    fig_hh=go.Figure()
    fig_hh.add_trace(go.Bar(x=MESES_ES,y=list(dem_h.values()),marker_color=cols_hh,
                            marker_line_color="white",marker_line_width=1.5,
                            hovertemplate="%{x}: %{y:.1f} H-H<extra></extra>",showlegend=False))
    fig_hh.add_trace(go.Scatter(x=MESES_ES,y=list(dem_h.values()),mode="lines+markers",
                                line=dict(color=C["mocha"],width=2),marker=dict(size=6),showlegend=False))
    fig_hh.add_hline(y=lr_ref,line_dash="dash",line_color="#8B5E3C",
                     annotation_text=f"Cap. base: {lr_ref:,.0f} H-H",annotation_font_color="#8B5E3C")
    fig_hh.update_layout(**PLOT_CFG,height=280,xaxis_title="Mes",yaxis_title="H-H",
                         xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"),margin=dict(t=20))
    st.plotly_chart(fig_hh,use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — PLAN AGREGADO
# Parámetros propios: costos, fuerza laboral, factores estratégicos
# ─────────────────────────────────────────────────────────────────────────────
with tabs[1]:
    st.markdown('<div class="sec-title">📋 Planeación Agregada — Optimización LP (PuLP)</div>',
                unsafe_allow_html=True)

    # ── Parámetros específicos de Planeación Agregada ────────────────────────
    with st.expander("⚙️ Parámetros de Planeación Agregada", expanded=True):
        st.markdown('<div class="param-box"><div class="param-box-title">💰 Costos operativos</div></div>',
                    unsafe_allow_html=True)
        ca1,ca2,ca3,ca4 = st.columns(4)
        ct  = ca1.number_input("Prod/H-H (Ct)",     value=4_310,   step=100)
        ht  = ca2.number_input("Inventario (Ht)",   value=100_000, step=1000)
        pit = ca3.number_input("Backlog (PIt)",     value=100_000, step=1000)
        stock_obj = ca4.slider("Stock seguridad (×dem)", 0.0, 0.5, 0.0, 0.05)

        st.markdown('<div class="param-box"><div class="param-box-title">👷 Mano de obra</div></div>',
                    unsafe_allow_html=True)
        cb1,cb2,cb3,cb4 = st.columns(4)
        crt = cb1.number_input("H. regular (CRt)", value=11_364, step=100)
        cot = cb2.number_input("H. extra (COt)",   value=14_205, step=100)
        cwp = cb3.number_input("Contratar (CW+)",  value=14_204, step=100)
        cwm = cb4.number_input("Despedir (CW−)",   value=15_061, step=100)

        st.markdown('<div class="param-box"><div class="param-box-title">🏗️ Capacidad laboral</div></div>',
                    unsafe_allow_html=True)
        cc1,cc2,cc3,cc4 = st.columns(4)
        trab       = cc1.number_input("Trabajadores", value=10, step=1)
        turnos_dia = cc2.slider("Turnos/día",  1, 3, 1)
        horas_t    = cc3.slider("Horas/turno", 6, 12, 8)
        dias_mes   = cc4.slider("Días/mes",    18, 26, 22)

        st.markdown('<div class="param-box"><div class="param-box-title">⚡ Factores estratégicos</div></div>',
                    unsafe_allow_html=True)
        cd1,cd2,cd3 = st.columns(3)
        eficiencia   = cd1.slider("Eficiencia (%)",      50, 100, 85, 1)
        ausentismo   = cd2.slider("Ausentismo (%)",       0,  20,  5, 1)
        flexibilidad = cd3.slider("Flexibilidad HH (%)",  0,  30, 10, 1)

    # Recalcular con parámetros del tab
    factor_ef  = (eficiencia/100)*(1-ausentismo/100)*(1+flexibilidad/100)
    hh_mes     = trab*turnos_dia*horas_t*dias_mes*factor_ef
    params_agr = {"Ct":ct,"Ht":ht,"PIt":pit,"CRt":crt,"COt":cot,
                  "CW_mas":cwp,"CW_menos":cwm,"M":1,
                  "LR_inicial":round(hh_mes,2),"stock_obj":stock_obj}
    dem_h_agr  = dem_horas_hombre(DEM_HIST)

    with st.spinner("⚙️ Recalculando plan agregado..."):
        df_agr2, costo2 = run_agregacion(
            tuple(dem_h_agr.items()), tuple(sorted(params_agr.items()))
        )

    st.markdown(f'<div class="info-box"><b>{trab} trabajadores</b> · {turnos_dia} turno(s)/día · '
                f'{horas_t}h/turno · {dias_mes} días/mes<br>'
                f'Eficiencia efectiva: <b>{factor_ef*100:.1f}%</b> → '
                f'Capacidad: <b>{hh_mes:,.0f} H-H/mes</b> · '
                f'Stock seguridad: {stock_obj*100:.0f}%</div>', unsafe_allow_html=True)

    m1,m2,m3,m4 = st.columns(4)
    m1.metric("💰 Costo Total",    f"${costo2:,.0f} COP")
    m2.metric("⏰ Horas Extra",     f"{df_agr2['Horas_Extras'].sum():,.0f} H-H")
    m3.metric("📉 Backlog Total",   f"{df_agr2['Backlog_HH'].sum():,.0f} H-H")
    m4.metric("👥 Contrat. Netas", f"{df_agr2['Contratacion'].sum()-df_agr2['Despidos'].sum():+.0f} pers.")

    st.markdown('<div class="sec-title">📊 Producción vs Demanda (H-H)</div>',unsafe_allow_html=True)
    fig_agr2=go.Figure()
    fig_agr2.add_trace(go.Bar(x=df_agr2["Mes_ES"],y=df_agr2["Inv_Ini_HH"],name="Inv. Inicial H-H",
                              marker_color=C["sky"],opacity=0.8,marker_line_color="white",marker_line_width=1))
    fig_agr2.add_trace(go.Bar(x=df_agr2["Mes_ES"],y=df_agr2["Produccion_HH"],name="Producción H-H",
                              marker_color=C["butter"],opacity=0.9,marker_line_color="white",marker_line_width=1))
    fig_agr2.add_trace(go.Scatter(x=df_agr2["Mes_ES"],y=df_agr2["Demanda_HH"],mode="lines+markers",
                                  name="Demanda H-H",line=dict(color=C["mocha"],dash="dash",width=2.5),
                                  marker=dict(size=8,color=C["mocha"])))
    fig_agr2.add_trace(go.Scatter(x=df_agr2["Mes_ES"],y=df_agr2["Horas_Regulares"],mode="lines",
                                  name="Cap. Regular",line=dict(color=C["rose_d"],dash="dot",width=2)))
    fig_agr2.add_vline(x=mes_idx,line_dash="dot",line_color=C["gold"],
                       annotation_text=f"★ {MESES_F[mes_idx]}",annotation_font_color=C["gold"])
    fig_agr2.update_layout(**PLOT_CFG,barmode="stack",height=380,
                           title=f"Costo Óptimo LP: COP ${costo2:,.0f}",
                           xaxis_title="Mes",yaxis_title="Horas-Hombre",
                           legend=dict(orientation="h",y=-0.22,x=0.5,xanchor="center"),
                           xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"))
    st.plotly_chart(fig_agr2,use_container_width=True)

    col1,col2 = st.columns(2)
    with col1:
        st.markdown('<div class="sec-title">👷 Fuerza laboral</div>',unsafe_allow_html=True)
        fig_fl=go.Figure()
        fig_fl.add_trace(go.Bar(x=df_agr2["Mes_ES"],y=df_agr2["Contratacion"],name="Contrataciones",
                                marker_color=C["mint"],marker_line_color="white",marker_line_width=1))
        fig_fl.add_trace(go.Bar(x=df_agr2["Mes_ES"],y=df_agr2["Despidos"],name="Despidos",
                                marker_color=C["rose"],marker_line_color="white",marker_line_width=1))
        fig_fl.update_layout(**PLOT_CFG,barmode="group",height=290,
                             legend=dict(orientation="h",y=-0.3,x=0.5,xanchor="center"),
                             xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"))
        st.plotly_chart(fig_fl,use_container_width=True)
    with col2:
        st.markdown('<div class="sec-title">⚡ Horas Extra & Backlog</div>',unsafe_allow_html=True)
        fig_ex=go.Figure()
        fig_ex.add_trace(go.Bar(x=df_agr2["Mes_ES"],y=df_agr2["Horas_Extras"],name="Horas Extra",
                                marker_color=C["peach"],marker_line_color="white",marker_line_width=1))
        fig_ex.add_trace(go.Bar(x=df_agr2["Mes_ES"],y=df_agr2["Backlog_HH"],name="Backlog",
                                marker_color=C["rose"],marker_line_color="white",marker_line_width=1))
        fig_ex.update_layout(**PLOT_CFG,barmode="group",height=290,
                             legend=dict(orientation="h",y=-0.3,x=0.5,xanchor="center"),
                             xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"))
        st.plotly_chart(fig_ex,use_container_width=True)

    with st.expander("📄 Ver tabla completa del plan"):
        df_show=df_agr2.drop(columns=["Mes","Mes_ES"]).rename(columns={"Mes_F":"Mes"})
        st.dataframe(df_show.style.format({c:"{:,.1f}" for c in df_show.columns if c!="Mes"})
                     .background_gradient(subset=["Produccion_HH","Horas_Extras"],cmap="YlOrBr"),
                     use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — DESAGREGACIÓN
# Parámetros propios: costo penalización, inventario, suavizado, protección mix
# ─────────────────────────────────────────────────────────────────────────────
with tabs[2]:
    st.markdown('<div class="sec-title">📦 Desagregación del plan en unidades por producto</div>',
                unsafe_allow_html=True)

    with st.expander("⚙️ Parámetros de Desagregación", expanded=True):
        st.markdown('<div class="param-box"><div class="param-box-title">📦 Controles de distribución</div>'
                    'Ajusta cómo se distribuye el plan entre productos. '
                    '<b>Penalización alta</b> → prioriza servicio. '
                    '<b>Inventario alto</b> → minimiza stock acumulado.</div>',
                    unsafe_allow_html=True)
        dd1,dd2,dd3,dd4 = st.columns(4)
        costo_pen_des  = dd1.number_input("⚠️ Penalización backlog", value=150_000, step=5000)
        costo_inv_des  = dd2.number_input("📦 Costo inventario/und", value=100_000, step=5000)
        suavizado_des  = dd3.slider("〰️ Suavizado producción", 0, 5000, 500, 100,
                                     help="Evita cambios bruscos de producción entre meses")
        proteccion_mix = dd4.checkbox("🔒 Proteger proporciones de mix", value=False,
                                       help="Mantiene las proporciones relativas entre productos")

    # Recalcular desagregación con parámetros propios
    prod_hh_agr2 = dict(zip(df_agr2["Mes"], df_agr2["Produccion_HH"]))
    dem_hist_items2 = tuple((p, tuple(DEM_HIST[p])) for p in PRODUCTOS)

    with st.spinner("🔢 Recalculando desagregación..."):
        desag2 = run_desagregacion(
            tuple(prod_hh_agr2.items()), dem_hist_items2,
            costo_pen_des, costo_inv_des, suavizado_des, proteccion_mix
        )

    mes_resaltar  = st.selectbox("Mes a resaltar ★", range(12), index=mes_idx,
                                  format_func=lambda i: MESES_F[i], key="mes_desag")
    mes_nm_desag  = MESES[mes_resaltar]

    plan_mes2 = {p:int(desag2[p].loc[desag2[p]["Mes"]==mes_nm,"Produccion"].values[0])
                 for p in PRODUCTOS}

    st.markdown(f'<div class="info-box">Plan en H-H convertido a unidades · '
                f'Suavizado: <b>{suavizado_des}</b> · '
                f'Penalización backlog: <b>${costo_pen_des:,}</b> · '
                f'Inventario: <b>${costo_inv_des:,}</b></div>', unsafe_allow_html=True)

    # ── Gráfico COMBINADO: Producción + Inventario + Demanda ─────────────────
    st.markdown('<div class="sec-title">📊 Producción · Inventario · Demanda — Vista combinada</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="info-box">Vista consolidada de los tres flujos críticos: '
                'producción, inventario y demanda mes a mes por producto. '
                'La <b>brecha sombreada</b> indica exceso o déficit de producción vs demanda.</div>',
                unsafe_allow_html=True)

    prod_sel = st.selectbox("Producto a analizar", PRODUCTOS,
                             format_func=lambda p: PROD_LABELS[p], key="combo_prod")
    df_c  = desag2[prod_sel]
    pc    = PROD_COLORS[prod_sel]; pcd = PROD_COLORS_DARK[prod_sel]

    fig_combo = make_subplots(rows=2,cols=1,row_heights=[0.65,0.35],shared_xaxes=True,
                              vertical_spacing=0.08,
                              subplot_titles=[f"Producción & Demanda — {PROD_LABELS[prod_sel]}",
                                             "Inventario Final"])
    fig_combo.add_trace(go.Bar(x=df_c["Mes_ES"],y=df_c["Produccion"],name="Producción",
        marker_color=pc,opacity=0.85,marker_line_color=pcd,marker_line_width=1.5,
        hovertemplate="%{x}: <b>%{y:.0f} und</b> producidas<extra></extra>"),row=1,col=1)
    fig_combo.add_trace(go.Scatter(x=df_c["Mes_ES"],y=df_c["Demanda"],name="Demanda",
        mode="lines+markers",line=dict(color=pcd,width=2.5,dash="dash"),
        marker=dict(size=9,color=pc,line=dict(color=pcd,width=2)),
        hovertemplate="%{x}: <b>%{y:.0f} und</b> demanda<extra></extra>"),row=1,col=1)
    # Brecha entre producción y demanda
    fig_combo.add_trace(go.Scatter(x=df_c["Mes_ES"],y=df_c["Produccion"],fill=None,
        mode="lines",line=dict(width=0),showlegend=False,hoverinfo="skip"),row=1,col=1)
    fig_combo.add_trace(go.Scatter(x=df_c["Mes_ES"],y=df_c["Demanda"],fill="tonexty",
        fillcolor=hex_rgba(pc,0.18),mode="lines",line=dict(width=0),
        name="Brecha",hoverinfo="skip"),row=1,col=1)
    # Estrella mes seleccionado
    mr=df_c[df_c["Mes"]==mes_nm_desag]
    if not mr.empty:
        fig_combo.add_trace(go.Scatter(x=[MESES_ES[mes_resaltar]],y=[mr["Produccion"].values[0]],
            mode="markers",marker=dict(size=16,color=C["gold"],symbol="star",
                                        line=dict(color=pcd,width=2)),
            name=f"★ {MESES_F[mes_resaltar]}"),row=1,col=1)
    # Inventario (área)
    fig_combo.add_trace(go.Scatter(x=df_c["Mes_ES"],y=df_c["Inv_Fin"],fill="tozeroy",
        mode="lines+markers",fillcolor=hex_rgba(C["mint"],0.35),
        line=dict(color="#5BAF7A",width=2),marker=dict(size=7,color="#5BAF7A"),
        name="Inventario Final",
        hovertemplate="%{x}: %{y:.0f} und inventario<extra></extra>"),row=2,col=1)
    if df_c["Backlog"].sum()>0:
        fig_combo.add_trace(go.Bar(x=df_c["Mes_ES"],y=df_c["Backlog"],name="Backlog",
            marker_color=C["rose"],opacity=0.8,
            hovertemplate="%{x}: %{y:.0f} und backlog<extra></extra>"),row=2,col=1)
    fig_combo.update_layout(**PLOT_CFG,height=500,barmode="group",
                            legend=dict(orientation="h",y=-0.12,x=0.5,xanchor="center"),
                            margin=dict(t=60,b=20))
    fig_combo.update_xaxes(showgrid=False)
    fig_combo.update_yaxes(gridcolor="#F0E8D8",row=1,col=1)
    fig_combo.update_yaxes(gridcolor="#F0E8D8",row=2,col=1)
    st.plotly_chart(fig_combo,use_container_width=True)

    # ── Grid todos los productos ─────────────────────────────────────────────
    st.markdown('<div class="sec-title">📐 Plan desagregado — Todos los productos</div>',
                unsafe_allow_html=True)
    fig_des=make_subplots(rows=3,cols=2,
                          subplot_titles=[PROD_LABELS[p] for p in PRODUCTOS],
                          vertical_spacing=0.12,horizontal_spacing=0.08)
    for idx,p in enumerate(PRODUCTOS):
        r,c=idx//2+1,idx%2+1; df_p=desag2[p]
        fig_des.add_trace(go.Bar(x=df_p["Mes_ES"],y=df_p["Produccion"],
                                 marker_color=PROD_COLORS[p],opacity=0.88,showlegend=False,
                                 marker_line_color="white",marker_line_width=1),row=r,col=c)
        fig_des.add_trace(go.Scatter(x=df_p["Mes_ES"],y=df_p["Demanda"],mode="lines+markers",
                                     line=dict(color=PROD_COLORS_DARK[p],dash="dash",width=1.5),
                                     marker=dict(size=5),showlegend=False),row=r,col=c)
        mr2=df_p[df_p["Mes"]==mes_nm_desag]
        if not mr2.empty:
            fig_des.add_trace(go.Scatter(x=[MESES_ES[mes_resaltar]],y=[mr2["Produccion"].values[0]],
                mode="markers",marker=dict(size=14,color=C["gold"],symbol="star"),
                showlegend=False),row=r,col=c)
    fig_des.update_layout(**PLOT_CFG,height=680,margin=dict(t=60))
    for i in range(1,4):
        for j in range(1,3):
            fig_des.update_xaxes(showgrid=False,row=i,col=j)
            fig_des.update_yaxes(gridcolor="#F0E8D8",row=i,col=j)
    st.plotly_chart(fig_des,use_container_width=True)

    # ── Cobertura ─────────────────────────────────────────────────────────
    st.markdown('<div class="sec-title">🎯 Cobertura de demanda anual</div>',unsafe_allow_html=True)
    prods_c,cob_vals,und_prod,und_dem=[],[],[],[]
    for p in PRODUCTOS:
        df_p=desag2[p]; tp_=df_p["Produccion"].sum(); td_=df_p["Demanda"].sum()
        cob=round(min(tp_/max(td_,1)*100,100),1)
        prods_c.append(PROD_LABELS_SHORT[p]); cob_vals.append(cob)
        und_prod.append(int(tp_)); und_dem.append(int(td_))

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

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — SIMULACIÓN
# Parámetros propios: capacidades, tiempos, falla, variabilidad, espaciamiento
# ─────────────────────────────────────────────────────────────────────────────
with tabs[3]:
    st.markdown('<div class="sec-title">🏭 Simulación Operativa — Gemelo Digital SimPy</div>',
                unsafe_allow_html=True)

    with st.expander("⚙️ Parámetros de Simulación", expanded=True):
        st.markdown('<div class="param-box"><div class="param-box-title">🏗️ Capacidades por estación (nº equipos)</div></div>',
                    unsafe_allow_html=True)
        sc1,sc2,sc3,sc4,sc5,sc6 = st.columns(6)
        mezcla_cap       = sc1.slider("🥣 Mezcla",       1,6,2)
        dosificado_cap   = sc2.slider("🔧 Dosificado",   1,6,2)
        cap_horno_sim    = sc3.slider("🔥 Horno",        1,8,3)
        enfriamiento_cap = sc4.slider("❄️ Enfriamiento", 1,8,4)
        empaque_cap      = sc5.slider("📦 Empaque",      1,6,2)
        amasado_cap      = sc6.slider("👐 Amasado",      1,4,1)

        st.markdown('<div class="param-box"><div class="param-box-title">🎛️ Lógica de simulación</div></div>',
                    unsafe_allow_html=True)
        sl1,sl2,sl3,sl4,sl5 = st.columns(5)
        falla_horno_sim = sl1.checkbox("⚠️ Fallas en horno")
        doble_turno_sim = sl2.checkbox("🕐 Doble turno")
        variabilidad_sim= sl3.slider("📉 Variabilidad tiempos",0.5,2.0,1.0,0.1)
        espaciamiento_sim=sl4.slider("📏 Espaciamiento lotes", 0.5,2.0,1.0,0.1)
        iter_sim        = sl5.slider("🔁 Iteraciones",          1,5,1)

        st.markdown('<div class="param-box"><div class="param-box-title">⏱️ Tiempos de proceso por estación (min mín–máx)</div></div>',
                    unsafe_allow_html=True)
        st1,st2,st3 = st.columns(3)
        tm  = st1.slider("🥣 Mezcla",       1,60,[12,18])
        td  = st2.slider("🔧 Dosificado",   1,60,[8,24])
        th  = st3.slider("🔥 Horno",        5,120,[20,48])
        st4,st5,st6 = st.columns(3)
        te  = st4.slider("❄️ Enfriamiento", 5,120,[25,72])
        tep = st5.slider("📦 Empaque",      1,30,[4,12])
        ta_ = st6.slider("👐 Amasado",      5,60,[16,24])

    factor_t_sim = 0.80 if doble_turno_sim else 1.0
    cap_rec_sim  = {"mezcla":mezcla_cap,"dosificado":dosificado_cap,"horno":cap_horno_sim,
                   "enfriamiento":enfriamiento_cap,"empaque":empaque_cap,"amasado":amasado_cap}

    # Actualizar rutas con tiempos personalizados
    import copy
    RUTAS_SIM = copy.deepcopy(RUTAS)
    tiempos_custom = {"mezcla":tm,"dosificado":td,"horno":th,"enfriamiento":te,"empaque":tep,"amasado":ta_}
    for p in RUTAS_SIM:
        RUTAS_SIM[p] = [(etapa,rec,tiempos_custom.get(rec,[tmin,tmax])[0],
                         tiempos_custom.get(rec,[tmin,tmax])[1])
                        for etapa,rec,tmin,tmax in RUTAS_SIM[p]]

    with st.spinner("🏭 Simulando con parámetros actualizados..."):
        df_lotes2,df_uso2,df_sensores2 = run_simulacion_cached(
            tuple(plan_mes2.items()), tuple(cap_rec_sim.items()),
            falla_horno_sim, factor_t_sim,
            variabilidad_sim, espaciamiento_sim, int(semilla)
        )

    df_kpis2  = calc_kpis(df_lotes2, plan_mes2)
    df_util2  = calc_utilizacion(df_uso2)

    st.markdown(f'<div class="info-box">Mes simulado: <b>{MESES_F[mes_idx]}</b> · '
                f'Lotes: <b>{len(df_lotes2)}</b> · '
                f'{"⚠️ Falla horno activa" if falla_horno_sim else "✓ Sin fallas"} · '
                f'{"🕐 Doble turno" if doble_turno_sim else "Turno estándar"} · '
                f'Variabilidad ×{variabilidad_sim}</div>', unsafe_allow_html=True)

    # ── KPIs de simulación ──────────────────────────────────────────────────
    if not df_kpis2.empty:
        st.markdown('<div class="sec-title">📈 KPIs de Producción</div>',unsafe_allow_html=True)
        cols_kpi = st.columns(len(df_kpis2))
        for i,(_, row) in enumerate(df_kpis2.iterrows()):
            p_name = list(PRODUCTOS)[i] if i < len(PRODUCTOS) else ""
            cols_kpi[i].metric(
                row["Producto"],
                f"{row['Cumplimiento %']:.1f}%",
                f"TP: {row['Throughput (und/h)']:.2f} und/h"
            )

    # ── Gráfico Producción + Inventario + Demanda por mes (simulación) ─────
    st.markdown('<div class="sec-title">📊 Producción · Inventario · Demanda — Mes simulado</div>',
                unsafe_allow_html=True)
    prod_sel_sim = st.selectbox("Producto a visualizar", PRODUCTOS,
                                 format_func=lambda p: PROD_LABELS[p], key="sim_prod")
    df_cs  = desag2[prod_sel_sim]
    pcs    = PROD_COLORS[prod_sel_sim]; pcsd = PROD_COLORS_DARK[prod_sel_sim]

    fig_sim_combo = make_subplots(rows=2,cols=1,row_heights=[0.65,0.35],shared_xaxes=True,
                                  vertical_spacing=0.08,
                                  subplot_titles=[f"Producción & Demanda — {PROD_LABELS[prod_sel_sim]}",
                                                 "Inventario Final"])
    fig_sim_combo.add_trace(go.Bar(x=df_cs["Mes_ES"],y=df_cs["Produccion"],name="Producción",
        marker_color=pcs,opacity=0.85,marker_line_color=pcsd,marker_line_width=1.5),row=1,col=1)
    fig_sim_combo.add_trace(go.Scatter(x=df_cs["Mes_ES"],y=df_cs["Demanda"],name="Demanda",
        mode="lines+markers",line=dict(color=pcsd,width=2.5,dash="dash"),
        marker=dict(size=9,color=pcs,line=dict(color=pcsd,width=2))),row=1,col=1)
    fig_sim_combo.add_trace(go.Scatter(x=df_cs["Mes_ES"],y=df_cs["Inv_Fin"],fill="tozeroy",
        mode="lines+markers",fillcolor=hex_rgba(C["mint"],0.35),
        line=dict(color="#5BAF7A",width=2),marker=dict(size=7,color="#5BAF7A"),
        name="Inventario Final"),row=2,col=1)
    # Marcar mes simulado
    fig_sim_combo.add_vline(x=mes_idx,line_dash="dot",line_color=C["gold"],
                            annotation_text=f"★ {MESES_F[mes_idx]}",annotation_font_color=C["gold"],row=1,col=1)
    fig_sim_combo.update_layout(**PLOT_CFG,height=460,barmode="group",
                                legend=dict(orientation="h",y=-0.12,x=0.5,xanchor="center"),
                                margin=dict(t=60,b=20))
    fig_sim_combo.update_xaxes(showgrid=False)
    fig_sim_combo.update_yaxes(gridcolor="#F0E8D8")
    st.plotly_chart(fig_sim_combo,use_container_width=True)

    # ── Utilización de recursos ─────────────────────────────────────────────
    if not df_util2.empty:
        st.markdown('<div class="sec-title">⚙️ Utilización de Recursos & Cuellos de Botella</div>',
                    unsafe_allow_html=True)
        cuellos=df_util2[df_util2["Cuello Botella"]]
        if not cuellos.empty:
            for _,row in cuellos.iterrows():
                st.markdown(f'<div class="pill-warn">⚠️ Cuello: <b>{row["Recurso"]}</b> — '
                            f'{row["Utilizacion_%"]:.1f}% · Cola prom: {row["Cola Prom"]:.2f}</div><br>',
                            unsafe_allow_html=True)
        else:
            st.markdown('<div class="pill-ok">✅ Sin cuellos de botella detectados</div><br>',
                        unsafe_allow_html=True)

        REC_LBL={"mezcla":"🥣 Mezcla","dosificado":"🔧 Dosificado","horno":"🔥 Horno",
                 "enfriamiento":"❄️ Enfriamiento","empaque":"📦 Empaque","amasado":"👐 Amasado"}
        rec_lb=[REC_LBL.get(r,r) for r in df_util2["Recurso"]]
        col_u2=[C["rose"] if u>=80 else C["butter"] if u>=60 else C["mint"]
                for u in df_util2["Utilizacion_%"]]

        fig_util2_g=make_subplots(rows=1,cols=2,subplot_titles=["Utilización (%)","Cola Promedio"])
        fig_util2_g.add_trace(go.Bar(x=rec_lb,y=df_util2["Utilizacion_%"],marker_color=col_u2,
            marker_line_color="white",marker_line_width=2,
            text=[f"{v:.0f}%" for v in df_util2["Utilizacion_%"]],textposition="outside",
            showlegend=False),row=1,col=1)
        fig_util2_g.add_trace(go.Bar(x=rec_lb,y=df_util2["Cola Prom"],marker_color=C["lavender"],
            marker_line_color="white",marker_line_width=2,
            text=[f"{v:.2f}" for v in df_util2["Cola Prom"]],textposition="outside",
            showlegend=False),row=1,col=2)
        fig_util2_g.add_hline(y=80,line_dash="dash",line_color=C["rose_d"],
                              annotation_text="⚠ 80%",row=1,col=1)
        fig_util2_g.update_layout(**PLOT_CFG,height=320)
        fig_util2_g.update_xaxes(showgrid=False); fig_util2_g.update_yaxes(gridcolor="#F0E8D8")
        st.plotly_chart(fig_util2_g,use_container_width=True)

    # ── Gantt ───────────────────────────────────────────────────────────────
    if not df_lotes2.empty:
        st.markdown('<div class="sec-title">📅 Diagrama de Gantt — Flujo de lotes</div>',
                    unsafe_allow_html=True)
        n_gantt=min(60,len(df_lotes2)); sub=df_lotes2.head(n_gantt).reset_index(drop=True)
        fig_gantt2=go.Figure()
        for _,row in sub.iterrows():
            fig_gantt2.add_trace(go.Bar(
                x=[row["tiempo_sistema"]],y=[row["lote_id"]],base=[row["t_creacion"]],
                orientation="h",marker_color=PROD_COLORS.get(row["producto"],"#ccc"),
                opacity=0.85,showlegend=False,marker_line_color="white",marker_line_width=0.5,
                hovertemplate=(f"<b>{PROD_LABELS_SHORT.get(row['producto'],row['producto'])}</b><br>"
                               f"Inicio: {row['t_creacion']:.0f} min<br>"
                               f"Duración: {row['tiempo_sistema']:.1f} min<extra></extra>"),
            ))
        for p,c in PROD_COLORS.items():
            fig_gantt2.add_trace(go.Bar(x=[None],y=[None],marker_color=c,name=PROD_LABELS_SHORT[p]))
        fig_gantt2.update_layout(**PLOT_CFG,barmode="overlay",height=max(380,n_gantt*8),
                                 title=f"Gantt — Primeros {n_gantt} lotes",
                                 xaxis_title="Tiempo simulado (min)",
                                 legend=dict(orientation="h",y=-0.1,x=0.5,xanchor="center"),
                                 yaxis=dict(showticklabels=False))
        st.plotly_chart(fig_gantt2,use_container_width=True)

        st.markdown('<div class="sec-title">🎻 Distribución de tiempos en sistema</div>',
                    unsafe_allow_html=True)
        fig_vio=go.Figure()
        for p in PRODUCTOS:
            sub_v=df_lotes2[df_lotes2["producto"]==p]["tiempo_sistema"]
            if len(sub_v)<3: continue
            fig_vio.add_trace(go.Violin(y=sub_v,name=PROD_LABELS_SHORT[p],
                box_visible=True,meanline_visible=True,
                fillcolor=PROD_COLORS[p],line_color=PROD_COLORS_DARK[p],opacity=0.82))
        fig_vio.update_layout(**PLOT_CFG,height=320,yaxis_title="Tiempo en sistema (min)",
                              showlegend=False,violinmode="overlay")
        st.plotly_chart(fig_vio,use_container_width=True)

        with st.expander("📊 Ver tabla completa de KPIs"):
            if not df_kpis2.empty:
                st.dataframe(df_kpis2.style.format({c:"{:,.2f}"
                             for c in df_kpis2.columns if c!="Producto"})
                             .background_gradient(subset=["Cumplimiento %"],cmap="YlGn"),
                             use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 5 — SENSORES
# Sin parámetros propios — lee resultados de simulación
# ─────────────────────────────────────────────────────────────────────────────
with tabs[4]:
    st.markdown('<div class="sec-title">🌡️ Sensores Virtuales — Monitor del Horno</div>',
                unsafe_allow_html=True)
    st.markdown(f'<div class="info-box">Gemelo digital IoT · '
                f'Variabilidad térmica: ×{variabilidad_sim} · '
                f'Capacidad del horno: {cap_horno_sim} estaciones · '
                f'Límite operativo: 200°C · '
                f'Datos en tiempo real de la simulación activa</div>', unsafe_allow_html=True)

    df_sens_use = df_sensores2 if not df_sensores2.empty else df_sensores
    excesos_sens = int((df_sens_use["temperatura"]>200).sum()) if not df_sens_use.empty else 0

    if not df_sens_use.empty:
        s1,s2,s3,s4 = st.columns(4)
        s1.metric("🌡️ Temp. mínima",   f"{df_sens_use['temperatura'].min():.1f} °C")
        s2.metric("🔥 Temp. máxima",   f"{df_sens_use['temperatura'].max():.1f} °C")
        s3.metric("📊 Temp. promedio", f"{df_sens_use['temperatura'].mean():.1f} °C")
        s4.metric("⚠️ Excesos >200°C", excesos_sens,
                  delta="Revisar horno" if excesos_sens else "Operación normal",
                  delta_color="inverse" if excesos_sens else "off")

        # Gráfica principal: temperatura
        fig_temp=go.Figure()
        fig_temp.add_hrect(y0=150,y1=200,fillcolor=hex_rgba(C["mint"],0.21),line_width=0,
                           annotation_text="Zona operativa óptima",annotation_font_color=C["sage"])
        fig_temp.add_trace(go.Scatter(x=df_sens_use["tiempo"],y=df_sens_use["temperatura"],
            mode="lines",name="Temperatura",fill="tozeroy",
            fillcolor=hex_rgba(C["peach"],0.13),
            line=dict(color=C["mocha"],width=1.8)))
        if len(df_sens_use)>10:
            mm=df_sens_use["temperatura"].rolling(5,min_periods=1).mean()
            fig_temp.add_trace(go.Scatter(x=df_sens_use["tiempo"],y=mm,mode="lines",
                name="Media móvil",line=dict(color=C["rose_d"],width=2,dash="dot")))
        fig_temp.add_hline(y=200,line_dash="dash",line_color="#C0392B",
                           annotation_text="⚠ Límite 200°C",annotation_font_color="#C0392B")
        fig_temp.update_layout(**PLOT_CFG,height=320,xaxis_title="Tiempo simulado (min)",
            yaxis_title="°C",title="Temperatura del Horno — Monitoreo Simulado",
            legend=dict(orientation="h",y=-0.22,x=0.5,xanchor="center"),
            xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"))
        st.plotly_chart(fig_temp,use_container_width=True)

        col_s1,col_s2 = st.columns(2)
        with col_s1:
            fig_ocup=go.Figure()
            fig_ocup.add_trace(go.Scatter(x=df_sens_use["tiempo"],y=df_sens_use["horno_ocup"],
                mode="lines",fill="tozeroy",fillcolor=hex_rgba(C["sky"],0.25),
                line=dict(color="#4A90C4",width=2),name="Ocupación"))
            fig_ocup.add_hline(y=cap_horno_sim,line_dash="dot",line_color=C["mocha"],
                               annotation_text=f"Cap. máx: {cap_horno_sim}")
            fig_ocup.update_layout(**PLOT_CFG,height=260,title="Ocupación del Horno",
                xaxis_title="min",yaxis_title="Estaciones activas",
                xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"),showlegend=False)
            st.plotly_chart(fig_ocup,use_container_width=True)
        with col_s2:
            fig_hist_s=go.Figure()
            fig_hist_s.add_trace(go.Histogram(x=df_sens_use["temperatura"],nbinsx=35,
                marker_color=C["butter"],opacity=0.85,
                marker_line_color="white",marker_line_width=1))
            fig_hist_s.add_vline(x=200,line_dash="dash",line_color="#C0392B",
                                 annotation_text="200°C")
            fig_hist_s.add_vline(x=df_sens_use["temperatura"].mean(),line_dash="dot",
                                 line_color=C["mocha"],
                                 annotation_text=f"Prom:{df_sens_use['temperatura'].mean():.0f}°C")
            fig_hist_s.update_layout(**PLOT_CFG,height=260,title="Distribución de Temperatura",
                xaxis_title="°C",yaxis_title="Frecuencia",showlegend=False,
                xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#F0E8D8"))
            st.plotly_chart(fig_hist_s,use_container_width=True)
    else:
        st.info("Sin datos de sensores.")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 6 — ESCENARIOS
# ─────────────────────────────────────────────────────────────────────────────
with tabs[5]:
    st.markdown('<div class="sec-title">🔬 Análisis de Escenarios What-If</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="info-box">Compara múltiples configuraciones de planta para '
                'identificar la estrategia óptima. Cada escenario simula condiciones '
                'distintas de demanda, capacidad y operación.</div>', unsafe_allow_html=True)

    ESCENARIOS_DEF = {
        "Base":                  {"fd":1.0,"falla":False,"ft":1.0,"cap_delta":0,"var":1.0},
        "Impulso comercial +20%":{"fd":1.2,"falla":False,"ft":1.0,"cap_delta":0,"var":1.0},
        "Contracción −20%":      {"fd":0.8,"falla":False,"ft":1.0,"cap_delta":0,"var":1.0},
        "Horno inestable":       {"fd":1.0,"falla":True, "ft":1.0,"cap_delta":0,"var":1.5},
        "Restricción capacidad": {"fd":1.0,"falla":False,"ft":1.0,"cap_delta":-1,"var":1.0},
        "Capacidad ampliada":    {"fd":1.0,"falla":False,"ft":1.0,"cap_delta":+1,"var":1.0},
        "Ritmo extendido":       {"fd":1.0,"falla":False,"ft":0.80,"cap_delta":0,"var":1.0},
        "Optimizado":            {"fd":1.0,"falla":False,"ft":0.85,"cap_delta":+1,"var":0.9},
    }
    ESC_ICONS={"Base":"🏠","Impulso comercial +20%":"📈","Contracción −20%":"📉",
               "Horno inestable":"⚠️","Restricción capacidad":"⬇️","Capacidad ampliada":"⬆️",
               "Ritmo extendido":"🕐","Optimizado":"🚀"}

    esc_sel=st.multiselect("Selecciona escenarios a comparar",
                            list(ESCENARIOS_DEF.keys()),
                            default=["Base","Impulso comercial +20%","Horno inestable",
                                     "Ritmo extendido","Optimizado"])

    if st.button("🚀 Comparar escenarios seleccionados", type="primary"):
        filas_esc=[]; prog=st.progress(0)
        for i,nm in enumerate(esc_sel):
            prog.progress((i+1)/len(esc_sel),text=f"Simulando: {nm}...")
            cfg=ESCENARIOS_DEF[nm]
            plan_esc={p:max(int(u*cfg["fd"]),0) for p,u in plan_mes2.items()}
            cap_esc={**cap_rec_sim,"horno":max(cap_horno_sim+cfg["cap_delta"],1)}
            df_l_e,df_u_e,_=run_simulacion_cached(
                tuple(plan_esc.items()),tuple(cap_esc.items()),
                cfg["falla"],cfg["ft"],cfg["var"],espaciamiento_sim,int(semilla))
            k=calc_kpis(df_l_e,plan_esc); u=calc_utilizacion(df_u_e)
            fila={"Escenario":ESC_ICONS.get(nm,"")+" "+nm}
            if not k.empty:
                fila["Throughput (und/h)"]=round(k["Throughput (und/h)"].mean(),2)
                fila["Lead Time (min)"]   =round(k["Lead Time (min/lote)"].mean(),2)
                fila["WIP Prom"]          =round(k["WIP Prom"].mean(),2)
                fila["Cumplimiento %"]    =round(k["Cumplimiento %"].mean(),2)
            if not u.empty:
                fila["Util. max %"]    =round(u["Utilizacion_%"].max(),2)
                fila["Cuellos botella"]=int(u["Cuello Botella"].sum())
            fila["Lotes prod."]=len(df_l_e)
            filas_esc.append(fila)
        prog.empty()
        df_comp=pd.DataFrame(filas_esc)

        st.markdown('<div class="sec-title">📊 Resultados comparativos</div>',unsafe_allow_html=True)
        num_cols=[c for c in df_comp.columns if c not in ["Escenario"] and df_comp[c].dtype!="object"]
        st.dataframe(df_comp.style.format({c:"{:,.2f}" for c in num_cols})
                     .background_gradient(
                         subset=["Cumplimiento %"] if "Cumplimiento %" in df_comp.columns else [],
                         cmap="YlGn"),use_container_width=True)

        if len(df_comp)>1:
            col_e1,col_e2=st.columns(2)
            with col_e1:
                st.markdown('<div class="sec-title">✅ Cumplimiento por escenario</div>',
                            unsafe_allow_html=True)
                if "Cumplimiento %" in df_comp.columns:
                    col_c=[C["mint"] if v>=90 else C["butter"] if v>=70 else C["rose"]
                           for v in df_comp["Cumplimiento %"]]
                    fig_ec=go.Figure(go.Bar(x=df_comp["Escenario"],y=df_comp["Cumplimiento %"],
                        marker_color=col_c,marker_line_color="white",marker_line_width=2,
                        text=[f"{v:.1f}%" for v in df_comp["Cumplimiento %"]],textposition="outside"))
                    fig_ec.add_hline(y=100,line_dash="dash",line_color=C["mocha"])
                    fig_ec.update_layout(**PLOT_CFG,height=310,yaxis_title="%",showlegend=False,
                                         xaxis=dict(showgrid=False,tickangle=-25),
                                         yaxis=dict(gridcolor="#F0E8D8"),margin=dict(t=30,b=90))
                    st.plotly_chart(fig_ec,use_container_width=True)
            with col_e2:
                st.markdown('<div class="sec-title">⚙️ Utilización máxima</div>',
                            unsafe_allow_html=True)
                if "Util. max %" in df_comp.columns:
                    col_u=[C["rose"] if v>=80 else C["butter"] if v>=60 else C["mint"]
                           for v in df_comp["Util. max %"]]
                    fig_eu=go.Figure(go.Bar(x=df_comp["Escenario"],y=df_comp["Util. max %"],
                        marker_color=col_u,marker_line_color="white",marker_line_width=2,
                        text=[f"{v:.0f}%" for v in df_comp["Util. max %"]],textposition="outside"))
                    fig_eu.add_hline(y=80,line_dash="dash",line_color=C["rose_d"],
                                     annotation_text="⚠ 80%")
                    fig_eu.update_layout(**PLOT_CFG,height=310,yaxis_title="%",showlegend=False,
                                         xaxis=dict(showgrid=False,tickangle=-25),
                                         yaxis=dict(gridcolor="#F0E8D8"),margin=dict(t=30,b=90))
                    st.plotly_chart(fig_eu,use_container_width=True)

            # Throughput vs Lead Time (scatter)
            st.markdown('<div class="sec-title">🔄 Throughput vs Lead Time</div>',unsafe_allow_html=True)
            if "Throughput (und/h)" in df_comp.columns and "Lead Time (min)" in df_comp.columns:
                pal_e=list(PROD_COLORS.values())+[C["rose"],C["sky"],C["lavender"]]
                fig_sc=go.Figure()
                for i,row in df_comp.iterrows():
                    fig_sc.add_trace(go.Scatter(
                        x=[row.get("Throughput (und/h)",0)],y=[row.get("Lead Time (min)",0)],
                        mode="markers+text",
                        marker=dict(size=18,color=pal_e[i%len(pal_e)],
                                    line=dict(color="white",width=2)),
                        text=[row["Escenario"]],textposition="top center",
                        textfont=dict(size=9),name=row["Escenario"],showlegend=False))
                fig_sc.update_layout(**PLOT_CFG,height=340,
                                     xaxis_title="Throughput (und/h)",
                                     yaxis_title="Lead Time (min)",
                                     xaxis=dict(gridcolor="#F0E8D8"),yaxis=dict(gridcolor="#F0E8D8"))
                st.plotly_chart(fig_sc,use_container_width=True)

            # Radar comparativo
            st.markdown('<div class="sec-title">🕸️ Radar comparativo de escenarios</div>',
                        unsafe_allow_html=True)
            cols_r=[c for c in df_comp.columns
                    if c not in ["Escenario","Cuellos botella"] and df_comp[c].dtype!="object"]
            if len(cols_r)>=3:
                df_norm=df_comp[cols_r].copy()
                for c in df_norm.columns:
                    rng=df_norm[c].max()-df_norm[c].min()
                    df_norm[c]=(df_norm[c]-df_norm[c].min())/rng if rng else 0.5
                COLORES_R=list(PROD_COLORS.values())+[C["rose"],C["sky"],C["lavender"]]
                RGBA_R=[hex_rgba(x,0.15) for x in COLORES_R]
                fig_rad=go.Figure()
                for i,row in df_comp.iterrows():
                    vals=[df_norm.loc[i,c] for c in cols_r]
                    fig_rad.add_trace(go.Scatterpolar(
                        r=vals+[vals[0]],theta=cols_r+[cols_r[0]],fill="toself",
                        name=row["Escenario"],
                        line=dict(color=COLORES_R[i%len(COLORES_R)],width=2),
                        fillcolor=RGBA_R[i%len(RGBA_R)]))
                fig_rad.update_layout(**PLOT_CFG,height=460,
                    polar=dict(
                        radialaxis=dict(visible=True,range=[0,1],gridcolor="#E8D5B0"),
                        angularaxis=dict(gridcolor="#E8D5B0")),
                    title="Comparación normalizada de escenarios",
                    legend=dict(orientation="h",y=-0.15,x=0.5,xanchor="center"))
                st.plotly_chart(fig_rad,use_container_width=True)
    else:
        st.markdown("""
        <div class="info-box" style="text-align:center;padding:2rem;">
          <div style="font-size:2.5rem">🔬</div>
          <b>Selecciona escenarios y haz clic en Comparar</b><br>
          <span style="font-size:0.85rem;color:#9B7B5A;">
          Se simulará cada configuración y se compararán KPIs lado a lado</span>
        </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown(f"""
<div style='text-align:center;color:#B9857E;font-size:0.82rem;
     font-family:DM Sans,sans-serif;padding:0.4rem 0 1rem'>
  🥐 <b>Gemelo Digital — Panadería Dora del Hoyo v4.0</b> &nbsp;·&nbsp;
  LP Agregada · Desagregación LP · SimPy · Streamlit &nbsp;·&nbsp;
  📅 {MESES_F[mes_idx]} · 📈 ×{factor_demanda} · 🧁 {litros_total:,.0f} L
</div>""", unsafe_allow_html=True)
