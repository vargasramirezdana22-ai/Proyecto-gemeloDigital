"""
app.py — Gemelo Digital · Panadería Dora del Hoyo
==================================================
v3.0 — Rediseño pastel completo:
  • Paleta suave sin tonos café
  • Pronóstico de demanda estilo serie temporal profesional
  • Paneles de parámetros inline por sección
  • Gráficos WOW: sunburst, waterfall, funnel, bubble
  • KPIs con indicadores de progreso visuales
  • Análisis de escenarios con coordenadas paralelas

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
# PALETA PASTEL SUAVE — SIN CAFÉ
# ══════════════════════════════════════════════════════════════════════════════
PAL = {
    "bg":       "#F7F9FC",
    "card":     "#FFFFFF",
    "text":     "#2C3E50",
    "text2":    "#7F8C8D",
    "border":   "#E8ECF1",
    "accent1":  "#FFB3BA",
    "accent2":  "#BAE1FF",
    "accent3":  "#BAFFC9",
    "accent4":  "#E8BAFF",
    "accent5":  "#FFFFBA",
    "accent6":  "#FFDFBA",
    "pink":     "#FFB3BA",
    "blue":     "#BAE1FF",
    "green":    "#BAFFC9",
    "lavender": "#E8BAFF",
    "yellow":   "#FFFFBA",
    "peach":    "#FFDFBA",
    "mint":     "#C5F0E3",
    "coral":    "#FFB5B5",
    "sky":      "#B5D8F7",
    "lilac":    "#D4C5F9",
    "rose":     "#FADBD8",
    "sage":     "#D5F5E3",
}

PROD_COLORS = {
    "Brownies":           "#FFB3BA",
    "Mantecadas":         "#BAE1FF",
    "Mantecadas_Amapola": "#BAFFC9",
    "Torta_Naranja":      "#E8BAFF",
    "Pan_Maiz":           "#FFDFBA",
}
PROD_COLORS_MID = {
    "Brownies":           "#FF8A95",
    "Mantecadas":         "#7EC8F0",
    "Mantecadas_Amapola": "#7EE8A0",
    "Torta_Naranja":      "#C895F0",
    "Pan_Maiz":           "#FFC87A",
}
PROD_COLORS_DARK = {
    "Brownies":           "#E05A65",
    "Mantecadas":         "#4A90C4",
    "Mantecadas_Amapola": "#3DAA6A",
    "Torta_Naranja":      "#9B59B6",
    "Pan_Maiz":           "#E67E22",
}
PROD_LABELS = {
    "Brownies":"Brownies","Mantecadas":"Mantecadas",
    "Mantecadas_Amapola":"Mant. Amapola","Torta_Naranja":"Torta Naranja","Pan_Maiz":"Pan de Maíz",
}
PROD_EMOJI = {
    "Brownies":"🍫","Mantecadas":"🧁","Mantecadas_Amapola":"🌸",
    "Torta_Naranja":"🍊","Pan_Maiz":"🌽",
}

def hex_rgba(h, a=0.15):
    h = h.lstrip("#")
    return f"rgba({int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)},{a})"

# ══════════════════════════════════════════════════════════════════════════════
# DATOS MAESTROS
# ══════════════════════════════════════════════════════════════════════════════
PRODUCTOS = ["Brownies","Mantecadas","Mantecadas_Amapola","Torta_Naranja","Pan_Maiz"]
MESES     = ["January","February","March","April","May","June",
             "July","August","September","October","November","December"]
MESES_ES  = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]
MESES_F   = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

DEM_HISTORICA = {
    "Brownies":           [315,804,734,541,494, 59,315,803,734,541,494, 59],
    "Mantecadas":         [125,780,432,910,275, 68,512,834,690,455,389,120],
    "Mantecadas_Amapola": [320,710,520,251,631,150,330,220,710,610,489,180],
    "Torta_Naranja":      [100,250,200,101,190, 50,100,220,200,170,180,187],
    "Pan_Maiz":           [330,140,143, 73, 83, 48, 70, 89,118, 83, 67, 87],
}
HORAS_PRODUCTO = {"Brownies":0.866,"Mantecadas":0.175,"Mantecadas_Amapola":0.175,
                  "Torta_Naranja":0.175,"Pan_Maiz":0.312}
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
TAMANO_LOTE_BASE = {"Brownies":12,"Mantecadas":10,"Mantecadas_Amapola":10,
                    "Torta_Naranja":12,"Pan_Maiz":15}
CAPACIDAD_BASE   = {"mezcla":2,"dosificado":2,"horno":3,"enfriamiento":4,"empaque":2,"amasado":1}
PARAMS_DEFAULT   = {"Ct":4_310,"Ht":100_000,"PIt":100_000,"CRt":11_364,"COt":14_205,
                    "CW_mas":14_204,"CW_menos":15_061,"M":1,"LR_inicial":44*4*10,"inv_seg":0.0}
INV_INICIAL = {p: 0 for p in PRODUCTOS}

REC_LABELS = {"mezcla":"Mezcla","dosificado":"Dosificado","horno":"Horno",
              "enfriamiento":"Enfriamiento","empaque":"Empaque","amasado":"Amasado"}
REC_EMOJI  = {"mezcla":"🥣","dosificado":"🔧","horno":"🔥",
              "enfriamiento":"❄️","empaque":"📦","amasado":"👐"}

# ══════════════════════════════════════════════════════════════════════════════
# FUNCIONES CORE
# ══════════════════════════════════════════════════════════════════════════════

def demanda_horas_hombre(factor=1.0):
    return {m: round(sum(DEM_HISTORICA[p][i]*HORAS_PRODUCTO[p] for p in PRODUCTOS)*factor, 4)
            for i, m in enumerate(MESES)}

def pronostico_simple(serie, meses_extra=3):
    alpha = 0.3; nivel = serie[0]; suavizada = []
    for v in serie:
        nivel = alpha*v + (1-alpha)*nivel; suavizada.append(round(nivel, 1))
    futuro = []; last = suavizada[-1]
    trend = (suavizada[-1]-suavizada[-4])/3 if len(suavizada) >= 4 else 0
    for _ in range(meses_extra):
        last = last + alpha*trend; futuro.append(round(last, 1))
    return suavizada, futuro

@st.cache_data(show_spinner=False)
def run_agregacion(factor_demanda=1.0, params_tuple=None):
    params = PARAMS_DEFAULT.copy()
    if params_tuple: params.update(dict(params_tuple))
    dem_h = demanda_horas_hombre(factor_demanda)
    Ct=params["Ct"]; Ht=params["Ht"]; PIt=params["PIt"]
    CRt=params["CRt"]; COt=params["COt"]; Wm=params["CW_mas"]; Wd=params["CW_menos"]
    M=params["M"]; LRi=params["LR_inicial"]
    mdl = LpProblem("Agregacion", LpMinimize)
    P=LpVariable.dicts("P",MESES,lowBound=0); I=LpVariable.dicts("I",MESES,lowBound=0)
    S=LpVariable.dicts("S",MESES,lowBound=0); LR=LpVariable.dicts("LR",MESES,lowBound=0)
    LO=LpVariable.dicts("LO",MESES,lowBound=0); LU=LpVariable.dicts("LU",MESES,lowBound=0)
    NI=LpVariable.dicts("NI",MESES)
    Wmas=LpVariable.dicts("Wm",MESES,lowBound=0); Wmenos=LpVariable.dicts("Wd",MESES,lowBound=0)
    mdl += lpSum(Ct*P[t]+Ht*I[t]+PIt*S[t]+CRt*LR[t]+COt*LO[t]+Wm*Wmas[t]+Wd*Wmenos[t] for t in MESES)
    for idx, t in enumerate(MESES):
        d = dem_h[t]; tp = MESES[idx-1] if idx > 0 else None
        if idx == 0: mdl += NI[t] == 0+P[t]-d
        else:        mdl += NI[t] == NI[tp]+P[t]-d
        mdl += NI[t] == I[t]-S[t]; mdl += LU[t]+LO[t] == M*P[t]; mdl += LU[t] <= LR[t]
        if idx == 0: mdl += LR[t] == LRi+Wmas[t]-Wmenos[t]
        else:        mdl += LR[t] == LR[tp]+Wmas[t]-Wmenos[t]
    mdl.solve(PULP_CBC_CMD(msg=False)); costo = value(mdl.objective)
    ini_l, fin_l = [], []
    for idx, t in enumerate(MESES):
        ini = 0.0 if idx == 0 else fin_l[-1]; ini_l.append(ini)
        fin_l.append(ini + (P[t].varValue or 0) - dem_h[t])
    df = pd.DataFrame({
        "Mes": MESES, "Mes_F": MESES_F, "Mes_ES": MESES_ES,
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
    prod_hh = dict(prod_hh_items)
    mdl = LpProblem("Desagregacion", LpMinimize)
    X = {(p,t): LpVariable(f"X_{p}_{t}", lowBound=0) for p in PRODUCTOS for t in MESES}
    I = {(p,t): LpVariable(f"I_{p}_{t}", lowBound=0) for p in PRODUCTOS for t in MESES}
    S = {(p,t): LpVariable(f"S_{p}_{t}", lowBound=0) for p in PRODUCTOS for t in MESES}
    mdl += lpSum(100_000*I[p,t]+150_000*S[p,t] for p in PRODUCTOS for t in MESES)
    for idx, t in enumerate(MESES):
        mdl += (lpSum(HORAS_PRODUCTO[p]*X[p,t] for p in PRODUCTOS) <= prod_hh[t], f"Cap_{t}")
        for p in PRODUCTOS:
            d = int(DEM_HISTORICA[p][idx]*factor_demanda)
            if idx == 0: mdl += I[p,t]-S[p,t] == INV_INICIAL[p]+X[p,t]-d
            else:        mdl += I[p,t]-S[p,t] == I[p,MESES[idx-1]]-S[p,MESES[idx-1]]+X[p,t]-d
    mdl.solve(PULP_CBC_CMD(msg=False))
    resultados = {}
    for p in PRODUCTOS:
        filas = []
        for idx, t in enumerate(MESES):
            xv = round(X[p,t].varValue or 0, 2); iv = round(I[p,t].varValue or 0, 2)
            sv = round(S[p,t].varValue or 0, 2)
            ini = INV_INICIAL[p] if idx == 0 else round(I[p,MESES[idx-1]].varValue or 0, 2)
            filas.append({"Mes":t,"Mes_ES":MESES_ES[idx],"Mes_F":MESES_F[idx],
                          "Demanda":int(DEM_HISTORICA[p][idx]*factor_demanda),
                          "Produccion":xv,"Inv_Ini":ini,"Inv_Fin":iv,"Backlog":sv})
        resultados[p] = pd.DataFrame(filas)
    return resultados

@st.cache_data(show_spinner=False)
def run_simulacion_cached(plan_items, cap_items, falla, factor_t, semilla=42):
    plan_unidades = dict(plan_items); cap_recursos = dict(cap_items)
    random.seed(semilla); np.random.seed(semilla)
    lotes_data, uso_rec, sensores = [], [], []
    def sensor_horno(env, recursos):
        while True:
            ocp = recursos["horno"].count
            temp = round(np.random.normal(160+ocp*20, 5), 2)
            sensores.append({"tiempo":round(env.now,1),"temperatura":temp,
                             "horno_ocup":ocp,"horno_cola":len(recursos["horno"].queue)})
            yield env.timeout(10)
    def reg_uso(env, recursos, prod=""):
        ts = round(env.now, 3)
        for nm, r in recursos.items():
            uso_rec.append({"tiempo":ts,"recurso":nm,"ocupados":r.count,
                            "cola":len(r.queue),"capacidad":r.capacity,"producto":prod})
    def proceso_lote(env, lid, prod, tam, recursos):
        t0 = env.now; esperas = {}
        for etapa, rec_nm, tmin, tmax in RUTAS[prod]:
            escala = math.sqrt(tam/TAMANO_LOTE_BASE[prod])
            tp = random.uniform(tmin, tmax)*escala*factor_t
            if falla and rec_nm == "horno": tp += random.uniform(10, 30)
            reg_uso(env, recursos, prod); t_entrada = env.now
            with recursos[rec_nm].request() as req:
                yield req; esperas[etapa] = round(env.now-t_entrada, 3)
                reg_uso(env, recursos, prod); yield env.timeout(tp)
            reg_uso(env, recursos, prod)
        lotes_data.append({"lote_id":lid,"producto":prod,"tamano":tam,
                           "t_creacion":round(t0,3),"t_fin":round(env.now,3),
                           "tiempo_sistema":round(env.now-t0,3),
                           "total_espera":round(sum(esperas.values()),3)})
    env = simpy.Environment()
    recursos = {nm: simpy.Resource(env, capacity=cap) for nm, cap in cap_recursos.items()}
    env.process(sensor_horno(env, recursos))
    dur_mes = 44*4*60; lotes = []; ctr = [0]
    for prod, unid in plan_unidades.items():
        if unid <= 0: continue
        tam = TAMANO_LOTE_BASE[prod]; n = math.ceil(unid/tam)
        tasa = dur_mes/max(n, 1); ta = random.expovariate(1/max(tasa, 1)); rem = unid
        for _ in range(n):
            lotes.append((round(ta, 2), prod, min(tam, int(rem)))); rem -= tam
            ta += random.expovariate(1/max(tasa, 1))
    lotes.sort(key=lambda x: x[0])
    def lanzador():
        for ta, prod, tam in lotes:
            yield env.timeout(max(ta-env.now, 0))
            lid = f"{prod[:3].upper()}_{ctr[0]:04d}"; ctr[0] += 1
            env.process(proceso_lote(env, lid, prod, tam, recursos))
    env.process(lanzador()); env.run(until=dur_mes*1.8)
    return (pd.DataFrame(lotes_data) if lotes_data else pd.DataFrame(),
            pd.DataFrame(uso_rec) if uso_rec else pd.DataFrame(),
            pd.DataFrame(sensores) if sensores else pd.DataFrame())

def calc_utilizacion(df_uso):
    if df_uso.empty: return pd.DataFrame()
    filas = []
    for rec, grp in df_uso.groupby("recurso"):
        grp = grp.sort_values("tiempo").reset_index(drop=True)
        cap = grp["capacidad"].iloc[0]; t = grp["tiempo"].values; ocp = grp["ocupados"].values
        if len(t) > 1 and (t[-1]-t[0]) > 0:
            fn = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
            util = round(fn(ocp, t)/(cap*(t[-1]-t[0]))*100, 2)
        else: util = 0.0
        filas.append({"Recurso":rec,"Utilizacion_%":util,
                      "Cola Prom":round(grp["cola"].mean(),3),
                      "Cola Max":int(grp["cola"].max()),"Capacidad":int(cap),
                      "Cuello Botella":util >= 80 or grp["cola"].mean() > 0.5})
    return pd.DataFrame(filas).sort_values("Utilizacion_%",ascending=False).reset_index(drop=True)

def calc_kpis(df_lotes, plan):
    if df_lotes.empty: return pd.DataFrame()
    dur = (df_lotes["t_fin"].max()-df_lotes["t_creacion"].min())/60; filas = []
    for p in PRODUCTOS:
        sub = df_lotes[df_lotes["producto"]==p]
        if sub.empty: continue
        und = sub["tamano"].sum(); plan_und = plan.get(p, 0)
        tp = round(und/max(dur, 0.01), 3)
        lt = round(sub["tiempo_sistema"].mean(), 3)
        dem_avg = sum(DEM_HISTORICA[p])/12
        takt = round((44*4*60)/max(dem_avg/TAMANO_LOTE_BASE[p], 1), 2)
        filas.append({"Producto":PROD_LABELS[p],"Und Producidas":und,"Plan":plan_und,
                      "Throughput (und/h)":tp,
                      "Lead Time (min/lote)":lt,
                      "WIP Prom":round(tp*(lt/60),2),"Takt (min/lote)":takt,
                      "Cumplimiento %":round(min(und/max(plan_und,1)*100,100),2)})
    return pd.DataFrame(filas)

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG STREAMLIT
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Gemelo Digital · Dora del Hoyo", page_icon="🥐",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;500;600;700&family=Inter:wght@300;400;500;600&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;background:#F7F9FC;}
.hero{background:linear-gradient(135deg,#E8BAFF 0%,#BAE1FF 40%,#BAFFC9 70%,#FFB3BA 100%);
  padding:1.8rem 2.2rem 1.4rem;border-radius:24px;margin-bottom:1.2rem;
  box-shadow:0 8px 32px rgba(184,161,255,0.15);position:relative;overflow:hidden;}
.hero::before{content:"🥐";font-size:7rem;position:absolute;right:1.5rem;top:-1rem;
  opacity:0.12;transform:rotate(-12deg);}
.hero h1{font-family:'Quicksand',sans-serif;color:#2C3E50;font-size:2rem;
  margin:0;font-weight:700;letter-spacing:-0.3px;}
.hero p{color:#5D6D7E;margin:0.3rem 0 0;font-size:0.88rem;font-weight:400;}
.hero .badge{display:inline-block;background:rgba(255,255,255,0.65);color:#2C3E50;
  padding:0.15rem 0.65rem;border-radius:20px;font-size:0.72rem;margin-top:0.5rem;
  margin-right:0.25rem;border:1px solid rgba(255,255,255,0.8);font-weight:500;
  backdrop-filter:blur(4px);}
.kpi-card{background:white;border-radius:16px;padding:1rem 1.1rem;
  box-shadow:0 2px 12px rgba(0,0,0,0.04);border:1px solid #E8ECF1;
  text-align:center;transition:all 0.25s;}
.kpi-card:hover{transform:translateY(-2px);box-shadow:0 6px 20px rgba(0,0,0,0.08);}
.kpi-card .icon{font-size:1.5rem;margin-bottom:0.15rem;}
.kpi-card .val{font-family:'Quicksand',sans-serif;font-size:1.6rem;color:#2C3E50;
  line-height:1;margin:0.05rem 0;font-weight:700;}
.kpi-card .lbl{font-size:0.65rem;color:#7F8C8D;text-transform:uppercase;
  letter-spacing:0.8px;font-weight:600;}
.kpi-card .sub{font-size:0.72rem;color:#95A5A6;margin-top:0.15rem;}
.sec-title{font-family:'Quicksand',sans-serif;font-size:1.15rem;color:#2C3E50;
  border-left:4px solid #BAE1FF;padding-left:0.7rem;margin:1.2rem 0 0.6rem;font-weight:600;}
.info-box{background:white;border:1px solid #E8ECF1;border-radius:14px;
  padding:0.75rem 1rem;font-size:0.84rem;color:#5D6D7E;margin:0.4rem 0 0.7rem;
  box-shadow:0 1px 4px rgba(0,0,0,0.03);}
.param-panel{background:white;border:1px solid #E8ECF1;border-radius:16px;
  padding:1.2rem;margin:0.5rem 0 1rem;box-shadow:0 2px 8px rgba(0,0,0,0.03);}
.param-panel h4{font-family:'Quicksand',sans-serif;color:#2C3E50;margin:0 0 0.8rem;
  font-size:0.95rem;font-weight:600;}
.param-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:0.6rem;}
.param-item{background:#F7F9FC;border-radius:10px;padding:0.5rem 0.7rem;
  border:1px solid #E8ECF1;}
.param-item .plabel{font-size:0.68rem;color:#7F8C8D;text-transform:uppercase;
  letter-spacing:0.5px;font-weight:500;}
.param-item .pval{font-family:'Quicksand',sans-serif;font-size:1.1rem;color:#2C3E50;
  font-weight:600;margin-top:0.1rem;}
.pill-ok{background:#D5F5E3;color:#1E8449;padding:0.25rem 0.8rem;
  border-radius:20px;font-size:0.8rem;font-weight:600;display:inline-block;}
.pill-warn{background:#FADBD8;color:#C0392B;padding:0.25rem 0.8rem;
  border-radius:20px;font-size:0.8rem;font-weight:600;display:inline-block;}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#2C3E50 0%,#34495E 100%) !important;}
[data-testid="stSidebar"] label,[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span{color:#D5DBDB !important;}
[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3{color:#BAE1FF !important;
  font-family:'Quicksand',sans-serif !important;}
[data-testid="stSidebar"] hr{border-color:rgba(186,225,255,0.2) !important;}
[data-testid="stSidebar"] .stNumberInput input,
[data-testid="stSidebar"] .stSlider>div>div{background:rgba(186,225,255,0.2) !important;}
.stTabs [data-baseweb="tab"]{font-family:'Inter',sans-serif;font-weight:500;color:#95A5A6;}
.stTabs [aria-selected="true"]{color:#2C3E50 !important;background:white !important;
  border-radius:10px 10px 0 0 !important;box-shadow:0 -2px 8px rgba(0,0,0,0.06) !important;}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🥐 Dora del Hoyo")
    st.markdown("<span style='color:#BAE1FF;font-size:0.85rem'>Gemelo Digital v3.0</span>",
                unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("### 📅 Simulación")
    mes_idx = st.selectbox("Mes", range(12), index=1,
                           format_func=lambda i: MESES_F[i], label_visibility="collapsed")
    factor_demanda   = st.slider("Factor de demanda", 0.5, 2.0, 1.0, 0.05)
    meses_pronostico = st.slider("Meses a proyectar", 1, 6, 3)
    st.markdown("### 🏭 Planta")
    cap_horno   = st.slider("Capacidad horno", 1, 6, 3)
    falla_horno = st.checkbox("⚠️ Fallas en horno")
    doble_turno = st.checkbox("🕐 Doble turno")
    semilla     = st.number_input("Semilla", value=42, step=1)
    st.markdown("### 💰 Costos COP")
    with st.expander("Parámetros LP"):
        ct   = st.number_input("Ct (prod/und)",  value=4_310,   step=100)
        crt  = st.number_input("CRt (hora reg.)", value=11_364,  step=100)
        cot  = st.number_input("COt (hora ext.)", value=14_205,  step=100)
        ht   = st.number_input("Ht (inv.)",       value=100_000, step=1000)
        pit  = st.number_input("PIt (backlog)",   value=100_000, step=1000)
        cwp  = st.number_input("CW+ (contratar)", value=14_204,  step=100)
        cwm  = st.number_input("CW− (despedir)",  value=15_061,  step=100)
        trab = st.number_input("Trabajadores",     value=10,      step=1)
    st.markdown("---")
    st.markdown("<div style='font-size:0.7rem;color:#7F8C8D;'>📍 Panadería Dora del Hoyo<br>"
                "🔢 SimPy · PuLP · Plotly · Streamlit</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# HERO
# ══════════════════════════════════════════════════════════════════════════════
badges = (f"<span class='badge'>📅 {MESES_F[mes_idx]}</span>"
          f"<span class='badge'>📈 ×{factor_demanda}</span>"
          f"<span class='badge'>🔥 {cap_horno} est.</span>")
if falla_horno: badges += "<span class='badge'>⚠️ Falla</span>"
if doble_turno: badges += "<span class='badge'>🕐 2 turnos</span>"

st.markdown(f"""
<div class="hero">
  <h1>Gemelo Digital — Panadería Dora del Hoyo</h1>
  <p>Planeación agregada · Desagregación · Simulación discreta · What-if</p>
  {badges}
