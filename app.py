"""
app.py  —  Gemelo Digital · Panadería Dora del Hoyo
====================================================
Versión 4.0 — Integración definitiva:
  • Paleta y estética del v3.1 (tonos suaves propios, fuentes Fraunces + Plus Jakarta Sans)
  • Sidebar: SOLO parámetros globales
  • Cada sección tiene sus propios parámetros DENTRO del tab
  • Toda la riqueza funcional del v3.0: mix de demanda, planeación agregada avanzada,
    desagregación con suavizado, simulación con variabilidad/espaciamiento/iteraciones,
    gráfico combinado Producción+Inventario+Demanda, sensores virtuales, escenarios what-if
  • Reactivo: cualquier cambio de parámetro regenera resultados correctamente
  • KPIs con litros y cobertura comercial

Ejecutar:  streamlit run app.py
"""

import math
import random
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import simpy
import streamlit as st
from pulp import LpProblem, LpMinimize, LpVariable, lpSum, value, PULP_CBC_CMD

# ══════════════════════════════════════════════════════════════════════════════
# PALETA · DORA DEL HOYO v4 (tonos del v3.1, enriquecidos)
# ══════════════════════════════════════════════════════════════════════════════
C = {
    "bg":        "#FFFDF8",
    "panel":     "#FFFFFF",
    "panel_2":   "#FFF7F1",
    "text":      "#46352A",
    "muted":     "#8C7B70",
    "line":      "#EADFD7",
    "pink":      "#F6C9D0",
    "peach":     "#FFD7BA",
    "butter":    "#FCE7A8",
    "mint":      "#CFE9D9",
    "sky":       "#CFE4F6",
    "lavender":  "#DDD2F4",
    "salmon":    "#F7B7A3",
    "sage":      "#BFD8C1",
    "rosewood":  "#B9857E",
    "gold":      "#E8C27A",
    "coffee":    "#8B5E3C",
    "mocha":     "#C68B59",
    "cream":     "#FFF8EE",
}