</div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# CÁLCULOS
# ══════════════════════════════════════════════════════════════════════════════
params_custom = {**PARAMS_DEFAULT, "Ct":ct,"CRt":crt,"COt":cot,"Ht":ht,"PIt":pit,
                 "CW_mas":cwp,"CW_menos":cwm,"LR_inicial":44*4*int(trab)}

with st.spinner("⚙️ Optimizando plan agregado…"):
    df_agr, costo = run_agregacion(factor_demanda, tuple(sorted(params_custom.items())))

prod_hh = dict(zip(df_agr["Mes"], df_agr["Produccion_HH"]))

with st.spinner("🔢 Desagregando por producto…"):
    desag = run_desagregacion(tuple(prod_hh.items()), factor_demanda)

mes_nm   = MESES[mes_idx]
plan_mes = {p: int(desag[p].loc[desag[p]["Mes"]==mes_nm, "Produccion"].values[0]) for p in PRODUCTOS}
cap_rec  = {**CAPACIDAD_BASE, "horno": int(cap_horno)}
factor_t = 0.80 if doble_turno else 1.0

with st.spinner("🏭 Simulando planta…"):
    df_lotes, df_uso, df_sensores = run_simulacion_cached(
        tuple(plan_mes.items()), tuple(cap_rec.items()), falla_horno, factor_t, int(semilla))

df_kpis = calc_kpis(df_lotes, plan_mes)
df_util = calc_utilizacion(df_uso)

# ══════════════════════════════════════════════════════════════════════════════
# KPIs SUPERIORES
# ══════════════════════════════════════════════════════════════════════════════
cum_avg  = df_kpis["Cumplimiento %"].mean() if not df_kpis.empty else 0
util_max = df_util["Utilizacion_%"].max()   if not df_util.empty else 0
lotes_n  = len(df_lotes) if not df_lotes.empty else 0
temp_avg = df_sensores["temperatura"].mean() if not df_sensores.empty else 0
excesos  = int((df_sensores["temperatura"]>200).sum()) if not df_sensores.empty else 0
backlog_hh = df_agr["Backlog_HH"].sum()

def kpi_card(col, icon, val, lbl, sub="", color="#BAE1FF"):
    col.markdown(f"""
    <div class="kpi-card" style="border-top:3px solid {color}">
      <div class="icon">{icon}</div>
      <div class="val">{val}</div>
      <div class="lbl">{lbl}</div>
      {"<div class='sub'>"+sub+"</div>" if sub else ""}
    </div>""", unsafe_allow_html=True)

c1,c2,c3,c4,c5,c6 = st.columns(6)
kpi_card(c1,"💰",f"${costo/1e6:.1f}M","Costo Óptimo","COP/año","#E8BAFF")
kpi_card(c2,"📦",f"{lotes_n:,}","Lotes",MESES_F[mes_idx],"#BAE1FF")
kpi_card(c3,"✅",f"{cum_avg:.1f}%","Cumplimiento","Prod vs Plan","#BAFFC9")
kpi_card(c4,"⚙️",f"{util_max:.0f}%","Util. Máx","Recurso","#FFB3BA" if util_max>=80 else "#BAFFC9")
kpi_card(c5,"🌡️",f"{temp_avg:.0f}°C","Temp. Horno",
         f"⚠ {excesos} excesos" if excesos else "✓ Normal",
         "#FFB3BA" if excesos else "#BAFFC9")
kpi_card(c6,"📉",f"{backlog_hh:,.0f}","Backlog","H-H total",
         "#FFB3BA" if backlog_hh > 0 else "#BAFFC9")

PCFG = dict(template="plotly_white", font=dict(family="Inter"),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#FAFBFD",
            margin=dict(l=50,r=30,t=50,b=40))

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tabs = st.tabs(["📊 Demanda","📋 Agregado","📦 Desagregación","🏭 Simulación","🌡️ Sensores","🔬 Escenarios"])