PROD_COLORS = {
    "Brownies":           "#D9B38C",
    "Mantecadas":         "#CFE4F6",
    "Mantecadas_Amapola": "#CFE9D9",
    "Torta_Naranja":      "#F6D0E6",
    "Pan_Maiz":           "#FFD7BA",
}
PROD_COLORS_DARK = {
    "Brownies":           "#9B7452",
    "Mantecadas":         "#6B9CC9",
    "Mantecadas_Amapola": "#6FA889",
    "Torta_Naranja":      "#A77DBA",
    "Pan_Maiz":           "#D98E68",
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
REC_LABELS = {
    "mezcla":"🥣 Mezcla","dosificado":"🔧 Dosificado","horno":"🔥 Horno",
    "enfriamiento":"❄️ Enfriamiento","empaque":"📦 Empaque","amasado":"👐 Amasado",
}


def hex_rgba(hex_color: str, alpha: float = 0.15) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ══════════════════════════════════════════════════════════════════════════════
# DATOS MAESTROS
# ══════════════════════════════════════════════════════════════════════════════
PRODUCTOS = ["Brownies","Mantecadas","Mantecadas_Amapola","Torta_Naranja","Pan_Maiz"]
MESES     = ["January","February","March","April","May","June",
             "July","August","September","October","November","December"]
MESES_ES  = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]
MESES_F   = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto",
             "Septiembre","Octubre","Noviembre","Diciembre"]

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
LITROS_UNIDAD_BASE = {
    "Brownies":0.5,"Mantecadas":0.15,"Mantecadas_Amapola":0.15,
    "Torta_Naranja":0.8,"Pan_Maiz":0.3,
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
TAMANO_LOTE_BASE = {"Brownies":12,"Mantecadas":10,"Mantecadas_Amapola":10,
                    "Torta_Naranja":12,"Pan_Maiz":15}
INV_INICIAL = {p:0 for p in PRODUCTOS}


# ══════════════════════════════════════════════════════════════════════════════
# FUNCIONES CORE
# ══════════════════════════════════════════════════════════════════════════════
def get_demanda_historica(mix_factors, factor_demanda):
    dem = {}
    for p in PRODUCTOS:
        mf = mix_factors.get(p, 1.0)
        dem[p] = [round(v * factor_demanda * mf, 1) for v in DEM_BASE[p]]
    return dem


def demanda_horas_hombre(dem_hist):
    return {mes: round(sum(dem_hist[p][i]*HORAS_PRODUCTO[p] for p in PRODUCTOS), 4)
            for i, mes in enumerate(MESES)}


def pronostico_simple(serie, meses_extra=3):
    alpha = 0.3
    nivel = serie[0]
    suavizada = []
    for v in serie:
        nivel = alpha*v + (1-alpha)*nivel
        suavizada.append(nivel)
    futuro = []
    last = suavizada[-1]
    trend = (suavizada[-1]-suavizada[-4])/3 if len(suavizada)>=4 else 0
    for _ in range(meses_extra):
        last = last + alpha*trend
        futuro.append(round(last, 1))
    return suavizada, futuro


@st.cache_data(show_spinner=False)
def run_agregacion(dem_hh_items, params_tuple):
    params = dict(params_tuple)
    dem_h  = dict(dem_hh_items)
    Ct=params["Ct"]; Ht=params["Ht"]; PIt=params["PIt"]
    CRt=params["CRt"]; COt=params["COt"]; Wm=params["CW_mas"]; Wd=params["CW_menos"]
    M=params["M"]; LRi=params["LR_inicial"]; stock_obj=params.get("stock_obj", 0.0)

    # Sufijo único por combinación de parámetros para evitar conflictos
    # de nombres en el registro global de PuLP entre llamadas cacheadas
    _uid = str(abs(hash((dem_hh_items, params_tuple))) % 999983)
    mdl = LpProblem(f"Agregacion_{_uid}", LpMinimize)
    P   = LpVariable.dicts(f"P_{_uid}",  MESES, lowBound=0)
    I   = LpVariable.dicts(f"I_{_uid}",  MESES, lowBound=0)
    S   = LpVariable.dicts(f"S_{_uid}",  MESES, lowBound=0)
    LR  = LpVariable.dicts(f"LR_{_uid}", MESES, lowBound=0)
    LO  = LpVariable.dicts(f"LO_{_uid}", MESES, lowBound=0)
    LU  = LpVariable.dicts(f"LU_{_uid}", MESES, lowBound=0)
    NI  = LpVariable.dicts(f"NI_{_uid}", MESES)
    Wmas   = LpVariable.dicts(f"Wm_{_uid}", MESES, lowBound=0)
    Wmenos = LpVariable.dicts(f"Wd_{_uid}", MESES, lowBound=0)

    mdl += lpSum(Ct*P[t]+Ht*I[t]+PIt*S[t]+CRt*LR[t]+COt*LO[t]+Wm*Wmas[t]+Wd*Wmenos[t]
                 for t in MESES)
    for idx, t in enumerate(MESES):
        d  = dem_h[t]
        tp = MESES[idx-1] if idx>0 else None
        if idx==0: mdl += NI[t] == P[t]-d
        else:      mdl += NI[t] == NI[tp]+P[t]-d
        mdl += NI[t] == I[t]-S[t]
        mdl += LU[t]+LO[t] == M*P[t]
        mdl += LU[t] <= LR[t]
        if stock_obj > 0: mdl += I[t] >= stock_obj*d
        if idx==0: mdl += LR[t] == LRi+Wmas[t]-Wmenos[t]
        else:      mdl += LR[t] == LR[tp]+Wmas[t]-Wmenos[t]

    mdl.solve(PULP_CBC_CMD(msg=False))
    costo = value(mdl.objective) or 0

    ini_l, fin_l = [], []
    for idx, t in enumerate(MESES):
        ini = 0.0 if idx==0 else fin_l[-1]
        ini_l.append(ini)
        fin_l.append(ini+(P[t].varValue or 0)-dem_h[t])

    df = pd.DataFrame({
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
def run_desagregacion(prod_hh_items, dem_hist_items, costo_pen, costo_inv, suavizado):
    prod_hh  = dict(prod_hh_items)
    dem_hist = {p: list(v) for p, v in dem_hist_items}

    # Sufijo único por combinación de parámetros para evitar conflictos
    # de nombres en el registro global de PuLP entre llamadas cacheadas
    _uid = str(abs(hash((prod_hh_items, dem_hist_items, costo_pen, costo_inv, suavizado))) % 999983)
    mdl = LpProblem(f"Desagregacion_{_uid}", LpMinimize)
    X  = {(p,t): LpVariable(f"X_{_uid}_{p}_{t}", lowBound=0) for p in PRODUCTOS for t in MESES}
    I  = {(p,t): LpVariable(f"I_{_uid}_{p}_{t}", lowBound=0) for p in PRODUCTOS for t in MESES}
    S  = {(p,t): LpVariable(f"S_{_uid}_{p}_{t}", lowBound=0) for p in PRODUCTOS for t in MESES}
    DX = {(p,t): LpVariable(f"DX_{_uid}_{p}_{t}", lowBound=0) for p in PRODUCTOS for t in MESES}

    mdl += lpSum(costo_inv*I[p,t]+costo_pen*S[p,t]+suavizado*DX[p,t]
                 for p in PRODUCTOS for t in MESES)

    for idx, t in enumerate(MESES):
        tp = MESES[idx-1] if idx>0 else None
        mdl += (lpSum(HORAS_PRODUCTO[p]*X[p,t] for p in PRODUCTOS) <= prod_hh[t])
        for p in PRODUCTOS:
            d = dem_hist[p][idx]
            if idx==0: mdl += I[p,t]-S[p,t] == INV_INICIAL[p]+X[p,t]-d
            else:      mdl += I[p,t]-S[p,t] == I[p,tp]-S[p,tp]+X[p,t]-d
            if idx>0:
                prev_x = X[p,tp]
                mdl += DX[p,t] >= X[p,t]-prev_x
                mdl += DX[p,t] >= prev_x-X[p,t]

    mdl.solve(PULP_CBC_CMD(msg=False))

    resultados = {}
    for p in PRODUCTOS:
        filas = []
        for idx, t in enumerate(MESES):
            xv = round(X[p,t].varValue or 0, 2)
            iv = round(I[p,t].varValue or 0, 2)
            sv = round(S[p,t].varValue or 0, 2)
            ini = INV_INICIAL[p] if idx==0 else round(I[p,MESES[idx-1]].varValue or 0, 2)
            filas.append({"Mes":t,"Mes_ES":MESES_ES[idx],"Mes_F":MESES_F[idx],
                          "Demanda":dem_hist[p][idx],
                          "Produccion":xv,"Inv_Ini":ini,"Inv_Fin":iv,"Backlog":sv})
        resultados[p] = pd.DataFrame(filas)
    return resultados


@st.cache_data(show_spinner=False)
def run_simulacion_cached(plan_items, cap_items, falla, factor_t,
                          variabilidad=1.0, espaciamiento=1.0, semilla=42,
                          temp_horno_base=160):
    plan_unidades = dict(plan_items)
    cap_recursos  = dict(cap_items)
    random.seed(semilla); np.random.seed(semilla)
    lotes_data, uso_rec, sensores = [], [], []

    def sensor_horno(env, recursos):
        while True:
            ocp  = recursos["horno"].count
            temp = round(np.random.normal(temp_horno_base + ocp*18, 4.5*variabilidad), 2)
            sensores.append({"tiempo":round(env.now,1),"temperatura":temp,
                             "horno_ocup":ocp,"horno_cola":len(recursos["horno"].queue)})
            yield env.timeout(10)

    def reg_uso(env, recursos, prod=""):
        ts = round(env.now, 3)
        for nm, r in recursos.items():
            uso_rec.append({"tiempo":ts,"recurso":nm,"ocupados":r.count,
                            "cola":len(r.queue),"capacidad":r.capacity,"producto":prod})

    def proceso_lote(env, lid, prod, tam, recursos):
        t0 = env.now
        esperas = {}
        for etapa, rec_nm, tmin, tmax in RUTAS[prod]:
            escala = math.sqrt(tam/TAMANO_LOTE_BASE[prod])
            tp = random.uniform(tmin*variabilidad, tmax*variabilidad)*escala*factor_t
            if falla and rec_nm=="horno": tp += random.uniform(10, 30)
            reg_uso(env, recursos, prod)
            t_entrada = env.now
            with recursos[rec_nm].request() as req:
                yield req
                esperas[etapa] = round(env.now-t_entrada, 3)
                reg_uso(env, recursos, prod)
                yield env.timeout(tp)
            reg_uso(env, recursos, prod)
        lotes_data.append({"lote_id":lid,"producto":prod,"tamano":tam,
                           "t_creacion":round(t0,3),"t_fin":round(env.now,3),
                           "tiempo_sistema":round(env.now-t0,3),
                           "total_espera":round(sum(esperas.values()),3)})

    env      = simpy.Environment()
    recursos = {nm: simpy.Resource(env, capacity=cap) for nm, cap in cap_recursos.items()}
    env.process(sensor_horno(env, recursos))

    dur_mes = 44*4*60
    lotes   = []
    ctr     = [0]

    for prod, unid in plan_unidades.items():
        if unid <= 0: continue
        tam  = TAMANO_LOTE_BASE[prod]
        n    = math.ceil(unid/tam)
        tasa = dur_mes/max(n,1)*espaciamiento
        ta   = random.expovariate(1/max(tasa,1))
        rem  = unid
        for _ in range(n):
            lotes.append((round(ta,2), prod, min(tam, int(rem))))
            rem -= tam
            ta  += random.expovariate(1/max(tasa,1))

    lotes.sort(key=lambda x: x[0])

    def lanzador():
        for ta, prod, tam in lotes:
            yield env.timeout(max(ta-env.now, 0))
            lid = f"{prod[:3].upper()}_{ctr[0]:04d}"; ctr[0] += 1
            env.process(proceso_lote(env, lid, prod, tam, recursos))

    env.process(lanzador())
    env.run(until=dur_mes*1.8)

    df_lotes    = pd.DataFrame(lotes_data) if lotes_data else pd.DataFrame()
    df_uso      = pd.DataFrame(uso_rec)    if uso_rec    else pd.DataFrame()
    df_sensores = pd.DataFrame(sensores)   if sensores   else pd.DataFrame()
    return df_lotes, df_uso, df_sensores


def calc_utilizacion(df_uso):
    if df_uso.empty: return pd.DataFrame()
    filas = []
    for rec, grp in df_uso.groupby("recurso"):
        grp = grp.sort_values("tiempo").reset_index(drop=True)
        cap = grp["capacidad"].iloc[0]
        t   = grp["tiempo"].values
        ocp = grp["ocupados"].values
        if len(t)>1 and (t[-1]-t[0])>0:
            fn   = np.trapezoid if hasattr(np,"trapezoid") else np.trapz
            util = round(fn(ocp,t)/(cap*(t[-1]-t[0]))*100, 2)
        else: util = 0.0
        filas.append({"Recurso":rec,"Utilizacion_%":util,
                      "Cola Prom":round(grp["cola"].mean(),3),
                      "Cola Max":int(grp["cola"].max()),
                      "Capacidad":int(cap),
                      "Cuello Botella": util>=80 or grp["cola"].mean()>0.5})
    return pd.DataFrame(filas).sort_values("Utilizacion_%", ascending=False).reset_index(drop=True)


def calc_kpis(df_lotes, plan):
    if df_lotes.empty: return pd.DataFrame()
    dur = (df_lotes["t_fin"].max()-df_lotes["t_creacion"].min())/60
    filas = []
    for p in PRODUCTOS:
        sub = df_lotes[df_lotes["producto"]==p]
        if sub.empty: continue
        und      = sub["tamano"].sum()
        plan_und = plan.get(p, 0)
        tp   = round(und/max(dur,0.01), 3)
        ct   = round((sub["tiempo_sistema"]/sub["tamano"]).mean(), 3)
        lt   = round(sub["tiempo_sistema"].mean(), 3)
        dem_avg = sum(DEM_BASE[p])/12
        takt = round((44*4*60)/max(dem_avg/TAMANO_LOTE_BASE[p],1), 2)
        wip  = round(tp*(lt/60), 2)
        filas.append({"Producto":PROD_LABELS[p],"Und Producidas":und,"Plan":plan_und,
                      "Throughput (und/h)":tp,"Cycle Time (min/und)":ct,
                      "Lead Time (min/lote)":lt,"WIP Prom":wip,"Takt (min/lote)":takt,
                      "Cumplimiento %":round(min(und/max(plan_und,1)*100,100),2)})
    return pd.DataFrame(filas)


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG STREAMLIT
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Gemelo Digital · Dora del Hoyo",
    page_icon="🥐",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,wght@0,500;0,600;0,700;1,500&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {{
  font-family: 'Plus Jakarta Sans', sans-serif;
  background: {C["bg"]};
  color: {C["text"]};
}}
.block-container {{ padding-top: 1rem; padding-bottom: 1.5rem; }}

/* HERO */
.hero {{
  background: linear-gradient(135deg, {C["lavender"]} 0%, {C["sky"]} 40%, {C["peach"]} 100%);
  padding: 2rem 2.5rem 1.7rem;
  border-radius: 24px;
  margin-bottom: 1.4rem;
  border: 1px solid {C["line"]};
  box-shadow: 0 14px 32px rgba(120,100,90,0.11);
  position: relative; overflow: hidden;
}}
.hero::before {{
  content: "🥐";
  font-size: 9rem;
  position: absolute; right: 2rem; top: -1.5rem;
  opacity: 0.07; transform: rotate(-15deg);
  pointer-events: none;
}}
.hero h1 {{
  font-family: 'Fraunces', serif;
  color: {C["text"]}; font-size: 2.2rem; margin: 0; font-weight: 700;
}}
.hero p {{ color: {C["muted"]}; margin: 0.45rem 0 0; font-size: 0.95rem; }}
.hero .badge {{
  display: inline-block;
  background: rgba(255,255,255,0.72);
  color: {C["text"]};
  padding: 0.28rem 0.85rem; border-radius: 999px;
  font-size: 0.75rem; margin-top: 0.8rem; margin-right: 0.35rem;
  border: 1px solid {C["line"]};
  backdrop-filter: blur(4px);
}}

/* KPI CARDS */
.kpi-card {{
  background: {C["panel"]};
  border-radius: 18px;
  padding: 1.05rem 0.9rem;
  border: 1px solid {C["line"]};
  box-shadow: 0 6px 18px rgba(120,100,90,0.07);
  text-align: center;
  transition: transform 0.22s, box-shadow 0.22s;
}}
.kpi-card:hover {{ transform: translateY(-3px); box-shadow: 0 12px 28px rgba(120,100,90,0.13); }}
.kpi-card .icon {{ font-size: 1.5rem; margin-bottom: 0.2rem; }}
.kpi-card .val {{
  font-family: 'Fraunces', serif;
  font-size: 1.65rem; color: {C["text"]}; line-height: 1; margin: 0.12rem 0;
}}
.kpi-card .lbl {{
  font-size: 0.68rem; color: {C["rosewood"]};
  text-transform: uppercase; letter-spacing: 0.09em; font-weight: 700; margin-top: 0.22rem;
}}
.kpi-card .sub {{ font-size: 0.76rem; color: {C["muted"]}; margin-top: 0.18rem; }}

/* SECTION TITLES */
.sec-title {{
  font-family: 'Fraunces', serif;
  font-size: 1.28rem; color: {C["text"]};
  border-left: 5px solid {C["gold"]};
  padding-left: 0.8rem;
  margin: 1.3rem 0 0.75rem;
  font-weight: 600;
}}

/* INFO BOX */
.info-box {{
  background: {C["panel_2"]};
  border: 1px solid {C["line"]};
  border-radius: 14px;
  padding: 0.85rem 1.1rem;
  font-size: 0.88rem; color: {C["text"]};
  margin: 0.4rem 0 0.9rem;
}}

/* PILLS */
.pill-ok   {{ background:{C["mint"]}; color:{C["text"]}; padding:0.28rem 0.9rem; border-radius:999px; font-size:0.82rem; font-weight:600; display:inline-block; }}
.pill-warn {{ background:{C["pink"]}; color:{C["text"]}; padding:0.28rem 0.9rem; border-radius:999px; font-size:0.82rem; font-weight:600; display:inline-block; }}

/* SIDEBAR */
[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, #fffaf3 0%, #fff3eb 100%) !important;
  border-right: 1px solid {C["line"]};
}}
[data-testid="stSidebar"] * {{ color: {C["text"]} !important; }}
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
  font-family: 'Fraunces', serif !important;
  color: {C["coffee"]} !important;
}}