# ────────────────────────────────────────────────────────────────────────────
# TAB 1 — DEMANDA & PRONÓSTICO
# ────────────────────────────────────────────────────────────────────────────
with tabs[0]:
    # Panel de parámetros generales (estilo referencia)
    st.markdown('<div class="sec-title">📈 Pronóstico de Demanda e Históricos</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Suavizado exponencial simple (α = 0.3) con tendencia. '
                'La zona sombreada marca el periodo de proyección.</div>', unsafe_allow_html=True)

    col_pp, col_pd = st.columns([1, 1])
    with col_pp:
        st.markdown("""<div class="param-panel">
        <h4>📋 Parámetros Generales</h4>
        <div class="param-grid">
          <div class="param-item"><div class="plabel">Meses a proyectar</div>
          <div class="pval">""" + str(meses_pronostico) + """</div></div>
          <div class="param-item"><div class="plabel">Factor de demanda</div>
          <div class="pval">×""" + str(factor_demanda) + """</div></div>
          <div class="param-item"><div class="plabel">Productos activos</div>
          <div class="pval">5</div></div>
          <div class="param-item"><div class="plabel">Mes simulado</div>
          <div class="pval">""" + MESES_F[mes_idx] + """</div></div>
        </div></div>""", unsafe_allow_html=True)
    with col_pd:
        total_dem = sum(sum(DEM_HISTORICA[p])*factor_demanda for p in PRODUCTOS)
        st.markdown(f"""<div class="param-panel">
        <h4>📊 Resumen de Demanda</h4>
        <div class="param-grid">
          <div class="param-item"><div class="plabel">Demanda anual total</div>
          <div class="pval">{total_dem:,.0f} und</div></div>
          <div class="param-item"><div class="plabel">Promedio mensual</div>
          <div class="pval">{total_dem/12:,.0f} und</div></div>
          <div class="param-item"><div class="plabel">Mes pico (Feb)</div>
          <div class="pval">{int(sum(DEM_HISTORICA[p][1]*factor_demanda for p in PRODUCTOS)):,}</div></div>
          <div class="param-item"><div class="plabel">Mes valle (Jun)</div>
          <div class="pval">{int(sum(DEM_HISTORICA[p][5]*factor_demanda for p in PRODUCTOS)):,}</div></div>
        </div></div>""", unsafe_allow_html=True)

    # Gráfico principal: áreas apiladas con pronóstico
    fig_pro = go.Figure()
    total_hist = [sum(DEM_HISTORICA[p][i]*factor_demanda for p in PRODUCTOS) for i in range(12)]

    # Áreas apiladas por producto (histórico)
    for p in PRODUCTOS:
        serie = [v*factor_demanda for v in DEM_HISTORICA[p]]
        fig_pro.add_trace(go.Scatter(
            x=MESES_ES, y=serie, name=PROD_LABELS[p],
            mode="lines", stackgroup="one",
            line=dict(color=PROD_COLORS_MID[p], width=1.5),
            fillcolor=PROD_COLORS[p], opacity=0.85,
            hovertemplate=f"<b>{PROD_LABELS[p]}</b><br>%{x}: %{y:,.0f} und<extra></extra>",
        ))

    # Total histórico como línea
    fig_pro.add_trace(go.Scatter(
        x=MESES_ES, y=total_hist, name="Total histórico",
        mode="lines+markers", line=dict(color="#2C3E50", width=2.5),
        marker=dict(size=6, color="#2C3E50"),
        hovertemplate="Total: %{y:,.0f}<extra></extra>",
    ))

    # Pronóstico del total
    suav_total, fut_total = pronostico_simple(total_hist, meses_pronostico)
    meses_fut = [f"P+{j+1}" for j in range(meses_pronostico)]
    x_fut = [MESES_ES[-1]] + meses_fut
    y_fut = [suav_total[-1]] + fut_total

    fig_pro.add_trace(go.Scatter(
        x=x_fut, y=y_fut, name="Pronóstico total",
        mode="lines+markers", line=dict(color="#E05A65", width=2.5, dash="dash"),
        marker=dict(size=8, color="#FFB3BA", line=dict(color="#E05A65", width=2)),
        hovertemplate="Pronóstico: %{y:,.0f}<extra></extra>",
    ))

    # Banda de confianza del pronóstico
    y_upper = [v*1.12 for v in y_fut]
    y_lower = [v*0.88 for v in y_fut]
    fig_pro.add_trace(go.Scatter(
        x=x_fut, y=y_upper, showlegend=False,
        mode="lines", line=dict(width=0), hoverinfo="skip",
    ))
    fig_pro.add_trace(go.Scatter(
        x=x_fut, y=y_lower, name="Intervalo 88%",
        mode="lines", fill="tonexty",
        fillcolor=hex_rgba("#FFB3BA", 0.2),
        line=dict(width=0, color="rgba(0,0,0,0)"), hoverinfo="skip",
    ))

    # Línea divisoria
    fig_pro.add_vline(x=11, line_dash="dot", line_color="#95A5A6", line_width=1.5,
                      annotation_text="  ▶ Proyección", annotation_font_color="#7F8C8D",
                      annotation_font_size=11, annotation_position="top right")

    fig_pro.update_layout(
        **PCFG, height=420,
        title=dict(text="Demanda Histórica y Pronóstico — Dora del Hoyo",
                   font=dict(family="Quicksand", size=15, color="#2C3E50")),
        xaxis_title="Mes", yaxis_title="Unidades demandadas",
        legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center",
                    font=dict(size=10)),
        xaxis=dict(showgrid=True, gridcolor="#E8ECF1", gridwidth=0.5),
        yaxis=dict(showgrid=True, gridcolor="#E8ECF1", gridwidth=0.5),
    )
    st.plotly_chart(fig_pro, use_container_width=True)

    # Fila inferior: heatmap + pie + H-H
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown('<div class="sec-title">🔥 Estacionalidad</div>', unsafe_allow_html=True)
        z = [[DEM_HISTORICA[p][i]*factor_demanda for i in range(12)] for p in PRODUCTOS]
        fig_heat = go.Figure(go.Heatmap(
            z=z, x=MESES_ES, y=[PROD_LABELS[p] for p in PRODUCTOS],
            colorscale=[[0,"#FAFBFD"],[0.3,"#BAE1FF"],[0.6,"#E8BAFF"],[1,"#FFB3BA"]],
            text=[[f"{int(v)}" for v in row] for row in z],
            texttemplate="%{text}", textfont=dict(size=9, color="#2C3E50"),
            hovertemplate="%{y}<br>%{x}: %{z:,.0f}<extra></extra>",
        ))
        fig_heat.update_layout(**PCFG, height=230, margin=dict(t=15,b=5))
        st.plotly_chart(fig_heat, use_container_width=True)

    with col_b:
        st.markdown('<div class="sec-title">🌸 Mix de Ventas</div>', unsafe_allow_html=True)
        totales = {p: sum(DEM_HISTORICA[p]) for p in PRODUCTOS}
        fig_pie = go.Figure(go.Sunburst(
            labels=[PROD_LABELS[p] for p in PRODUCTOS],
            parents=[""]*5,
            values=list(totales.values()),
            marker=dict(colors=list(PROD_COLORS.values()),
                        line=dict(color="white", width=3)),
            textfont=dict(size=10, color="#2C3E50"),
            hovertemplate="<b>%{label}</b><br>%{value:,} und/año<extra></extra>",
        ))
        fig_pie.update_layout(**PCFG, height=230, margin=dict(t=5,b=5))
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_c:
        st.markdown('<div class="sec-title">⏱️ Demanda H-H</div>', unsafe_allow_html=True)
        dem_h_vals = demanda_horas_hombre(factor_demanda)
        colores_hh = [PAL["blue"] if i != mes_idx else PAL["lavender"] for i in range(12)]
        fig_hh = go.Figure()
        fig_hh.add_trace(go.Bar(x=MESES_ES, y=list(dem_h_vals.values()),
                                marker_color=colores_hh,
                                marker_line_color="white", marker_line_width=1.5,
                                hovertemplate="%{x}: %{y:,.0f} H-H<extra></extra>",
                                showlegend=False))
        fig_hh.update_layout(**PCFG, height=230, xaxis_title="Mes", yaxis_title="H-H",
                             xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#E8ECF1",gridwidth=0.5),
                             margin=dict(t=15,b=5))
        st.plotly_chart(fig_hh, use_container_width=True)

    # Distribución por producto (box plot)
    st.markdown('<div class="sec-title">📦 Distribución mensual por producto</div>', unsafe_allow_html=True)
    fig_box = go.Figure()
    for p in PRODUCTOS:
        fig_box.add_trace(go.Box(
            y=[v*factor_demanda for v in DEM_HISTORICA[p]],
            name=PROD_LABELS[p], marker_color=PROD_COLORS_MID[p],
            line_color=PROD_COLORS_DARK[p], fillcolor=PROD_COLORS[p],
            boxpoints="outliers", opacity=0.8,
        ))
    fig_box.update_layout(**PCFG, height=280, yaxis_title="Unidades",
                          showlegend=False,
                          xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#E8ECF1",gridwidth=0.5))
    st.plotly_chart(fig_box, use_container_width=True)

# ────────────────────────────────────────────────────────────────────────────
# TAB 2 — PLAN AGREGADO
# ────────────────────────────────────────────────────────────────────────────
with tabs[1]:
    st.markdown('<div class="sec-title">📋 Planeación Agregada — Optimización LP</div>', unsafe_allow_html=True)

    # Panel de parámetros económicos y laborales (estilo referencia)
    hh_reg = int(44*4*trab)
    st.markdown(f"""<div class="param-panel">
    <h4>💰 Costos Operativos & Fuerza Laboral</h4>
    <div class="param-grid">
      <div class="param-item"><div class="plabel">Ct — Producción/und</div>
      <div class="pval">${ct:,.0f}</div></div>
      <div class="param-item"><div class="plabel">CRt — Hora regular</div>
      <div class="pval">${crt:,.0f}</div></div>
      <div class="param-item"><div class="plabel">COt — Hora extra</div>
      <div class="pval">${cot:,.0f}</div></div>
      <div class="param-item"><div class="plabel">Ht — Inventario</div>
      <div class="pval">${ht:,.0f}</div></div>
      <div class="param-item"><div class="plabel">PIt — Backlog</div>
      <div class="pval">${pit:,.0f}</div></div>
      <div class="param-item"><div class="plabel">Trabajadores</div>
      <div class="pval">{int(trab)} ({hh_reg:,} H-H/mes)</div></div>
      <div class="param-item"><div class="plabel">CW+ Contratar</div>
      <div class="pval">${cwp:,.0f}</div></div>
      <div class="param-item"><div class="plabel">CW− Despedir</div>
      <div class="pval">${cwm:,.0f}</div></div>
    </div></div>""", unsafe_allow_html=True)

    # KPIs agregados
    ka1,ka2,ka3,ka4 = st.columns(4)
    ka1.metric("💰 Costo Total", f"${costo:,.0f} COP")
    ka2.metric("⏰ Horas Extra", f"{df_agr['Horas_Extras'].sum():,.0f} H-H")
    ka3.metric("📉 Backlog", f"{df_agr['Backlog_HH'].sum():,.0f} H-H")
    net = df_agr["Contratacion"].sum()-df_agr["Despidos"].sum()
    ka4.metric("👥 Contratación neta", f"{net:+.0f} pers.")

    # Gráfico principal: waterfall de producción
    st.markdown('<div class="sec-title">📊 Plan Agregado — Producción vs Demanda (H-H)</div>', unsafe_allow_html=True)
    fig_agr = go.Figure()
    fig_agr.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Inv_Ini_HH"],
                             name="Inv. Inicial", marker_color=PAL["blue"],
                             marker_line_color="white", marker_line_width=1))
    fig_agr.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Produccion_HH"],
                             name="Producción", marker_color=PAL["lavender"],
                             marker_line_color="white", marker_line_width=1))
    fig_agr.add_trace(go.Scatter(x=df_agr["Mes_ES"], y=df_agr["Demanda_HH"],
                                 mode="lines+markers", name="Demanda",
                                 line=dict(color="#2C3E50", dash="dash", width=2.5),
                                 marker=dict(size=7, color="#2C3E50")))
    fig_agr.add_trace(go.Scatter(x=df_agr["Mes_ES"], y=df_agr["Horas_Regulares"],
                                 mode="lines", name="Cap. Regular",
                                 line=dict(color=PAL["coral"], dash="dot", width=2)))
    fig_agr.update_layout(**PCFG, barmode="stack", height=380,
                          title=dict(text=f"Costo Óptimo: COP ${costo:,.0f}",
                                     font=dict(family="Quicksand",size=13,color="#2C3E50")),
                          xaxis_title="Mes", yaxis_title="Horas-Hombre",
                          legend=dict(orientation="h",y=-0.2,x=0.5,xanchor="center",font=dict(size=10)),
                          xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#E8ECF1",gridwidth=0.5))
    st.plotly_chart(fig_agr, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="sec-title">👷 Fuerza laboral</div>', unsafe_allow_html=True)
        fig_fl = go.Figure()
        fig_fl.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Contratacion"],
                                name="Contrataciones", marker_color=PAL["green"],
                                marker_line_color="white", marker_line_width=1))
        fig_fl.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Despidos"],
                                name="Despidos", marker_color=PAL["coral"],
                                marker_line_color="white", marker_line_width=1))
        fig_fl.update_layout(**PCFG, barmode="group", height=280,
                             legend=dict(orientation="h",y=-0.3,x=0.5,xanchor="center",font=dict(size=10)),
                             xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#E8ECF1",gridwidth=0.5))
        st.plotly_chart(fig_fl, use_container_width=True)

    with col2:
        st.markdown('<div class="sec-title">⚡ Extras & Backlog</div>', unsafe_allow_html=True)
        fig_ex = go.Figure()
        fig_ex.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Horas_Extras"],
                                name="Horas Extra", marker_color=PAL["yellow"],
                                marker_line_color="white", marker_line_width=1))
        fig_ex.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Backlog_HH"],
                                name="Backlog", marker_color=PAL["pink"],
                                marker_line_color="white", marker_line_width=1))
        fig_ex.update_layout(**PCFG, barmode="group", height=280,
                             legend=dict(orientation="h",y=-0.3,x=0.5,xanchor="center",font=dict(size=10)),
                             xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#E8ECF1",gridwidth=0.5))
        st.plotly_chart(fig_ex, use_container_width=True)

    # Waterfall de costos (NUEVO WOW)
    st.markdown('<div class="sec-title">💎 Desglose de costos — Waterfall</div>', unsafe_allow_html=True)
    cost_prod  = sum(df_agr["Produccion_HH"]*ct)
    cost_inv   = sum(df_agr["Inv_Fin_HH"]*ht)
    cost_extra = sum(df_agr["Horas_Extras"]*cot)
    cost_reg   = sum(df_agr["Horas_Regulares"]*crt)
    cost_back  = sum(df_agr["Backlog_HH"]*pit)
    cost_wf    = sum(df_agr["Contratacion"]*cwp) + sum(df_agr["Despidos"]*cwm)

    labels_wf = ["Prod.","Regular","Extra","Inventario","Backlog","Personal","Total"]
    vals_wf   = [cost_prod, cost_reg, cost_extra, cost_inv, cost_back, cost_wf, costo]
    colors_wf = [PAL["lavender"],PAL["blue"],PAL["yellow"],PAL["green"],PAL["pink"],PAL["peach"],"#2C3E50"]
    measures  = ["relative"]*6 + ["total"]

    fig_wf = go.Figure(go.Waterfall(
        x=labels_wf, y=vals_wf, measure=measures,
        text=[f"${v/1e6:.1f}M" for v in vals_wf], textposition="outside",
        textfont=dict(size=10, color="#2C3E50"),
        connector=dict(line=dict(color="#95A5A6", width=1.5)),
        increasing=dict(marker=dict(color=PAL["blue"])),
        decreasing=dict(marker=dict(color=PAL["coral"])),
        totals=dict(marker=dict(color="#2C3E50")),
    ))
    fig_wf.update_layout(**PCFG, height=320, showlegend=False,
                         yaxis_title="COP", yaxis=dict(gridcolor="#E8ECF1",gridwidth=0.5),
                         xaxis=dict(showgrid=False))
    st.plotly_chart(fig_wf, use_container_width=True)

    with st.expander("📄 Tabla completa"):
        df_show = df_agr.drop(columns=["Mes","Mes_ES"]).rename(columns={"Mes_F":"Mes"})
        st.dataframe(df_show.style.format({c:"{:,.1f}" for c in df_show.columns if c!="Mes"})
                     .background_gradient(subset=["Produccion_HH","Horas_Extras"],cmap="BuGn"),
                     use_container_width=True)

# ────────────────────────────────────────────────────────────────────────────
# TAB 3 — DESAGREGACIÓN
# ────────────────────────────────────────────────────────────────────────────
with tabs[2]:
    st.markdown('<div class="sec-title">📦 Desagregación por Producto</div>', unsafe_allow_html=True)

    # Panel de parámetros de desagregación (estilo referencia)
    st.markdown(f"""<div class="param-panel">
    <h4>⚙️ Parámetros de Desagregación</h4>
    <p style='font-size:0.82rem;color:#7F8C8D;margin:0 0 0.6rem'>
    Ajuste de costos para balancear producción e inventario. Reducir costos de inventario
    favorece producción just-in-time; reducir costos de producción permite lotes más grandes.</p>
    <div class="param-grid">
      <div class="param-item" style="border-left:3px solid #E8BAFF">
      <div class="plabel">Ct — Costo Producción</div>
      <div class="pval">${ct:,.0f} COP</div></div>
      <div class="param-item" style="border-left:3px solid #BAE1FF">
      <div class="plabel">Ht — Costo Inventario</div>
      <div class="pval">${ht:,.0f} COP</div></div>
      <div class="param-item" style="border-left:3px solid #BAFFC9">
      <div class="plabel">Relación Ht/Ct</div>
      <div class="pval">{ht/max(ct,1):.1f}x</div></div>
      <div class="param-item" style="border-left:3px solid #FFB3BA">
      <div class="plabel">Mes simulado</div>
      <div class="pval">{MESES_F[mes_idx]}</div></div>
    </div></div>""", unsafe_allow_html=True)

    mes_resaltar = st.selectbox("Mes a resaltar ★", range(12), index=mes_idx,
                                format_func=lambda i: MESES_F[i], key="mes_desag")

    fig_des = make_subplots(rows=3, cols=2,
                            subplot_titles=[f"{PROD_EMOJI[p]} {PROD_LABELS[p]}" for p in PRODUCTOS],
                            vertical_spacing=0.13, horizontal_spacing=0.08)
    for idx, p in enumerate(PRODUCTOS):
        r, c = idx//2+1, idx%2+1
        df_p = desag[p]
        fig_des.add_trace(go.Bar(x=df_p["Mes_ES"], y=df_p["Produccion"],
                                 marker_color=PROD_COLORS[p], opacity=0.9, showlegend=False,
                                 marker_line_color="white", marker_line_width=1), row=r, col=c)
        fig_des.add_trace(go.Scatter(x=df_p["Mes_ES"], y=df_p["Demanda"],
                                     mode="lines+markers",
                                     line=dict(color=PROD_COLORS_DARK[p], dash="dash", width=1.5),
                                     marker=dict(size=5), showlegend=False), row=r, col=c)
        mr = df_p[df_p["Mes"]==MESES[mes_resaltar]]
        if not mr.empty:
            fig_des.add_trace(go.Scatter(x=[MESES_ES[mes_resaltar]],
                                         y=[mr["Produccion"].values[0]],
                                         mode="markers",
                                         marker=dict(size=14, color="#2C3E50", symbol="star"),
                                         showlegend=False), row=r, col=c)
    fig_des.update_layout(**PCFG, height=700, barmode="group",
                          title=dict(text="Producción vs Demanda (unidades/mes)",
                                     font=dict(family="Quicksand",size=13,color="#2C3E50")),
                          margin=dict(t=55))
    for i in range(1, 4):
        for j in range(1, 3):
            fig_des.update_xaxes(showgrid=False, row=i, col=j)
            fig_des.update_yaxes(gridcolor="#E8ECF1", gridwidth=0.5, row=i, col=j)
    st.plotly_chart(fig_des, use_container_width=True)

    # Cobertura
    st.markdown('<div class="sec-title">🎯 Cobertura de demanda anual</div>', unsafe_allow_html=True)
    prods_c, cob_vals, und_prod, und_dem = [], [], [], []
    for p in PRODUCTOS:
        df_p = desag[p]
        tot_p = df_p["Produccion"].sum(); tot_d = df_p["Demanda"].sum()
        cob = round(min(tot_p/max(tot_d,1)*100, 100), 1)
        prods_c.append(PROD_LABELS[p]); cob_vals.append(cob)
        und_prod.append(int(tot_p)); und_dem.append(int(tot_d))

    col_c1, col_c2 = st.columns([2, 1])
    with col_c1:
        fig_cob = go.Figure()
        fig_cob.add_trace(go.Bar(y=prods_c, x=cob_vals, orientation="h",
                                  marker=dict(color=list(PROD_COLORS.values()),
                                              line=dict(color="white", width=2)),
                                  text=[f"{v:.1f}%" for v in cob_vals], textposition="inside",
                                  textfont=dict(color="#2C3E50", size=12)))
        fig_cob.add_vline(x=100, line_dash="dash", line_color="#2C3E50",
                          annotation_text="Meta 100%", annotation_font_color="#7F8C8D")
        fig_cob.update_layout(**PCFG, height=240, xaxis_title="Cobertura (%)",
                              xaxis=dict(range=[0, 115]), yaxis=dict(showgrid=False),
                              showlegend=False, margin=dict(t=15,b=15))
        st.plotly_chart(fig_cob, use_container_width=True)
    with col_c2:
        df_cob = pd.DataFrame({"Producto":prods_c,"Producido":und_prod,"Demanda":und_dem,"Cob %":cob_vals})
        st.dataframe(df_cob.style.format({"Producido":"{:,.0f}","Demanda":"{:,.0f}","Cob %":"{:.1f}%"})
                     .background_gradient(subset=["Cob %"],cmap="BuGn"),
                     use_container_width=True, height=240)

    # Inventario proyectado (área)
    st.markdown('<div class="sec-title">📦 Inventario final proyectado</div>', unsafe_allow_html=True)
    fig_inv = go.Figure()
    for p in PRODUCTOS:
        fig_inv.add_trace(go.Scatter(x=desag[p]["Mes_ES"], y=desag[p]["Inv_Fin"],
                                     name=PROD_LABELS[p], mode="lines",
                                     line=dict(color=PROD_COLORS_DARK[p], width=2),
                                     fill="tozeroy", fillcolor=hex_rgba(PROD_COLORS[p], 0.18),
                                     hovertemplate=f"{PROD_LABELS[p]}: %{y:,.0f}<extra></extra>"))
    fig_inv.update_layout(**PCFG, height=260, xaxis_title="Mes", yaxis_title="Unidades",
                          legend=dict(orientation="h",y=-0.25,x=0.5,xanchor="center",font=dict(size=10)),
                          xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#E8ECF1",gridwidth=0.5))
    st.plotly_chart(fig_inv, use_container_width=True)

# ────────────────────────────────────────────────────────────────────────────
# TAB 4 — SIMULACIÓN
# ────────────────────────────────────────────────────────────────────────────
with tabs[3]:
    st.markdown(f'<div class="sec-title">🏭 Simulación de Planta — {MESES_F[mes_idx]}</div>', unsafe_allow_html=True)

    # Panel de parámetros operativos (estilo referencia)
    st.markdown(f"""<div class="param-panel">
    <h4>⚙️ Parámetros Operativos de Simulación</h4>
    <div class="param-grid">
      <div class="param-item"><div class="plabel">Horas/día</div><div class="pval">8</div></div>
      <div class="param-item"><div class="plabel">Días/mes</div><div class="pval">22</div></div>
      <div class="param-item"><div class="plabel">Turnos/día</div><div class="pval">{2 if doble_turno else 1}</div></div>
      <div class="param-item"><div class="plabel">Factor tiempo</div><div class="pval">{factor_t}</div></div>
    </div>
    <h4 style='margin-top:0.8rem'>🔧 Capacidad de Estaciones</h4>
    <div class="param-grid">
      <div class="param-item"><div class="plabel">🥣 Mezcla</div><div class="pval">{cap_rec['mezcla']}</div></div>
      <div class="param-item"><div class="plabel">🔧 Dosificado</div><div class="pval">{cap_rec['dosificado']}</div></div>
      <div class="param-item"><div class="plabel">🔥 Horno</div><div class="pval">{cap_rec['horno']}</div></div>
      <div class="param-item"><div class="plabel">❄️ Enfriamiento</div><div class="pval">{cap_rec['enfriamiento']}</div></div>
      <div class="param-item"><div class="plabel">📦 Empaque</div><div class="pval">{cap_rec['empaque']}</div></div>
      <div class="param-item"><div class="plabel">👐 Amasado</div><div class="pval">{cap_rec['amasado']}</div></div>
    </div></div>""", unsafe_allow_html=True)

    # Plan del mes
    st.markdown('<div class="sec-title">🗓️ Plan del mes</div>', unsafe_allow_html=True)
    cols_p = st.columns(5)
    for i, (p, u) in enumerate(plan_mes.items()):
        with cols_p[i]:
            hh_req = round(u*HORAS_PRODUCTO[p], 1)
            st.markdown(f"""
            <div class="kpi-card" style="border-top:3px solid {PROD_COLORS_DARK[p]}">
              <div class="icon">{PROD_EMOJI[p]}</div>
              <div class="val" style="font-size:1.4rem">{u:,}</div>
              <div class="lbl">{PROD_LABELS[p]}</div>
              <div class="sub">{hh_req} H-H</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if not df_kpis.empty:
        st.markdown('<div class="sec-title">✅ Cumplimiento por producto</div>', unsafe_allow_html=True)
        fig_cum = go.Figure()
        for i, row in df_kpis.iterrows():
            pk = [p for p in PRODUCTOS if PROD_LABELS[p]==row["Producto"]]
            pk = pk[0] if pk else PRODUCTOS[i%5]
            fig_cum.add_trace(go.Bar(
                x=[row["Cumplimiento %"]], y=[row["Producto"]], orientation="h",
                marker=dict(color=PROD_COLORS[pk], line=dict(color=PROD_COLORS_DARK[pk], width=1.5)),
                text=f"{row['Cumplimiento %']:.1f}%", textposition="inside",
                textfont=dict(color="#2C3E50", size=12), showlegend=False,
                hovertemplate=f"<b>{row['Producto']}</b><br>Prod: {row['Und Producidas']:,.0f}<extra></extra>",
            ))
        fig_cum.add_vline(x=100, line_dash="dash", line_color="#2C3E50")
        fig_cum.update_layout(**PCFG, height=230, xaxis=dict(range=[0, 115]),
                              yaxis=dict(showgrid=False), xaxis_title="%",
                              margin=dict(t=15,b=15), showlegend=False)
        st.plotly_chart(fig_cum, use_container_width=True)

        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.markdown('<div class="sec-title">⚡ Throughput (und/h)</div>', unsafe_allow_html=True)
            pks = [p for p in PRODUCTOS if PROD_LABELS[p] in df_kpis["Producto"].values]
            fig_tp = go.Figure(go.Bar(
                x=[PROD_LABELS[p] for p in pks],
                y=[df_kpis.loc[df_kpis["Producto"]==PROD_LABELS[p],"Throughput (und/h)"].values[0] for p in pks],
                marker_color=[PROD_COLORS[p] for p in pks],
                marker_line_color="white", marker_line_width=2,
                textposition="outside",
            ))
            fig_tp.update_layout(**PCFG, height=260, yaxis_title="und/h", showlegend=False,
                                 xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#E8ECF1",gridwidth=0.5),
                                 margin=dict(t=35))
            st.plotly_chart(fig_tp, use_container_width=True)
        with col_t2:
            st.markdown('<div class="sec-title">⏱️ Lead Time (min/lote)</div>', unsafe_allow_html=True)
            fig_lt = go.Figure(go.Bar(
                x=[PROD_LABELS[p] for p in pks],
                y=[df_kpis.loc[df_kpis["Producto"]==PROD_LABELS[p],"Lead Time (min/lote)"].values[0] for p in pks],
                marker_color=[PROD_COLORS_DARK[p] for p in pks],
                marker_line_color="white", marker_line_width=2,
                textposition="outside",
            ))
            fig_lt.update_layout(**PCFG, height=260, yaxis_title="min/lote", showlegend=False,
                                 xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#E8ECF1",gridwidth=0.5),
                                 margin=dict(t=35))
            st.plotly_chart(fig_lt, use_container_width=True)

    if not df_util.empty:
        st.markdown('<div class="sec-title">⚙️ Utilización & Cuellos de Botella</div>', unsafe_allow_html=True)
        cuellos = df_util[df_util["Cuello Botella"]]
        if not cuellos.empty:
            for _, row in cuellos.iterrows():
                st.markdown(f'<div class="pill-warn">⚠️ Cuello: <b>{REC_LABELS.get(row["Recurso"],row["Recurso"])}</b>'
                            f' — {row["Utilizacion_%"]:.1f}% · Cola: {row["Cola Prom"]:.2f}</div>',
                            unsafe_allow_html=True)
        else:
            st.markdown('<div class="pill-ok">✅ Sin cuellos de botella</div>', unsafe_allow_html=True)

        rec_lb = [f"{REC_EMOJI.get(r,'')} {REC_LABELS.get(r,r)}" for r in df_util["Recurso"]]
        col_u = [PAL["pink"] if u>=80 else PAL["yellow"] if u>=60 else PAL["green"]
                 for u in df_util["Utilizacion_%"]]
        fig_ug = make_subplots(rows=1, cols=2, subplot_titles=["Utilización (%)","Cola Promedio"])
        fig_ug.add_trace(go.Bar(x=rec_lb, y=df_util["Utilizacion_%"], marker_color=col_u,
                                marker_line_color="white", marker_line_width=2,
                                text=[f"{v:.0f}%" for v in df_util["Utilizacion_%"]],
                                textposition="outside", showlegend=False), row=1, col=1)
        fig_ug.add_trace(go.Bar(x=rec_lb, y=df_util["Cola Prom"], marker_color=PAL["lavender"],
                                marker_line_color="white", marker_line_width=2,
                                text=[f"{v:.2f}" for v in df_util["Cola Prom"]],
                                textposition="outside", showlegend=False), row=1, col=2)
        fig_ug.add_hline(y=80, line_dash="dash", line_color=PAL["coral"],
                         annotation_text="⚠ 80%", row=1, col=1)
        fig_ug.update_layout(**PCFG, height=300)
        fig_ug.update_xaxes(showgrid=False); fig_ug.update_yaxes(gridcolor="#E8ECF1",gridwidth=0.5)
        st.plotly_chart(fig_ug, use_container_width=True)

        # Bubble chart: Utilización vs Cola (NUEVO WOW)
        st.markdown('<div class="sec-title">🫧 Análisis de Cuellos — Utilización vs Cola</div>', unsafe_allow_html=True)
        fig_bub = go.Figure()
        for _, row in df_util.iterrows():
            size = row["Capacidad"] * 25
            color = PAL["pink"] if row["Cuello Botella"] else PAL["blue"]
            fig_bub.add_trace(go.Scatter(
                x=[row["Utilizacion_%"]], y=[row["Cola Prom"]],
                marker=dict(size=size, color=color, opacity=0.7,
                            line=dict(color="white", width=2)),
                text=f"{REC_LABELS.get(row['Recurso'],row['Recurso'])}<br>"
                     f"Util: {row['Utilizacion_%']:.0f}%<br>Cola: {row['Cola Prom']:.2f}",
                hovertemplate="%{text}<extra></extra>",
                showlegend=False, mode="markers",
            ))
        fig_bub.add_vline(x=80, line_dash="dash", line_color=PAL["coral"])
        fig_bub.update_layout(**PCFG, height=280,
                              xaxis_title="Utilización (%)", yaxis_title="Cola promedio",
                              xaxis=dict(gridcolor="#E8ECF1",gridwidth=0.5),
                              yaxis=dict(gridcolor="#E8ECF1",gridwidth=0.5),
                              showlegend=False, margin=dict(t=15,b=15))
        st.plotly_chart(fig_bub, use_container_width=True)

    if not df_lotes.empty:
        st.markdown('<div class="sec-title">📅 Gantt de producción</div>', unsafe_allow_html=True)
        n_gantt = min(50, len(df_lotes)); sub = df_lotes.head(n_gantt).reset_index(drop=True)
        fig_gantt = go.Figure()
        for _, row in sub.iterrows():
            fig_gantt.add_trace(go.Bar(
                x=[row["tiempo_sistema"]], y=[row["lote_id"]], base=[row["t_creacion"]],
                orientation="h", marker_color=PROD_COLORS.get(row["producto"], "#ccc"),
                opacity=0.85, showlegend=False, marker_line_color="white", marker_line_width=0.5,
                hovertemplate=f"<b>{PROD_LABELS.get(row['producto'],'')}</b><br>"
                              f"Dur: {row['tiempo_sistema']:.1f} min<extra></extra>",
            ))
        for p, c in PROD_COLORS.items():
            fig_gantt.add_trace(go.Bar(x=[None], y=[None], marker_color=c, name=PROD_LABELS[p]))
        fig_gantt.update_layout(**PCFG, barmode="overlay",
                                height=max(350, n_gantt*8),
                                title=dict(text=f"Primeros {n_gantt} lotes",
                                           font=dict(family="Quicksand",size=12,color="#2C3E50")),
                                xaxis_title="Tiempo (min)",
                                legend=dict(orientation="h",y=-0.08,x=0.5,xanchor="center",font=dict(size=10)),
                                yaxis=dict(showticklabels=False))
        st.plotly_chart(fig_gantt, use_container_width=True)

        # Violin (NUEVO)
        st.markdown('<div class="sec-title">🎻 Distribución de tiempos por producto</div>', unsafe_allow_html=True)
        fig_vio = go.Figure()
        for p in PRODUCTOS:
            sv = df_lotes[df_lotes["producto"]==p]["tiempo_sistema"]
            if len(sv) < 3: continue
            fig_vio.add_trace(go.Violin(y=sv, name=PROD_LABELS[p], box_visible=True,
                                        meanline_visible=True, fillcolor=PROD_COLORS[p],
                                        line_color=PROD_COLORS_DARK[p], opacity=0.8,
                                        hovertemplate=f"<b>{PROD_LABELS[p]}</b><extra></extra>"))
        fig_vio.update_layout(**PCFG, height=290, yaxis_title="Min en sistema",
                              showlegend=False, violinmode="overlay",
                              yaxis=dict(gridcolor="#E8ECF1",gridwidth=0.5))
        st.plotly_chart(fig_vio, use_container_width=True)

        with st.expander("📊 KPIs completos"):
            st.dataframe(df_kpis.style.format({c:"{:,.2f}" for c in df_kpis.columns if c!="Producto"})
                         .background_gradient(subset=["Cumplimiento %"],cmap="BuGn"),
                         use_container_width=True)

# ────────────────────────────────────────────────────────────────────────────
# TAB 5 — SENSORES
# ────────────────────────────────────────────────────────────────────────────
with tabs[4]:
    st.markdown('<div class="sec-title">🌡️ Sensores Virtuales — Horno</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Simulación IoT: temperatura, ocupación y alertas del horno. '
                'Límite operativo: 200°C.</div>', unsafe_allow_html=True)

    if not df_sensores.empty:
        s1,s2,s3,s4 = st.columns(4)
        s1.metric("🌡️ Mín.", f"{df_sensores['temperatura'].min():.1f} °C")
        s2.metric("🔥 Máx.", f"{df_sensores['temperatura'].max():.1f} °C")
        s3.metric("📊 Prom.", f"{df_sensores['temperatura'].mean():.1f} °C")
        s4.metric("⚠️ Excesos", excesos,
                  delta="Revisar" if excesos else "OK",
                  delta_color="inverse" if excesos else "off")

        # Temperatura con zona operativa
        fig_temp = go.Figure()
        fig_temp.add_hrect(y0=140, y1=200, fillcolor=hex_rgba(PAL["green"], 0.15),
                           line_width=0,
                           annotation_text="Zona óptima", annotation_font_color="#1E8449",
                           annotation_font_size=10)
        fig_temp.add_trace(go.Scatter(
            x=df_sensores["tiempo"], y=df_sensores["temperatura"],
            mode="lines", name="Temperatura", fill="tozeroy",
            fillcolor=hex_rgba(PAL["peach"], 0.12),
            line=dict(color="#5D6D7E", width=1.5)))
        if len(df_sensores) > 10:
            mm = df_sensores["temperatura"].rolling(5, min_periods=1).mean()
            fig_temp.add_trace(go.Scatter(x=df_sensores["tiempo"], y=mm, mode="lines",
                                          name="Media móvil",
                                          line=dict(color=PAL["pink"], width=2, dash="dot")))
        fig_temp.add_hline(y=200, line_dash="dash", line_color="#C0392B",
                           annotation_text="⚠ 200°C", annotation_font_color="#C0392B")
        fig_temp.update_layout(**PCFG, height=300, xaxis_title="Min", yaxis_title="°C",
                               title=dict(text="Temperatura del Horno",
                                          font=dict(family="Quicksand",size=13,color="#2C3E50")),
                               legend=dict(orientation="h",y=-0.2,x=0.5,xanchor="center",font=dict(size=10)),
                               xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#E8ECF1",gridwidth=0.5))
        st.plotly_chart(fig_temp, use_container_width=True)

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            fig_ocup = go.Figure()
            fig_ocup.add_trace(go.Scatter(x=df_sensores["tiempo"], y=df_sensores["horno_ocup"],
                                          mode="lines", fill="tozeroy",
                                          fillcolor=hex_rgba(PAL["blue"], 0.2),
                                          line=dict(color="#4A90C4", width=2), name="Ocupación"))
            fig_ocup.add_hline(y=cap_horno, line_dash="dot", line_color="#2C3E50",
                               annotation_text=f"Cap: {cap_horno}")
            fig_ocup.update_layout(**PCFG, height=240, title="Ocupación",
                                   xaxis_title="min", yaxis_title="Estaciones",
                                   xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#E8ECF1",gridwidth=0.5),
                                   showlegend=False, margin=dict(t=30))
            st.plotly_chart(fig_ocup, use_container_width=True)
        with col_s2:
            fig_hist = go.Figure()
            fig_hist.add_trace(go.Histogram(x=df_sensores["temperatura"], nbinsx=30,
                                            marker_color=PAL["lavender"], opacity=0.85,
                                            marker_line_color="white", marker_line_width=1))
            fig_hist.add_vline(x=200, line_dash="dash", line_color="#C0392B",
                               annotation_text="200°C")
            fig_hist.add_vline(x=df_sensores["temperatura"].mean(), line_dash="dot",
                               line_color="#2C3E50",
                               annotation_text=f"μ={df_sensores['temperatura'].mean():.0f}°C")
            fig_hist.update_layout(**PCFG, height=240, title="Distribución",
                                   xaxis_title="°C", yaxis_title="Frecuencia", showlegend=False,
                                   xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#E8ECF1",gridwidth=0.5),
                                   margin=dict(t=30))
            st.plotly_chart(fig_hist, use_container_width=True)
    else:
        st.info("Sin datos de sensores.")

# ────────────────────────────────────────────────────────────────────────────
# TAB 6 — ESCENARIOS WHAT-IF
# ────────────────────────────────────────────────────────────────────────────
with tabs[5]:
    st.markdown('<div class="sec-title">🔬 Análisis What-If</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Compara configuraciones de planta para encontrar la estrategia '
                'óptima de producción en la panadería Dora del Hoyo.</div>', unsafe_allow_html=True)

    ESC_DEF = {
        "Base":               {"fd":1.0,"falla":False,"ft":1.0, "cd":0},
        "Demanda +20%":       {"fd":1.2,"falla":False,"ft":1.0, "cd":0},
        "Demanda −20%":       {"fd":0.8,"falla":False,"ft":1.0, "cd":0},
        "Falla en horno":     {"fd":1.0,"falla":True, "ft":1.0, "cd":0},
        "Horno reducido":     {"fd":1.0,"falla":False,"ft":1.0, "cd":-1},
        "Horno ampliado":     {"fd":1.0,"falla":False,"ft":1.0, "cd":+1},
        "Doble turno":        {"fd":1.0,"falla":False,"ft":0.80,"cd":0},
        "Optimizado":         {"fd":1.0,"falla":False,"ft":0.85,"cd":+1},
    }
    ESC_ICO = {"Base":"🏠","Demanda +20%":"📈","Demanda −20%":"📉","Falla en horno":"⚠️",
               "Horno reducido":"⬇️","Horno ampliado":"⬆️","Doble turno":"🕐","Optimizado":"🚀"}

    esc_sel = st.multiselect("Escenarios a comparar", list(ESC_DEF.keys()),
                              default=["Base","Demanda +20%","Falla en horno","Doble turno","Optimizado"])

    if st.button("🚀 Comparar escenarios", type="primary"):
        filas = []; prog = st.progress(0)
        for i, nm in enumerate(esc_sel):
            prog.progress((i+1)/len(esc_sel), text=f"Simulando: {nm}…")
            cfg = ESC_DEF[nm]
            pe = {p: max(int(u*cfg["fd"]), 0) for p, u in plan_mes.items()}
            ce = {**CAPACIDAD_BASE, "horno": max(cap_horno+cfg["cd"], 1)}
            dl, du, _ = run_simulacion_cached(tuple(pe.items()), tuple(ce.items()),
                                               cfg["falla"], cfg["ft"], int(semilla))
            k = calc_kpis(dl, pe); u = calc_utilizacion(du)
            fila = {"Escenario": f"{ESC_ICO.get(nm,'')} {nm}"}
            if not k.empty:
                fila["Throughput"]   = round(k["Throughput (und/h)"].mean(), 2)
                fila["Lead Time"]    = round(k["Lead Time (min/lote)"].mean(), 2)
                fila["WIP Prom"]     = round(k["WIP Prom"].mean(), 2)
                fila["Cumplimiento"] = round(k["Cumplimiento %"].mean(), 2)
            if not u.empty:
                fila["Util. max"]    = round(u["Utilizacion_%"].max(), 2)
                fila["Cuellos"]      = int(u["Cuello Botella"].sum())
            fila["Lotes"] = len(dl)
            filas.append(fila)
        prog.empty()
        df_comp = pd.DataFrame(filas)

        st.markdown('<div class="sec-title">📊 Resultados comparativos</div>', unsafe_allow_html=True)
        nc = [c for c in df_comp.columns if c != "Escenario" and df_comp[c].dtype != "object"]
        st.dataframe(df_comp.style.format({c: "{:,.2f}" for c in nc})
                     .background_gradient(subset=["Cumplimiento"] if "Cumplimiento" in df_comp.columns else [],
                                          cmap="BuGn"),
                     use_container_width=True)

        if len(df_comp) > 1:
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                st.markdown('<div class="sec-title">✅ Cumplimiento</div>', unsafe_allow_html=True)
                if "Cumplimiento" in df_comp.columns:
                    cc = [PAL["green"] if v>=90 else PAL["yellow"] if v>=70 else PAL["pink"]
                          for v in df_comp["Cumplimiento"]]
                    fig_ec = go.Figure(go.Bar(x=df_comp["Escenario"], y=df_comp["Cumplimiento"],
                                              marker_color=cc, marker_line_color="white", marker_line_width=2,
                                              text=[f"{v:.1f}%" for v in df_comp["Cumplimiento"]],
                                              textposition="outside"))
                    fig_ec.add_hline(y=100, line_dash="dash", line_color="#2C3E50")
                    fig_ec.update_layout(**PCFG, height=280, yaxis_title="%",
                                         xaxis=dict(showgrid=False, tickangle=-20),
                                         yaxis=dict(gridcolor="#E8ECF1",gridwidth=0.5),
                                         showlegend=False, margin=dict(t=25,b=60))
                    st.plotly_chart(fig_ec, use_container_width=True)
            with col_e2:
                st.markdown('<div class="sec-title">⚙️ Utilización máx.</div>', unsafe_allow_html=True)
                if "Util. max" in df_comp.columns:
                    cu = [PAL["pink"] if v>=80 else PAL["yellow"] if v>=60 else PAL["green"]
                          for v in df_comp["Util. max"]]
                    fig_eu = go.Figure(go.Bar(x=df_comp["Escenario"], y=df_comp["Util. max"],
                                              marker_color=cu, marker_line_color="white", marker_line_width=2,
                                              text=[f"{v:.0f}%" for v in df_comp["Util. max"]],
                                              textposition="outside"))
                    fig_eu.add_hline(y=80, line_dash="dash", line_color=PAL["coral"],
                                     annotation_text="⚠ 80%")
                    fig_eu.update_layout(**PCFG, height=280, yaxis_title="%",
                                         xaxis=dict(showgrid=False, tickangle=-20),
                                         yaxis=dict(gridcolor="#E8ECF1",gridwidth=0.5),
                                         showlegend=False, margin=dict(t=25,b=60))
                    st.plotly_chart(fig_eu, use_container_width=True)

            # Radar
            st.markdown('<div class="sec-title">🕸️ Radar comparativo</div>', unsafe_allow_html=True)
            cr = [c for c in df_comp.columns if c not in ["Escenario","Cuellos"]
                  and df_comp[c].dtype != "object"]
            if len(cr) >= 3:
                dn = df_comp[cr].copy()
                for c in dn.columns:
                    rng = dn[c].max()-dn[c].min()
                    dn[c] = (dn[c]-dn[c].min())/rng if rng else 0.5
                RC = [PAL["lavender"],PAL["blue"],PAL["pink"],PAL["green"],
                      PAL["yellow"],PAL["peach"],PAL["coral"],PAL["mint"]]
                RA = [hex_rgba(c, 0.12) for c in RC]
                fig_rad = go.Figure()
                for i, row in df_comp.iterrows():
                    vals = [dn.loc[i, c] for c in cr]
                    fig_rad.add_trace(go.Scatterpolar(
                        r=vals+[vals[0]], theta=cr+[cr[0]],
                        fill="toself", name=row["Escenario"],
                        line=dict(color=RC[i%len(RC)], width=2),
                        fillcolor=RA[i%len(RA)]))
                fig_rad.update_layout(**PCFG, height=420,
                    polar=dict(radialaxis=dict(visible=True, range=[0,1],
                              gridcolor="#E8ECF1", linecolor="#E8ECF1"),
                              angularaxis=dict(gridcolor="#E8ECF1")),
                    title=dict(text="Comparación normalizada",
                               font=dict(family="Quicksand",size=13,color="#2C3E50")),
                    legend=dict(orientation="h",y=-0.12,x=0.5,xanchor="center",font=dict(size=10)))
                st.plotly_chart(fig_rad, use_container_width=True)

            # Coordenadas paralelas (NUEVO WOW)
            st.markdown('<div class="sec-title">🔗 Coordenadas Paralelas</div>', unsafe_allow_html=True)
            if "Cumplimiento" in df_comp.columns and "Util. max" in df_comp.columns:
                fig_par = go.Figure(go.Parcoords(
                    line=dict(color=df_comp["Cumplimiento"],
                              colorscale=[[0,PAL["pink"]],[0.5,PAL["yellow"]],[1,PAL["green"]]],
                              showscale=True, colorbar=dict(title="Cumpl.%")),
                    dimensions=[
                        dict(label="Throughput", values=df_comp["Throughput"]),
                        dict(label="Lead Time", values=df_comp["Lead Time"]),
                        dict(label="WIP", values=df_comp["WIP Prom"]),
                        dict(label="Cumplimiento", values=df_comp["Cumplimiento"], range=[0,110]),
                        dict(label="Util. max", values=df_comp["Util. max"]),
                        dict(label="Cuellos", values=df_comp["Cuellos"]),
                    ],
                    tickfont=dict(size=9),
                ))
                fig_par.update_layout(**PCFG, height=320, margin=dict(t=15,b=15))
                st.plotly_chart(fig_par, use_container_width=True)
    else:
        st.markdown("""
        <div class="info-box" style="text-align:center;padding:2rem">
          <div style="font-size:2.5rem">🔬</div>
          <b>Selecciona escenarios y haz clic en Comparar</b><br>
          <span style="font-size:0.85rem;color:#95A5A6">
          Se simulará cada escenario y se generarán KPIs, radar y coordenadas paralelas</span>
        </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("""
<div style='text-align:center;color:#95A5A6;font-size:0.78rem;
     font-family:Inter,sans-serif;padding:0.3rem 0 0.8rem'>
  🥐 <b>Gemelo Digital — Panadería Dora del Hoyo</b> &nbsp;·&nbsp;
  PuLP · SimPy · Plotly · Streamlit
</div>""", unsafe_allow_html=True)