/* TABS */
.stTabs [data-baseweb="tab"] {{
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-weight: 600; color: {C["muted"]};
}}
.stTabs [aria-selected="true"] {{ color: {C["text"]} !important; }}

/* EXPANDERS */
.streamlit-expanderHeader {{ font-weight: 600; }}
</style>
""", unsafe_allow_html=True)


PLOT_CFG = dict(
    template="plotly_white",
    font=dict(family="Plus Jakarta Sans", color=C["text"]),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor=C["bg"],
)


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR — SOLO PARÁMETROS GLOBALES
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🥐 Dora del Hoyo")
    st.markdown("*Gemelo Digital v4.0*")
    st.markdown("---")
    st.markdown("### 🌐 Parámetros Globales")
    st.markdown("*Los parámetros específicos de cada módulo están dentro de su pestaña.*")

    mes_idx = st.selectbox(
        "📅 Mes de análisis", range(12), index=1,
        format_func=lambda i: MESES_F[i]
    )
    factor_demanda = st.slider("📈 Impulso de demanda", 0.5, 2.0, 1.0, 0.05)
    meses_pronostico = st.slider("🔮 Horizonte de proyección (meses)", 1, 6, 3)
    participacion_mercado = st.slider("🛒 Cobertura comercial (%)", 10, 100, 75, 5)
    litros_por_unidad = st.slider("🧁 Litros promedio por unidad", 0.1, 2.0, 0.35, 0.05)
    semilla = st.number_input("🎲 Semilla aleatoria", value=42, step=1)

    st.markdown("---")
    st.markdown('<div style="font-size:0.74rem;color:#8C7B70;">📍 Panadería Dora del Hoyo<br>🔢 SimPy · PuLP · Streamlit v4</div>', unsafe_allow_html=True)


PLOT_CFG = dict(
    template="plotly_white",
    font=dict(family="Plus Jakarta Sans", color=C["text"]),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor=C["bg"],
)

# Placeholders: se rellenan al final del script cuando todos los cálculos están listos
hero_placeholder = st.empty()
kpi_placeholder  = st.empty()
st.markdown("<br>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TABS — DEFINICIÓN
# ══════════════════════════════════════════════════════════════════════════════
tabs = st.tabs([
    "📊 Demanda & Pronóstico",
    "📋 Plan Agregado",
    "📦 Desagregación",
    "🏭 Simulación",
    "🌡️ Sensores",
    "🔬 Escenarios",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — DEMANDA: parámetros propios + visualizaciones
# ══════════════════════════════════════════════════════════════════════════════
with tabs[0]:
    st.markdown('<div class="sec-title">📊 Parámetros de demanda</div>', unsafe_allow_html=True)

    with st.expander("🎛️ Mix de participación por producto", expanded=False):
        mc1,mc2,mc3,mc4,mc5 = st.columns(5)
        mix_brownies   = mc1.slider("🍫 Brownies",       0.3, 2.0, 1.0, 0.05, key="mix_br")
        mix_mantecadas = mc2.slider("🧁 Mantecadas",      0.3, 2.0, 1.0, 0.05, key="mix_ma")
        mix_amapola    = mc3.slider("🌸 Mant. Amapola",  0.3, 2.0, 1.0, 0.05, key="mix_am")
        mix_torta      = mc4.slider("🍊 Torta Naranja",  0.3, 2.0, 1.0, 0.05, key="mix_to")
        mix_panmaiz    = mc5.slider("🌽 Pan de Maíz",    0.3, 2.0, 1.0, 0.05, key="mix_pn")

    MIX_FACTORS = {
        "Brownies":mix_brownies,"Mantecadas":mix_mantecadas,
        "Mantecadas_Amapola":mix_amapola,"Torta_Naranja":mix_torta,"Pan_Maiz":mix_panmaiz,
    }

    DEM_HIST = get_demanda_historica(MIX_FACTORS, factor_demanda)
    dem_h    = demanda_horas_hombre(DEM_HIST)

    st.markdown('<div class="sec-title">📈 Demanda histórica y pronóstico</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Datos ajustados por mix de producto y factor de impulso global · Suavizado exponencial α=0.3 · Las líneas punteadas representan la proyección futura.</div>', unsafe_allow_html=True)

    fig_pro = go.Figure()
    for p in PRODUCTOS:
        serie = DEM_HIST[p]
        suav, futuro = pronostico_simple(serie, meses_pronostico)
        fig_pro.add_trace(go.Scatter(
            x=MESES_ES, y=serie, mode="lines+markers", name=PROD_LABELS[p],
            line=dict(color=PROD_COLORS_DARK[p], width=2.5),
            marker=dict(size=6, color=PROD_COLORS[p], line=dict(color="white", width=1.5)),
        ))
        meses_fut = [f"P+{j+1}" for j in range(meses_pronostico)]
        fig_pro.add_trace(go.Scatter(
            x=[MESES_ES[-1]]+meses_fut, y=[suav[-1]]+futuro,
            mode="lines+markers", showlegend=False,
            line=dict(color=PROD_COLORS_DARK[p], width=2, dash="dot"),
            marker=dict(size=9, color=PROD_COLORS[p], symbol="diamond",
                        line=dict(color=PROD_COLORS_DARK[p], width=1.5)),
        ))
    fig_pro.add_vrect(
        x0=len(MESES_ES)-0.5, x1=len(MESES_ES)+meses_pronostico-0.5,
        fillcolor=hex_rgba(C["lavender"], 0.18), line_width=0,
        annotation_text="▶ Proyección", annotation_position="top left",
        annotation_font_color=C["rosewood"],
    )
    fig_pro.update_layout(**PLOT_CFG, height=420,
                          title="Demanda histórica y horizonte proyectado",
                          xaxis_title="Mes", yaxis_title="Unidades estimadas",
                          legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center"),
                          xaxis=dict(showgrid=True, gridcolor=C["line"]),
                          yaxis=dict(showgrid=True, gridcolor=C["line"]))
    st.plotly_chart(fig_pro, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown('<div class="sec-title">🔥 Mapa de calor — Estacionalidad</div>', unsafe_allow_html=True)
        z = [[DEM_HIST[p][i] for i in range(12)] for p in PRODUCTOS]
        fig_heat = go.Figure(go.Heatmap(
            z=z, x=MESES_ES, y=[PROD_LABELS[p] for p in PRODUCTOS],
            colorscale=[[0,C["bg"]],[0.35,C["butter"]],[0.65,C["peach"]],[1,C["rosewood"]]],
            hovertemplate="%{y}<br>%{x}: %{z:.0f} und<extra></extra>",
            text=[[f"{int(v)}" for v in row] for row in z],
            texttemplate="%{text}", textfont=dict(size=9, color=C["text"]),
        ))
        fig_heat.update_layout(**PLOT_CFG, height=260, title="Mapa estacional", margin=dict(t=40,b=10))
        st.plotly_chart(fig_heat, use_container_width=True)

    with col_b:
        st.markdown('<div class="sec-title">🌸 Participación anual</div>', unsafe_allow_html=True)
        totales = {p: sum(DEM_HIST[p]) for p in PRODUCTOS}
        fig_pie = go.Figure(go.Pie(
            labels=[PROD_LABELS[p] for p in PRODUCTOS],
            values=list(totales.values()), hole=0.58,
            marker=dict(colors=list(PROD_COLORS.values()), line=dict(color="white", width=3)),
            textfont=dict(size=11),
            hovertemplate="%{label}<br>%{value:,.0f} und/año<br>%{percent}<extra></extra>",
        ))
        fig_pie.update_layout(**PLOT_CFG, height=260, title="Aporte anual por línea",
                              annotations=[dict(text="<b>Mix</b>", x=0.5, y=0.5,
                                                font=dict(size=13, color=C["text"]), showarrow=False)],
                              legend=dict(orientation="v", x=1, y=0.5, font=dict(size=11)))
        st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown('<div class="sec-title">⏱️ Carga en Horas-Hombre por mes</div>', unsafe_allow_html=True)
    colores_hh = [C["peach"] if i!=mes_idx else C["rosewood"] for i in range(12)]
    fig_hh = go.Figure()
    fig_hh.add_trace(go.Bar(x=MESES_ES, y=list(dem_h.values()), marker_color=colores_hh,
                            marker_line_color="white", marker_line_width=1.3,
                            hovertemplate="%{x}: %{y:.1f} H-H<extra></extra>", showlegend=False))
    fig_hh.add_trace(go.Scatter(x=MESES_ES, y=list(dem_h.values()), mode="lines+markers",
                                line=dict(color=C["rosewood"], width=2),
                                marker=dict(size=6), showlegend=False))
    fig_hh.update_layout(**PLOT_CFG, height=280, title="Carga agregada en horas-hombre",
                         xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]),
                         margin=dict(t=40, b=10))
    st.plotly_chart(fig_hh, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — PLAN AGREGADO: parámetros propios + optimización
# ══════════════════════════════════════════════════════════════════════════════
with tabs[1]:
    st.markdown('<div class="sec-title">📋 Configuración de Planeación Agregada</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Ajusta costos y estructura laboral. El modelo LP optimizará el plan anual en tiempo real con cada cambio.</div>', unsafe_allow_html=True)

    with st.expander("💰 Costos del modelo LP", expanded=True):
        ac1,ac2,ac3,ac4 = st.columns(4)
        ct  = ac1.number_input("Ct — Producción (COP/H-H)",    value=4_310,   step=100,  key="ct")
        ht  = ac2.number_input("Ht — Inventario (COP/H-H)",    value=100_000, step=1000, key="ht")
        pit = ac3.number_input("PIt — Diferimiento (COP/H-H)", value=100_000, step=1000, key="pit")
        stock_obj = ac4.slider("Stock seguridad (× dem.)", 0.0, 0.5, 0.0, 0.05, key="stock_obj")
        ac5,ac6,ac7,ac8 = st.columns(4)
        crt = ac5.number_input("CRt — Hora regular (COP/H-H)",     value=11_364, step=100, key="crt")
        cot = ac6.number_input("COt — Hora extra (COP/H-H)",        value=14_205, step=100, key="cot")
        cwp = ac7.number_input("CW+ — Contratar (COP/H-H cap.)",    value=14_204, step=100, key="cwp")
        cwm = ac8.number_input("CW− — Despedir (COP/H-H cap.)",     value=15_061, step=100, key="cwm")

    with st.expander("👷 Fuerza laboral y capacidad", expanded=True):
        lc1,lc2,lc3,lc4 = st.columns(4)
        trab        = lc1.number_input("Trabajadores iniciales", value=10,  step=1,  key="trab")
        turnos_dia  = lc2.number_input("Turnos por día",         value=1,   step=1,  key="turnos_dia")
        horas_turno = lc3.number_input("Horas por turno",        value=8,   step=1,  key="horas_turno")
        dias_mes    = lc4.number_input("Días hábiles del mes",   value=22,  step=1,  key="dias_mes")
        lc5,lc6,lc7 = st.columns(3)
        eficiencia   = lc5.slider("Rendimiento operativo (%)", 50, 110, 85, 1, key="eficiencia")
        ausentismo   = lc6.slider("Ausentismo (%)",              0,  20,  5, 1, key="ausentismo")
        flexibilidad = lc7.slider("Flexibilidad HH (%)",         0,  30, 10, 1, key="flexibilidad")

    # Cálculos derivados de capacidad
    factor_ef  = (eficiencia/100)*(1-ausentismo/100)*(1+flexibilidad/100)
    LR_inicial = trab * turnos_dia * horas_turno * dias_mes * factor_ef

    params_custom = {
        "Ct":ct,"Ht":ht,"PIt":pit,"CRt":crt,"COt":cot,
        "CW_mas":cwp,"CW_menos":cwm,"M":1,
        "LR_inicial":round(LR_inicial,2),"stock_obj":stock_obj,
    }

    # Necesitamos dem_h de la demanda — si MIX_FACTORS no está definido aún en este flujo,
    # lo recalculamos desde valores por defecto. En realidad tab[0] ya lo computó pero
    # Streamlit ejecuta todo en orden; usamos get con fallback seguro.
    _mix = {
        "Brownies":st.session_state.get("mix_br",1.0),
        "Mantecadas":st.session_state.get("mix_ma",1.0),
        "Mantecadas_Amapola":st.session_state.get("mix_am",1.0),
        "Torta_Naranja":st.session_state.get("mix_to",1.0),
        "Pan_Maiz":st.session_state.get("mix_pn",1.0),
    }
    _DEM_HIST = get_demanda_historica(_mix, factor_demanda)
    _dem_h    = demanda_horas_hombre(_DEM_HIST)

    with st.spinner("⚙️ Optimizando plan agregado..."):
        df_agr, costo = run_agregacion(
            tuple(_dem_h.items()),
            tuple(sorted(params_custom.items()))
        )

    st.markdown('<div class="sec-title">📊 Resultados de optimización LP</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="info-box"><b>{trab} trabajadores</b> · {turnos_dia} turno(s)/día · {horas_turno}h/turno · {dias_mes} días/mes · Eficiencia efectiva: <b>{factor_ef*100:.1f}%</b> → Capacidad: <b>{LR_inicial:,.0f} H-H/mes</b></div>', unsafe_allow_html=True)

    m1,m2,m3,m4 = st.columns(4)
    m1.metric("💰 Costo Total",    f"${costo/1e6:.2f}M COP")
    m2.metric("⏰ Horas Extra",     f"{df_agr['Horas_Extras'].sum():,.0f} H-H")
    m3.metric("📉 Backlog Total",   f"{df_agr['Backlog_HH'].sum():,.0f} H-H")
    m4.metric("👥 Contrat. Netas", f"{df_agr['Contratacion'].sum()-df_agr['Despidos'].sum():+.0f} H-H")

    fig_agr = go.Figure()
    fig_agr.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Inv_Ini_HH"], name="Inv. Inicial H-H",
                             marker_color=C["sky"], marker_line_color="white", marker_line_width=1))
    fig_agr.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Produccion_HH"], name="Producción H-H",
                             marker_color=C["peach"], marker_line_color="white", marker_line_width=1))
    fig_agr.add_trace(go.Scatter(x=df_agr["Mes_ES"], y=df_agr["Demanda_HH"], mode="lines+markers",
                                 name="Demanda H-H", line=dict(color=C["rosewood"], dash="dash", width=2.5),
                                 marker=dict(size=7, color=C["rosewood"])))
    fig_agr.add_trace(go.Scatter(x=df_agr["Mes_ES"], y=df_agr["Horas_Regulares"], mode="lines",
                                 name="Cap. Regular", line=dict(color=C["lavender"], dash="dot", width=2)))
    fig_agr.update_layout(**PLOT_CFG, barmode="stack", height=380,
                          title=f"Plan agregado — Costo óptimo LP: ${costo/1e6:.2f}M COP",
                          xaxis_title="Mes", yaxis_title="Horas-Hombre",
                          legend=dict(orientation="h", y=-0.23, x=0.5, xanchor="center"),
                          xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]))
    st.plotly_chart(fig_agr, use_container_width=True)

    c1_agr, c2_agr = st.columns(2)
    with c1_agr:
        st.markdown('<div class="sec-title">👷 Movimiento de personal</div>', unsafe_allow_html=True)
        fig_fl = go.Figure()
        fig_fl.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Contratacion"], name="Vinculación",
                                marker_color=C["mint"], marker_line_color="white", marker_line_width=1))
        fig_fl.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Despidos"], name="Salida",
                                marker_color=C["pink"], marker_line_color="white", marker_line_width=1))
        fig_fl.update_layout(**PLOT_CFG, barmode="group", height=290,
                             legend=dict(orientation="h", y=-0.28, x=0.5, xanchor="center"),
                             xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]))
        st.plotly_chart(fig_fl, use_container_width=True)

    with c2_agr:
        st.markdown('<div class="sec-title">⚡ Presión operativa</div>', unsafe_allow_html=True)
        fig_ex = go.Figure()
        fig_ex.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Horas_Extras"], name="Horas Extra",
                                marker_color=C["butter"], marker_line_color="white", marker_line_width=1))
        fig_ex.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Backlog_HH"], name="Backlog",
                                marker_color=C["salmon"], marker_line_color="white", marker_line_width=1))
        fig_ex.update_layout(**PLOT_CFG, barmode="group", height=290,
                             legend=dict(orientation="h", y=-0.28, x=0.5, xanchor="center"),
                             xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]))
        st.plotly_chart(fig_ex, use_container_width=True)

    with st.expander("📄 Tabla completa del plan"):
        df_show = df_agr.drop(columns=["Mes","Mes_ES"]).rename(columns={"Mes_F":"Mes"})
        st.dataframe(df_show.style.format({c:"{:,.1f}" for c in df_show.columns if c!="Mes"})
                     .background_gradient(subset=["Produccion_HH","Horas_Extras"], cmap="YlOrBr"),
                     use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — DESAGREGACIÓN: parámetros propios
# ══════════════════════════════════════════════════════════════════════════════
with tabs[2]:
    st.markdown('<div class="sec-title">📦 Parámetros de desagregación</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Ajusta cómo se distribuye el plan en unidades por producto. El suavizado penaliza cambios bruscos entre periodos.</div>', unsafe_allow_html=True)

    with st.expander("🔧 Parámetros avanzados de desagregación", expanded=True):
        da1, da2, da3 = st.columns(3)
        costo_pen_des = da1.number_input("Penalización backlog",    value=150_000, step=5000, key="cpen")
        costo_inv_des = da2.number_input("Costo inventario/und",    value=100_000, step=5000, key="cinv")
        suavizado_des = da3.slider("Suavizado de producción",        0, 5000, 500, 100, key="suav")

    mes_resaltar  = st.selectbox("★ Mes a resaltar", range(12), index=mes_idx,
                                  format_func=lambda i: MESES_F[i])
    mes_nm_desag  = MESES[mes_resaltar]

    # Desagregación depende de plan agregado calculado en tab 1
    # Usamos el prod_hh del plan calculado (df_agr ya fue computado arriba)
    prod_hh = dict(zip(df_agr["Mes"], df_agr["Produccion_HH"]))
    dem_hist_items = tuple((p, tuple(_DEM_HIST[p])) for p in PRODUCTOS)

    with st.spinner("🔢 Desagregando por producto..."):
        desag = run_desagregacion(
            tuple(prod_hh.items()), dem_hist_items,
            costo_pen_des, costo_inv_des, suavizado_des
        )

    # ── Gráfico combinado Producción + Inventario + Demanda ──────────────
    st.markdown('<div class="sec-title">📊 Vista combinada: Producción · Inventario · Demanda</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Vista consolidada de los tres flujos críticos del negocio mes a mes para el producto seleccionado.</div>', unsafe_allow_html=True)

    prod_sel_combo = st.selectbox("Producto a analizar", PRODUCTOS,
                                   format_func=lambda p: PROD_LABELS[p], key="combo_prod")
    df_combo = desag[prod_sel_combo]
    pc  = PROD_COLORS[prod_sel_combo]
    pcd = PROD_COLORS_DARK[prod_sel_combo]

    fig_combo = make_subplots(
        rows=2, cols=1, row_heights=[0.65, 0.35],
        shared_xaxes=True, vertical_spacing=0.08,
        subplot_titles=[f"Producción & Demanda — {PROD_LABELS[prod_sel_combo]}", "Inventario Final"],
    )
    fig_combo.add_trace(go.Bar(
        x=df_combo["Mes_ES"], y=df_combo["Produccion"], name="Producción",
        marker_color=pc, opacity=0.87,
        marker_line_color=pcd, marker_line_width=1.5,
        hovertemplate="%{x}: <b>%{y:.0f} und</b> producidas<extra></extra>",
    ), row=1, col=1)
    fig_combo.add_trace(go.Scatter(
        x=df_combo["Mes_ES"], y=df_combo["Demanda"], name="Demanda",
        mode="lines+markers",
        line=dict(color=pcd, width=2.5, dash="dash"),
        marker=dict(size=9, color=pc, line=dict(color=pcd, width=2)),
        hovertemplate="%{x}: <b>%{y:.0f} und</b> demanda<extra></extra>",
    ), row=1, col=1)
    # Fill entre producción y demanda
    fig_combo.add_trace(go.Scatter(
        x=df_combo["Mes_ES"], y=df_combo["Produccion"],
        fill=None, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip",
    ), row=1, col=1)
    fig_combo.add_trace(go.Scatter(
        x=df_combo["Mes_ES"], y=df_combo["Demanda"],
        fill="tonexty", fillcolor=hex_rgba(pc, 0.18),
        mode="lines", line=dict(width=0), name="Brecha", showlegend=True, hoverinfo="skip",
    ), row=1, col=1)
    # Estrella mes resaltado
    mes_row_c = df_combo[df_combo["Mes"]==mes_nm_desag]
    if not mes_row_c.empty:
        fig_combo.add_trace(go.Scatter(
            x=[MESES_ES[mes_resaltar]], y=[mes_row_c["Produccion"].values[0]],
            mode="markers",
            marker=dict(size=16, color=C["gold"], symbol="star", line=dict(color=pcd, width=2)),
            name=f"★ {MESES_F[mes_resaltar]}", showlegend=True,
        ), row=1, col=1)
    # Inventario
    fig_combo.add_trace(go.Scatter(
        x=df_combo["Mes_ES"], y=df_combo["Inv_Fin"],
        fill="tozeroy", mode="lines+markers",
        fillcolor=hex_rgba(C["mint"], 0.35),
        line=dict(color="#6FA889", width=2),
        marker=dict(size=7, color="#6FA889"),
        name="Inventario Final",
        hovertemplate="%{x}: %{y:.0f} und en inventario<extra></extra>",
    ), row=2, col=1)
    if df_combo["Backlog"].sum() > 0:
        fig_combo.add_trace(go.Bar(
            x=df_combo["Mes_ES"], y=df_combo["Backlog"],
            name="Backlog", marker_color=C["pink"], opacity=0.8,
        ), row=2, col=1)
    fig_combo.update_layout(**PLOT_CFG, height=500, barmode="group",
                            legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center"),
                            margin=dict(t=60, b=20))
    fig_combo.update_xaxes(showgrid=False)
    fig_combo.update_yaxes(gridcolor=C["line"], row=1, col=1)
    fig_combo.update_yaxes(gridcolor=C["line"], row=2, col=1)
    st.plotly_chart(fig_combo, use_container_width=True)

    # ── Subgráficas por producto ──────────────────────────────────────────
    st.markdown('<div class="sec-title">📐 Plan desagregado — Todos los productos</div>', unsafe_allow_html=True)
    fig_des = make_subplots(rows=3, cols=2,
                            subplot_titles=[PROD_LABELS[p] for p in PRODUCTOS],
                            vertical_spacing=0.12, horizontal_spacing=0.08)
    for idx, p in enumerate(PRODUCTOS):
        r, c = idx//2+1, idx%2+1
        df_p = desag[p]
        fig_des.add_trace(go.Bar(x=df_p["Mes_ES"], y=df_p["Produccion"],
                                 marker_color=PROD_COLORS[p], opacity=0.88,
                                 showlegend=False, marker_line_color="white", marker_line_width=1),
                          row=r, col=c)
        fig_des.add_trace(go.Scatter(x=df_p["Mes_ES"], y=df_p["Demanda"], mode="lines+markers",
                                     line=dict(color=PROD_COLORS_DARK[p], dash="dash", width=1.5),
                                     marker=dict(size=5), showlegend=False), row=r, col=c)
        mes_row = df_p[df_p["Mes"]==mes_nm_desag]
        if not mes_row.empty:
            fig_des.add_trace(go.Scatter(
                x=[MESES_ES[mes_resaltar]], y=[mes_row["Produccion"].values[0]],
                mode="markers", marker=dict(size=13, color=C["gold"], symbol="star"),
                showlegend=False), row=r, col=c)
    fig_des.update_layout(**PLOT_CFG, height=700, barmode="group", margin=dict(t=60))
    for i in range(1,4):
        for j in range(1,3):
            fig_des.update_xaxes(showgrid=False, row=i, col=j)
            fig_des.update_yaxes(gridcolor=C["line"], row=i, col=j)
    st.plotly_chart(fig_des, use_container_width=True)

    # ── Cobertura ──────────────────────────────────────────────────────────
    st.markdown('<div class="sec-title">🎯 Cobertura de demanda anual</div>', unsafe_allow_html=True)
    prods_c, cob_vals, und_prod, und_dem = [], [], [], []
    for p in PRODUCTOS:
        df_p = desag[p]
        tot_p = df_p["Produccion"].sum(); tot_d = df_p["Demanda"].sum()
        cob = round(min(tot_p/max(tot_d,1)*100, 100), 1)
        prods_c.append(PROD_LABELS[p]); cob_vals.append(cob)
        und_prod.append(int(tot_p)); und_dem.append(int(tot_d))

    col_cob1, col_cob2 = st.columns([2,1])
    with col_cob1:
        fig_cob = go.Figure(go.Bar(
            y=prods_c, x=cob_vals, orientation="h",
            marker=dict(color=list(PROD_COLORS.values()),
                        line=dict(color=list(PROD_COLORS_DARK.values()), width=1.5)),
            text=[f"{v:.1f}%" for v in cob_vals], textposition="inside",
            textfont=dict(color=C["text"], size=12),
        ))
        fig_cob.add_vline(x=100, line_dash="dash", line_color=C["rosewood"],
                          annotation_text="Meta 100%", annotation_font_color=C["rosewood"])
        fig_cob.update_layout(**PLOT_CFG, height=280, xaxis_title="Cobertura (%)",
                              xaxis=dict(range=[0,115], gridcolor=C["line"]),
                              yaxis=dict(showgrid=False), margin=dict(t=20,b=20), showlegend=False)
        st.plotly_chart(fig_cob, use_container_width=True)
    with col_cob2:
        df_cob = pd.DataFrame({"Producto":prods_c,"Producido":und_prod,"Demanda":und_dem,"Cob %":cob_vals})
        st.dataframe(df_cob.style.format({"Producido":"{:,.0f}","Demanda":"{:,.0f}","Cob %":"{:.1f}%"})
                     .background_gradient(subset=["Cob %"], cmap="YlGn"),
                     use_container_width=True, height=280)

    # ── Inventario final ────────────────────────────────────────────────────
    st.markdown('<div class="sec-title">📦 Inventario final proyectado — todos los productos</div>', unsafe_allow_html=True)
    fig_inv = go.Figure()
    for p in PRODUCTOS:
        fig_inv.add_trace(go.Scatter(
            x=desag[p]["Mes_ES"], y=desag[p]["Inv_Fin"], name=PROD_LABELS[p],
            mode="lines+markers",
            line=dict(color=PROD_COLORS_DARK[p], width=2),
            marker=dict(size=7, color=PROD_COLORS[p], line=dict(color=PROD_COLORS_DARK[p], width=1.5)),
            fill="tozeroy", fillcolor=hex_rgba(PROD_COLORS[p], 0.16),
        ))
    fig_inv.update_layout(**PLOT_CFG, height=290, title="Trayectoria de inventario final",
                          xaxis_title="Mes", yaxis_title="Unidades",
                          legend=dict(orientation="h", y=-0.28, x=0.5, xanchor="center"),
                          xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]))
    st.plotly_chart(fig_inv, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — SIMULACIÓN: parámetros propios de planta
# ══════════════════════════════════════════════════════════════════════════════
with tabs[3]:
    mes_nm = MESES[mes_idx]
    # plan_mes depende del desag — si desag no está listo en este punto del flujo
    # lo recalculamos de manera segura
    _prod_hh_sim = dict(zip(df_agr["Mes"], df_agr["Produccion_HH"]))
    with st.spinner("Preparando plan del mes..."):
        _desag_sim = run_desagregacion(
            tuple(_prod_hh_sim.items()), dem_hist_items,
            st.session_state.get("cpen", 150_000),
            st.session_state.get("cinv", 100_000),
            st.session_state.get("suav", 500),
        )
    plan_mes = {p: int(_desag_sim[p].loc[_desag_sim[p]["Mes"]==mes_nm, "Produccion"].values[0])
                for p in PRODUCTOS}

    st.markdown(f'<div class="sec-title">🏭 Configuración de planta — {MESES_F[mes_idx]}</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Parámetros operativos de la planta. Cada cambio redispara la simulación de eventos discretos.</div>', unsafe_allow_html=True)

    with st.expander("🏗️ Capacidades por recurso", expanded=True):
        s1,s2,s3,s4,s5,s6 = st.columns(6)
        mezcla_cap      = s1.number_input("🥣 Mezcla",        value=2, step=1, min_value=1, key="mezcla_cap")
        dosificado_cap  = s2.number_input("🔧 Dosificado",    value=2, step=1, min_value=1, key="dosif_cap")
        cap_horno       = s3.number_input("🔥 Horno",         value=3, step=1, min_value=1, key="cap_horno")
        enfriamiento_cap= s4.number_input("❄️ Enfriamiento",  value=4, step=1, min_value=1, key="enfr_cap")
        empaque_cap     = s5.number_input("📦 Empaque",       value=2, step=1, min_value=1, key="empa_cap")
        amasado_cap     = s6.number_input("👐 Amasado",       value=1, step=1, min_value=1, key="amas_cap")

    with st.expander("🎛️ Comportamiento de la simulación", expanded=True):
        ss1,ss2,ss3,ss4 = st.columns(4)
        falla_horno  = ss1.checkbox("⚠️ Fallas en horno", value=False, key="falla_horno")
        doble_turno  = ss2.checkbox("🕐 Ritmo extendido (−20% tiempo)", value=False, key="doble_turno")
        variabilidad = ss3.slider("📉 Variabilidad tiempos",  0.5, 2.0, 1.0, 0.1, key="variab")
        espaciamiento= ss4.slider("📏 Espaciamiento de lotes",0.5, 2.0, 1.0, 0.1, key="espac")
        ss5,ss6 = st.columns(2)
        iter_sim        = ss5.slider("🔁 Iteraciones a promediar", 1, 5, 1, key="iter_sim")
        temp_horno_base = ss6.slider("🌡️ Temperatura base horno (°C)", 130, 190, 160, key="temp_horno")

    cap_rec   = {"mezcla":mezcla_cap,"dosificado":dosificado_cap,"horno":cap_horno,
                 "enfriamiento":enfriamiento_cap,"empaque":empaque_cap,"amasado":amasado_cap}
    factor_t  = 0.80 if doble_turno else 1.0

    # Acumular iteraciones
    lotes_runs, uso_runs, sens_runs = [], [], []
    with st.spinner("🏭 Simulando planta de producción..."):
        for it in range(iter_sim):
            df_l, df_u, df_s = run_simulacion_cached(
                tuple(plan_mes.items()), tuple(cap_rec.items()),
                falla_horno, factor_t, variabilidad, espaciamiento,
                int(semilla)+it, temp_horno_base,
            )
            if not df_l.empty: df_l["it"]=it+1; lotes_runs.append(df_l)
            if not df_u.empty: df_u["it"]=it+1; uso_runs.append(df_u)
            if not df_s.empty: df_s["it"]=it+1; sens_runs.append(df_s)

    df_lotes    = pd.concat(lotes_runs, ignore_index=True) if lotes_runs else pd.DataFrame()
    df_uso      = pd.concat(uso_runs,   ignore_index=True) if uso_runs   else pd.DataFrame()
    df_sensores = pd.concat(sens_runs,  ignore_index=True) if sens_runs  else pd.DataFrame()
    df_kpis     = calc_kpis(df_lotes, plan_mes)
    df_util     = calc_utilizacion(df_uso)

    # Plan del mes
    st.markdown('<div class="sec-title">🗓️ Plan del mes en unidades</div>', unsafe_allow_html=True)
    cols_p = st.columns(5)
    for i, (p, u) in enumerate(plan_mes.items()):
        hh_req = round(u*HORAS_PRODUCTO[p], 1)
        lit    = round(u*LITROS_UNIDAD_BASE[p], 1)
        cols_p[i].markdown(f"""
        <div class="kpi-card" style="background:{hex_rgba(PROD_COLORS[p],0.3)};border-color:{PROD_COLORS_DARK[p]}">
          <div class="icon">{EMOJIS[p]}</div>
          <div class="val" style="font-size:1.4rem">{u:,}</div>
          <div class="lbl">{PROD_LABELS[p]}</div>
          <div class="sub">{hh_req} H-H · {lit}L</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if not df_kpis.empty:
        st.markdown('<div class="sec-title">✅ Cumplimiento del plan</div>', unsafe_allow_html=True)
        fig_cum = go.Figure()
        for i, row in df_kpis.iterrows():
            p_key = next((p for p in PRODUCTOS if PROD_LABELS[p]==row["Producto"]), PRODUCTOS[i%len(PRODUCTOS)])
            fig_cum.add_trace(go.Bar(
                x=[row["Cumplimiento %"]], y=[row["Producto"]], orientation="h",
                marker=dict(color=PROD_COLORS[p_key], line=dict(color=PROD_COLORS_DARK[p_key], width=1.5)),
                text=f"{row['Cumplimiento %']:.1f}%", textposition="inside",
                textfont=dict(color=C["text"], size=12), showlegend=False,
            ))
        fig_cum.add_vline(x=100, line_dash="dash", line_color=C["rosewood"])
        fig_cum.update_layout(**PLOT_CFG, height=265,
                              title="Cumplimiento del plan por producto",
                              xaxis=dict(range=[0,115], gridcolor=C["line"]),
                              yaxis=dict(showgrid=False), margin=dict(t=40, b=10))
        st.plotly_chart(fig_cum, use_container_width=True)

        t1, t2 = st.columns(2)
        prods_kpi = list(df_kpis["Producto"].values)
        colores_kpi = [PROD_COLORS[next((p for p in PRODUCTOS if PROD_LABELS[p]==prod), PRODUCTOS[0])]
                       for prod in prods_kpi]
        with t1:
            fig_tp = go.Figure(go.Bar(
                x=prods_kpi, y=df_kpis["Throughput (und/h)"].values,
                marker_color=colores_kpi, marker_line_color="white", marker_line_width=2,
                text=[f"{v:.1f}" for v in df_kpis["Throughput (und/h)"].values], textposition="outside",
            ))
            fig_tp.update_layout(**PLOT_CFG, height=285, title="Flujo por referencia (und/h)",
                                 xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]), showlegend=False)
            st.plotly_chart(fig_tp, use_container_width=True)
        with t2:
            fig_lt = go.Figure(go.Bar(
                x=prods_kpi, y=df_kpis["Lead Time (min/lote)"].values,
                marker_color=[PROD_COLORS_DARK[next((p for p in PRODUCTOS if PROD_LABELS[p]==prod), PRODUCTOS[0])]
                              for prod in prods_kpi],
                marker_line_color="white", marker_line_width=2,
                text=[f"{v:.0f}" for v in df_kpis["Lead Time (min/lote)"].values], textposition="outside",
            ))
            fig_lt.update_layout(**PLOT_CFG, height=285, title="Tiempo de lote (min/lote)",
                                 xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]), showlegend=False)
            st.plotly_chart(fig_lt, use_container_width=True)

    if not df_util.empty:
        st.markdown('<div class="sec-title">⚙️ Saturación de recursos</div>', unsafe_allow_html=True)
        cuellos = df_util[df_util["Cuello Botella"]]
        if not cuellos.empty:
            for _, row in cuellos.iterrows():
                st.markdown(f'<div class="pill-warn">⚠️ {REC_LABELS.get(row["Recurso"],row["Recurso"])} — {row["Utilizacion_%"]:.1f}% · Cola prom: {row["Cola Prom"]:.2f}</div><br>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="pill-ok">✅ Sin cuellos de botella críticos</div><br>', unsafe_allow_html=True)

        rec_lb   = [REC_LABELS.get(r,r) for r in df_util["Recurso"]]
        col_util = [C["pink"] if u>=80 else C["butter"] if u>=60 else C["mint"] for u in df_util["Utilizacion_%"]]
        fig_ug = make_subplots(rows=1, cols=2, subplot_titles=["Carga del recurso (%)","Cola promedio"])
        fig_ug.add_trace(go.Bar(x=rec_lb, y=df_util["Utilizacion_%"], marker_color=col_util,
                                text=[f"{v:.0f}%" for v in df_util["Utilizacion_%"]], textposition="outside",
                                showlegend=False), row=1, col=1)
        fig_ug.add_trace(go.Bar(x=rec_lb, y=df_util["Cola Prom"], marker_color=C["lavender"],
                                text=[f"{v:.2f}" for v in df_util["Cola Prom"]], textposition="outside",
                                showlegend=False), row=1, col=2)
        fig_ug.add_hline(y=80, line_dash="dash", line_color=C["rosewood"], row=1, col=1)
        fig_ug.update_layout(**PLOT_CFG, height=320)
        fig_ug.update_xaxes(showgrid=False)
        fig_ug.update_yaxes(gridcolor=C["line"])
        st.plotly_chart(fig_ug, use_container_width=True)

    if not df_lotes.empty:
        st.markdown('<div class="sec-title">📅 Diagrama de Gantt — Flujo de lotes</div>', unsafe_allow_html=True)
        n_gantt = min(60, len(df_lotes))
        sub = df_lotes.head(n_gantt).reset_index(drop=True)
        fig_gantt = go.Figure()
        for _, row in sub.iterrows():
            fig_gantt.add_trace(go.Bar(
                x=[row["tiempo_sistema"]], y=[row["lote_id"]], base=[row["t_creacion"]],
                orientation="h", marker_color=PROD_COLORS.get(row["producto"],"#ccc"),
                opacity=0.87, showlegend=False,
                marker_line_color="white", marker_line_width=0.5,
                hovertemplate=(f"<b>{PROD_LABELS.get(row['producto'],row['producto'])}</b><br>"
                               f"Inicio: {row['t_creacion']:.0f} min<br>"
                               f"Duración: {row['tiempo_sistema']:.1f} min<extra></extra>"),
            ))
        for p, c in PROD_COLORS.items():
            fig_gantt.add_trace(go.Bar(x=[None], y=[None], marker_color=c, name=PROD_LABELS[p]))
        fig_gantt.update_layout(**PLOT_CFG, barmode="overlay",
                                height=max(380, n_gantt*8),
                                title=f"Gantt — Primeros {n_gantt} lotes",
                                xaxis_title="Tiempo simulado (min)",
                                legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"),
                                yaxis=dict(showticklabels=False))
        st.plotly_chart(fig_gantt, use_container_width=True)

        st.markdown('<div class="sec-title">🎻 Distribución de tiempos en sistema</div>', unsafe_allow_html=True)
        fig_violin = go.Figure()
        for p in PRODUCTOS:
            sub_v = df_lotes[df_lotes["producto"]==p]["tiempo_sistema"]
            if len(sub_v) < 3: continue
            fig_violin.add_trace(go.Violin(
                y=sub_v, name=PROD_LABELS[p], box_visible=True, meanline_visible=True,
                fillcolor=PROD_COLORS[p], line_color=PROD_COLORS_DARK[p], opacity=0.82,
            ))
        fig_violin.update_layout(**PLOT_CFG, height=310,
                                 yaxis_title="Tiempo en sistema (min)",
                                 showlegend=False, violinmode="overlay")
        st.plotly_chart(fig_violin, use_container_width=True)

        with st.expander("📊 Tabla completa de KPIs"):
            if not df_kpis.empty:
                st.dataframe(df_kpis.style.format({c:"{:,.2f}" for c in df_kpis.columns if c!="Producto"})
                             .background_gradient(subset=["Cumplimiento %"], cmap="YlGn"),
                             use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — SENSORES
# ══════════════════════════════════════════════════════════════════════════════
with tabs[4]:
    st.markdown('<div class="sec-title">🌡️ Sensores Virtuales — Monitor del Horno</div>', unsafe_allow_html=True)
    cap_horno_s = st.session_state.get("cap_horno", 3)
    temp_base_s = st.session_state.get("temp_horno", 160)
    st.markdown(f'<div class="info-box">Gemelo digital IoT · Temperatura base: {temp_base_s}°C · Capacidad del horno: {cap_horno_s} estaciones · Límite operativo: 200°C</div>', unsafe_allow_html=True)

    # df_sensores proviene del bloque de simulación (tab 4) calculado arriba
    if not df_sensores.empty:
        excesos_s = int((df_sensores["temperatura"]>200).sum())
        temp_avg_s = df_sensores["temperatura"].mean()

        s1,s2,s3,s4 = st.columns(4)
        s1.metric("🌡️ Temp. mínima",   f"{df_sensores['temperatura'].min():.1f} °C")
        s2.metric("🔥 Temp. máxima",   f"{df_sensores['temperatura'].max():.1f} °C")
        s3.metric("📊 Temp. promedio", f"{temp_avg_s:.1f} °C")
        s4.metric("⚠️ Excesos >200°C", excesos_s,
                  delta="Revisar horno" if excesos_s else "Operación normal",
                  delta_color="inverse" if excesos_s else "off")

        fig_temp = go.Figure()
        fig_temp.add_hrect(y0=150, y1=200, fillcolor=hex_rgba(C["mint"],0.21), line_width=0,
                           annotation_text="Zona operativa óptima", annotation_font_color=C["sage"])
        fig_temp.add_trace(go.Scatter(
            x=df_sensores["tiempo"], y=df_sensores["temperatura"],
            mode="lines", name="Temperatura",
            fill="tozeroy", fillcolor=hex_rgba(C["salmon"],0.14),
            line=dict(color=C["rosewood"], width=1.8),
        ))
        if len(df_sensores)>10:
            mm = df_sensores["temperatura"].rolling(5, min_periods=1).mean()
            fig_temp.add_trace(go.Scatter(
                x=df_sensores["tiempo"], y=mm, mode="lines", name="Media móvil",
                line=dict(color=C["lavender"], width=2, dash="dot"),
            ))
        fig_temp.add_hline(y=200, line_dash="dash", line_color="#C0392B",
                           annotation_text="⚠ Límite 200°C", annotation_font_color="#C0392B")
        fig_temp.update_layout(**PLOT_CFG, height=320,
                               title="Señal térmica del horno — Monitoreo simulado",
                               xaxis_title="Tiempo simulado (min)", yaxis_title="°C",
                               legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center"),
                               xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]))
        st.plotly_chart(fig_temp, use_container_width=True)

        sx1, sx2 = st.columns(2)
        with sx1:
            fig_ocup = go.Figure()
            fig_ocup.add_trace(go.Scatter(
                x=df_sensores["tiempo"], y=df_sensores["horno_ocup"],
                mode="lines", fill="tozeroy", fillcolor=hex_rgba(C["sky"],0.25),
                line=dict(color=PROD_COLORS_DARK["Mantecadas"], width=2),
            ))
            fig_ocup.add_hline(y=cap_horno_s, line_dash="dot", line_color=C["rosewood"],
                               annotation_text=f"Cap. máx: {cap_horno_s}")
            fig_ocup.update_layout(**PLOT_CFG, height=265, title="Ocupación del horno",
                                   xaxis_title="Tiempo (min)", yaxis_title="Estaciones activas",
                                   showlegend=False, xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]))
            st.plotly_chart(fig_ocup, use_container_width=True)
        with sx2:
            fig_hist_t = go.Figure(go.Histogram(
                x=df_sensores["temperatura"], nbinsx=35,
                marker_color=C["peach"], marker_line_color="white", marker_line_width=1,
            ))
            fig_hist_t.add_vline(x=200, line_dash="dash", line_color="#C0392B")
            fig_hist_t.add_vline(x=temp_avg_s, line_dash="dot", line_color=C["rosewood"],
                                 annotation_text=f"Prom:{temp_avg_s:.0f}°C",
                                 annotation_font_color=C["rosewood"])
            fig_hist_t.update_layout(**PLOT_CFG, height=265, title="Distribución térmica",
                                     xaxis_title="°C", yaxis_title="Frecuencia", showlegend=False,
                                     xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]))
            st.plotly_chart(fig_hist_t, use_container_width=True)
    else:
        st.info("Sin datos de sensores. Ajusta los parámetros en la pestaña Simulación y vuelve aquí.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — ESCENARIOS
# ══════════════════════════════════════════════════════════════════════════════
with tabs[5]:
    st.markdown('<div class="sec-title">🔬 Análisis de Escenarios What-If</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Compara múltiples configuraciones de planta para identificar la estrategia óptima. Cada escenario simula condiciones distintas de demanda, capacidad y operación.</div>', unsafe_allow_html=True)

    ESCENARIOS_DEF = {
        "Base":                   {"fd":1.0, "falla":False, "ft":1.0,  "cap_delta":0,  "var":1.0},
        "Impulso comercial +20%": {"fd":1.2, "falla":False, "ft":1.0,  "cap_delta":0,  "var":1.0},
        "Contracción −20%":       {"fd":0.8, "falla":False, "ft":1.0,  "cap_delta":0,  "var":1.0},
        "Horno inestable":        {"fd":1.0, "falla":True,  "ft":1.0,  "cap_delta":0,  "var":1.5},
        "Restricción capacidad":  {"fd":1.0, "falla":False, "ft":1.0,  "cap_delta":-1, "var":1.0},
        "Capacidad ampliada":     {"fd":1.0, "falla":False, "ft":1.0,  "cap_delta":+1, "var":1.0},
        "Ritmo extendido":        {"fd":1.0, "falla":False, "ft":0.80, "cap_delta":0,  "var":1.0},
        "Modo optimizado":        {"fd":1.0, "falla":False, "ft":0.85, "cap_delta":+1, "var":0.9},
    }
    ESC_ICONS = {
        "Base":"🏠","Impulso comercial +20%":"📈","Contracción −20%":"📉",
        "Horno inestable":"⚠️","Restricción capacidad":"⬇️","Capacidad ampliada":"⬆️",
        "Ritmo extendido":"🕐","Modo optimizado":"🚀",
    }

    escenarios_sel = st.multiselect(
        "Selecciona escenarios a comparar",
        list(ESCENARIOS_DEF.keys()),
        default=["Base","Impulso comercial +20%","Horno inestable","Ritmo extendido","Modo optimizado"],
    )

    # parámetros de capacidad heredados de simulación
    _cap_horno_esc   = st.session_state.get("cap_horno", 3)
    _variab_esc      = st.session_state.get("variab", 1.0)
    _espac_esc       = st.session_state.get("espac", 1.0)
    _temp_horno_esc  = st.session_state.get("temp_horno", 160)
    cap_rec_esc = {
        "mezcla":       st.session_state.get("mezcla_cap", 2),
        "dosificado":   st.session_state.get("dosif_cap",  2),
        "horno":        _cap_horno_esc,
        "enfriamiento": st.session_state.get("enfr_cap",   4),
        "empaque":      st.session_state.get("empa_cap",   2),
        "amasado":      st.session_state.get("amas_cap",   1),
    }

    if st.button("🚀 Comparar escenarios seleccionados", type="primary"):
        filas_esc = []
        prog = st.progress(0)
        for i, nm in enumerate(escenarios_sel):
            prog.progress((i+1)/len(escenarios_sel), text=f"Simulando: {nm}...")
            cfg = ESCENARIOS_DEF[nm]
            plan_esc = {p: max(int(u*cfg["fd"]), 0) for p, u in plan_mes.items()}
            cap_esc  = {**cap_rec_esc, "horno": max(_cap_horno_esc+cfg["cap_delta"], 1)}
            df_l, df_u, _ = run_simulacion_cached(
                tuple(plan_esc.items()), tuple(cap_esc.items()),
                cfg["falla"], cfg["ft"], cfg["var"], _espac_esc,
                int(semilla)+i+100, _temp_horno_esc,
            )
            k = calc_kpis(df_l, plan_esc)
            u = calc_utilizacion(df_u)
            fila = {"Escenario": ESC_ICONS.get(nm,"")+" "+nm}
            if not k.empty:
                fila["Throughput (und/h)"] = round(k["Throughput (und/h)"].mean(), 2)
                fila["Lead Time (min)"]    = round(k["Lead Time (min/lote)"].mean(), 2)
                fila["WIP Prom"]           = round(k["WIP Prom"].mean(), 2)
                fila["Cumplimiento %"]     = round(k["Cumplimiento %"].mean(), 2)
            if not u.empty:
                fila["Util. max %"]     = round(u["Utilizacion_%"].max(), 2)
                fila["Cuellos botella"] = int(u["Cuello Botella"].sum())
            fila["Lotes prod."] = len(df_l)
            filas_esc.append(fila)
        prog.empty()
        df_comp = pd.DataFrame(filas_esc)

        st.markdown('<div class="sec-title">📊 Resultados comparativos</div>', unsafe_allow_html=True)
        num_cols = [c for c in df_comp.columns if c!="Escenario" and df_comp[c].dtype!="object"]
        st.dataframe(df_comp.style.format({c:"{:,.2f}" for c in num_cols})
                     .background_gradient(subset=["Cumplimiento %"] if "Cumplimiento %" in df_comp.columns else [],
                                          cmap="YlGn"),
                     use_container_width=True)

        if len(df_comp) > 1:
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                if "Cumplimiento %" in df_comp.columns:
                    col_c = [C["mint"] if v>=90 else C["butter"] if v>=70 else C["pink"]
                             for v in df_comp["Cumplimiento %"]]
                    fig_ec = go.Figure(go.Bar(
                        x=df_comp["Escenario"], y=df_comp["Cumplimiento %"],
                        marker_color=col_c, marker_line_color="white", marker_line_width=2,
                        text=[f"{v:.1f}%" for v in df_comp["Cumplimiento %"]], textposition="outside",
                    ))
                    fig_ec.add_hline(y=100, line_dash="dash", line_color=C["rosewood"])
                    fig_ec.update_layout(**PLOT_CFG, height=310, title="Cumplimiento por escenario",
                                         xaxis=dict(showgrid=False, tickangle=-25),
                                         yaxis=dict(gridcolor=C["line"]), showlegend=False,
                                         margin=dict(t=40, b=90))
                    st.plotly_chart(fig_ec, use_container_width=True)
            with col_e2:
                if "Util. max %" in df_comp.columns:
                    col_u = [C["pink"] if v>=80 else C["butter"] if v>=60 else C["mint"]
                             for v in df_comp["Util. max %"]]
                    fig_eu = go.Figure(go.Bar(
                        x=df_comp["Escenario"], y=df_comp["Util. max %"],
                        marker_color=col_u, marker_line_color="white", marker_line_width=2,
                        text=[f"{v:.0f}%" for v in df_comp["Util. max %"]], textposition="outside",
                    ))
                    fig_eu.add_hline(y=80, line_dash="dash", line_color=C["rosewood"],
                                     annotation_text="⚠ 80%")
                    fig_eu.update_layout(**PLOT_CFG, height=310, title="Utilización máxima",
                                         xaxis=dict(showgrid=False, tickangle=-25),
                                         yaxis=dict(gridcolor=C["line"]), showlegend=False,
                                         margin=dict(t=40, b=90))
                    st.plotly_chart(fig_eu, use_container_width=True)

            # Radar comparativo
            cols_radar = [c for c in df_comp.columns
                          if c not in ["Escenario","Cuellos botella"] and df_comp[c].dtype!="object"]
            if len(cols_radar) >= 3:
                df_norm = df_comp[cols_radar].copy()
                for c in df_norm.columns:
                    rng = df_norm[c].max()-df_norm[c].min()
                    df_norm[c] = (df_norm[c]-df_norm[c].min())/rng if rng else 0.5
                radar_colors = [C["peach"],C["sky"],C["pink"],C["mint"],
                                C["lavender"],C["salmon"],C["butter"],C["sage"]]
                rgba_r = [hex_rgba(x, 0.15) for x in radar_colors]
                fig_radar = go.Figure()
                for i, row in df_comp.iterrows():
                    vals = [df_norm.loc[i,c] for c in cols_radar]
                    fig_radar.add_trace(go.Scatterpolar(
                        r=vals+[vals[0]], theta=cols_radar+[cols_radar[0]],
                        fill="toself", name=row["Escenario"],
                        line=dict(color=radar_colors[i%len(radar_colors)], width=2),
                        fillcolor=rgba_r[i%len(rgba_r)],
                    ))
                fig_radar.update_layout(
                    **PLOT_CFG, height=450, title="Perfil normalizado de escenarios",
                    polar=dict(
                        radialaxis=dict(visible=True, range=[0,1], gridcolor=C["line"], linecolor=C["line"]),
                        angularaxis=dict(gridcolor=C["line"]),
                    ),
                    legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"),
                )
                st.plotly_chart(fig_radar, use_container_width=True)

            # Score ranking
            if {"Cumplimiento %","Lead Time (min)","Util. max %","Cuellos botella"}.issubset(df_comp.columns):
                df_rank = df_comp.copy()
                df_rank["Score"] = (
                    df_rank["Cumplimiento %"]*0.45
                    + (100-df_rank["Util. max %"].clip(upper=100))*0.20
                    + (100-df_rank["Lead Time (min)"].rank(pct=True)*100)*0.20
                    + (100-df_rank["Cuellos botella"].rank(pct=True)*100)*0.15
                )
                df_rank = df_rank.sort_values("Score", ascending=False).reset_index(drop=True)
                cols_score = [C["mint"],C["sky"],C["lavender"],C["peach"],
                              C["pink"],C["salmon"],C["butter"],C["sage"]]
                fig_rank = go.Figure(go.Bar(
                    x=df_rank["Score"], y=df_rank["Escenario"], orientation="h",
                    marker=dict(color=cols_score[:len(df_rank)], line=dict(color="white", width=2)),
                    text=[f"{v:.1f}" for v in df_rank["Score"]], textposition="outside",
                ))
                fig_rank.update_layout(**PLOT_CFG, height=340,
                                       title="🏆 Ranking integrado de escenarios (score compuesto)",
                                       xaxis_title="Score compuesto",
                                       yaxis=dict(autorange="reversed", showgrid=False),
                                       xaxis=dict(gridcolor=C["line"]), showlegend=False)
                st.plotly_chart(fig_rank, use_container_width=True)
    else:
        st.markdown("""
        <div class="info-box" style="text-align:center;padding:2rem;">
          <div style="font-size:2.5rem">🔬</div>
          <b>Selecciona escenarios y haz clic en Comparar</b><br>
          <span style="font-size:0.86rem;color:#8C7B70;">
            Se simulará cada configuración y se compararán KPIs lado a lado con radar y ranking.</span>
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# RELLENAR HERO & KPIs — con todos los datos ya calculados
# Los st.empty() placeholders definidos antes de los tabs se rellenan aquí.
# Streamlit procesa el script completo antes de renderizar, así que los
# placeholders aparecerán en su posición original (arriba de los tabs)
# pero con los valores finales calculados en esta pasada.
# ══════════════════════════════════════════════════════════════════════════════
prod_total  = sum(_desag_sim[p]["Produccion"].sum() for p in PRODUCTOS)
litros_total= round(prod_total * litros_por_unidad, 1)
cum_avg_g   = df_kpis["Cumplimiento %"].mean() if not df_kpis.empty else 0
util_max_g  = df_util["Utilizacion_%"].max()   if not df_util.empty else 0
temp_avg_g  = df_sensores["temperatura"].mean() if not df_sensores.empty else 0
excesos_g   = int((df_sensores["temperatura"]>200).sum()) if not df_sensores.empty else 0
falla_act   = st.session_state.get("falla_horno", False)
doble_act   = st.session_state.get("doble_turno", False)

hero_placeholder.markdown(f"""
<div class="hero">
  <h1>Gemelo Digital — Panadería Dora del Hoyo</h1>
  <p>Optimización LP · Simulación de Eventos Discretos · Análisis What-If en tiempo real</p>
  <span class="badge">📅 {MESES_F[mes_idx]}</span>
  <span class="badge">📈 Demanda ×{factor_demanda}</span>
  <span class="badge">🛒 Cobertura {participacion_mercado}%</span>
  <span class="badge">🧁 {litros_total:,.0f} L proyectados</span>
  <span class="badge">👩‍🍳 {trab} operarios/turno</span>
  {"<span class='badge'>⚠️ Falla activa</span>" if falla_act else ""}
  {"<span class='badge'>🕐 Doble turno</span>" if doble_act else ""}
</div>
""", unsafe_allow_html=True)

kpi_placeholder.markdown(f"""
<div style="display:flex;gap:0.6rem;margin-bottom:0.5rem;flex-wrap:wrap;">
  <div class="kpi-card" style="flex:1;min-width:120px;">
    <div class="icon">💰</div>
    <div class="val">${costo/1e6:.1f}M</div>
    <div class="lbl">Costo Óptimo</div>
    <div class="sub">COP · Plan anual</div>
  </div>
  <div class="kpi-card" style="flex:1;min-width:120px;">
    <div class="icon">🧁</div>
    <div class="val">{litros_total:,.0f}L</div>
    <div class="lbl">Volumen Anual</div>
    <div class="sub">×{litros_por_unidad} L/und</div>
  </div>
  <div class="kpi-card" style="flex:1;min-width:120px;">
    <div class="icon">🛒</div>
    <div class="val">{participacion_mercado}%</div>
    <div class="lbl">Cobertura</div>
    <div class="sub">{prod_total:,.0f} und/año</div>
  </div>
  <div class="kpi-card" style="flex:1;min-width:120px;">
    <div class="icon">✅</div>
    <div class="val">{cum_avg_g:.1f}%</div>
    <div class="lbl">Cumplimiento</div>
    <div class="sub">{MESES_F[mes_idx]}</div>
  </div>
  <div class="kpi-card" style="flex:1;min-width:120px;">
    <div class="icon">⚙️</div>
    <div class="val">{util_max_g:.0f}%</div>
    <div class="lbl">Util. Máx.</div>
    <div class="sub">{"⚠️ Cuello" if util_max_g>=80 else "✓ Estable"}</div>
  </div>
  <div class="kpi-card" style="flex:1;min-width:120px;">
    <div class="icon">🌡️</div>
    <div class="val">{temp_avg_g:.0f}°C</div>
    <div class="lbl">Temp. Horno</div>
    <div class="sub">{"⚠️ "+str(excesos_g)+" excesos" if excesos_g else "✓ Sin alertas"}</div>
  </div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("""
<div style='text-align:center;color:#8C7B70;font-size:0.82rem;
     font-family:Plus Jakarta Sans,sans-serif;padding:0.3rem 0 1rem'>
  🥐 <b>Gemelo Digital — Panadería Dora del Hoyo v4.0</b> &nbsp;·&nbsp;
  Optimización LP · Desagregación · SimPy · Streamlit
</div>""", unsafe_allow_html=True)


