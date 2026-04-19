"""
app.py  —  Gemelo Digital · Panadería Dora del Hoyo
====================================================
App Streamlit completa que integra:
  • Análisis de demanda
  • Planeación agregada (PuLP)
  • Desagregación por producto
  • Simulación de eventos discretos (SimPy)
  • Análisis de escenarios what-if

Ejecutar:
    streamlit run app.py
"""

import math
import random
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import simpy
import streamlit as st
from pulp import (
    LpProblem, LpMinimize, LpVariable, lpSum, value, PULP_CBC_CMD
)

# ──────────────────────────────────────────────────────────────────────────────
# DATOS MAESTROS
# ──────────────────────────────────────────────────────────────────────────────

PRODUCTOS = [
    "Brownies", "Mantecadas", "Mantecadas_Amapola", "Torta_Naranja", "Pan_Maiz",
]

MESES = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December",
]

MESES_ES = [
    "Enero","Febrero","Marzo","Abril","Mayo","Junio",
    "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre",
]

DEM_HISTORICA = {
    "Brownies":           [315, 804, 734, 541, 494,  59, 315, 803, 734, 541, 494,  59],
    "Mantecadas":         [125, 780, 432, 910, 275,  68, 512, 834, 690, 455, 389, 120],
    "Mantecadas_Amapola": [320, 710, 520, 251, 631, 150, 330, 220, 710, 610, 489, 180],
    "Torta_Naranja":      [100, 250, 200, 101, 190,  50, 100, 220, 200, 170, 180, 187],
    "Pan_Maiz":           [330, 140, 143,  73,  83,  48,  70,  89, 118,  83,  67,  87],
}

HORAS_PRODUCTO = {
    "Brownies": 0.866, "Mantecadas": 0.175,
    "Mantecadas_Amapola": 0.175, "Torta_Naranja": 0.175, "Pan_Maiz": 0.312,
}

PROD_COLORS = {
    "Brownies": "#E8A838", "Mantecadas": "#4FC3F7",
    "Mantecadas_Amapola": "#81C784", "Torta_Naranja": "#CE93D8", "Pan_Maiz": "#FF8A65",
}

RUTAS = {
    "Brownies": [
        ("Mezclado","mezcla",12,18),("Moldeado","dosificado",8,14),
        ("Horneado","horno",30,40),("Enfriamiento","enfriamiento",25,35),
        ("Corte_Empaque","empaque",8,12),
    ],
    "Mantecadas": [
        ("Mezclado","mezcla",12,18),("Dosificado","dosificado",16,24),
        ("Horneado","horno",20,30),("Enfriamiento","enfriamiento",35,55),
        ("Empaque","empaque",4,6),
    ],
    "Mantecadas_Amapola": [
        ("Mezclado","mezcla",12,18),("Inc_Semillas","mezcla",8,12),
        ("Dosificado","dosificado",16,24),("Horneado","horno",20,30),
        ("Enfriamiento","enfriamiento",36,54),("Empaque","empaque",4,6),
    ],
    "Torta_Naranja": [
        ("Mezclado","mezcla",16,24),("Dosificado","dosificado",8,12),
        ("Horneado","horno",32,48),("Enfriamiento","enfriamiento",48,72),
        ("Desmolde","dosificado",8,12),("Empaque","empaque",8,12),
    ],
    "Pan_Maiz": [
        ("Mezclado","mezcla",12,18),("Amasado","amasado",16,24),
        ("Moldeado","dosificado",12,18),("Horneado","horno",28,42),
        ("Enfriamiento","enfriamiento",36,54),("Empaque","empaque",4,6),
    ],
}

TAMANO_LOTE_BASE = {
    "Brownies":12,"Mantecadas":10,"Mantecadas_Amapola":10,
    "Torta_Naranja":12,"Pan_Maiz":15,
}

CAPACIDAD_BASE = {
    "mezcla":2,"dosificado":2,"horno":3,
    "enfriamiento":4,"empaque":2,"amasado":1,
}

PARAMS_DEFAULT = {
    "Ct":4_310,"Ht":100_000,"PIt":100_000,"CRt":11_364,"COt":14_205,
    "CW_mas":14_204,"CW_menos":15_061,"M":1,
    "LR_inicial":44*4*10,"inv_seg":0.0,
}

INV_INICIAL = {p: 0 for p in PRODUCTOS}


# ──────────────────────────────────────────────────────────────────────────────
# FUNCIONES DE NEGOCIO
# ──────────────────────────────────────────────────────────────────────────────

def demanda_horas_hombre(factor=1.0):
    return {
        mes: round(sum(DEM_HISTORICA[p][i]*HORAS_PRODUCTO[p] for p in PRODUCTOS)*factor, 4)
        for i, mes in enumerate(MESES)
    }


@st.cache_data(show_spinner=False)
def run_agregacion(factor_demanda=1.0, params_json=None):
    params = PARAMS_DEFAULT.copy() if params_json is None else dict(params_json)
    dem_h  = demanda_horas_hombre(factor_demanda)

    Ct=params["Ct"]; Ht=params["Ht"]; PIt=params["PIt"]
    CRt=params["CRt"]; COt=params["COt"]; Wm=params["CW_mas"]; Wd=params["CW_menos"]
    M=params["M"]; LRi=params["LR_inicial"]

    mdl = LpProblem("Agregacion", LpMinimize)
    P   = LpVariable.dicts("P",  MESES, lowBound=0)
    I   = LpVariable.dicts("I",  MESES, lowBound=0)
    S   = LpVariable.dicts("S",  MESES, lowBound=0)
    LR  = LpVariable.dicts("LR", MESES, lowBound=0)
    LO  = LpVariable.dicts("LO", MESES, lowBound=0)
    LU  = LpVariable.dicts("LU", MESES, lowBound=0)
    NI  = LpVariable.dicts("NI", MESES)
    Wmas= LpVariable.dicts("Wm", MESES, lowBound=0)
    Wmenos=LpVariable.dicts("Wd",MESES, lowBound=0)

    mdl += lpSum(Ct*P[t]+Ht*I[t]+PIt*S[t]+CRt*LR[t]+COt*LO[t]+Wm*Wmas[t]+Wd*Wmenos[t] for t in MESES)

    for idx, t in enumerate(MESES):
        d  = dem_h[t]; tp = MESES[idx-1] if idx>0 else None
        if idx==0: mdl += NI[t]==0+P[t]-d
        else:      mdl += NI[t]==NI[tp]+P[t]-d
        mdl += NI[t]==I[t]-S[t]
        mdl += LU[t]+LO[t]==M*P[t]
        mdl += LU[t]<=LR[t]
        if idx==0: mdl += LR[t]==LRi+Wmas[t]-Wmenos[t]
        else:      mdl += LR[t]==LR[tp]+Wmas[t]-Wmenos[t]

    mdl.solve(PULP_CBC_CMD(msg=False))
    costo = value(mdl.objective)

    ini_l, fin_l = [], []
    for idx, t in enumerate(MESES):
        ini = 0.0 if idx==0 else fin_l[-1]
        ini_l.append(ini)
        fin_l.append(ini+(P[t].varValue or 0)-dem_h[t])

    df = pd.DataFrame({
        "Mes": MESES,
        "Mes_ES": MESES_ES,
        "Demanda_HH":           [round(dem_h[t],2) for t in MESES],
        "Produccion_HH":        [round(P[t].varValue or 0,2) for t in MESES],
        "Backlog_HH":           [round(S[t].varValue or 0,2) for t in MESES],
        "Horas_Regulares":      [round(LR[t].varValue or 0,2) for t in MESES],
        "Horas_Extras":         [round(LO[t].varValue or 0,2) for t in MESES],
        "Inventario_Inicial_HH":[round(v,2) for v in ini_l],
        "Inventario_Final_HH":  [round(v,2) for v in fin_l],
        "Contratacion":         [round(Wmas[t].varValue or 0,2) for t in MESES],
        "Despidos":             [round(Wmenos[t].varValue or 0,2) for t in MESES],
    })
    return df, costo


@st.cache_data(show_spinner=False)
def run_desagregacion(prod_hh_items, factor_demanda=1.0):
    prod_hh = dict(prod_hh_items)
    mdl = LpProblem("Desagregacion", LpMinimize)
    X   = {(p,t): LpVariable(f"X_{p}_{t}", lowBound=0) for p in PRODUCTOS for t in MESES}
    I   = {(p,t): LpVariable(f"I_{p}_{t}", lowBound=0) for p in PRODUCTOS for t in MESES}
    S   = {(p,t): LpVariable(f"S_{p}_{t}", lowBound=0) for p in PRODUCTOS for t in MESES}

    mdl += lpSum(100_000*I[p,t]+150_000*S[p,t] for p in PRODUCTOS for t in MESES)

    for idx, t in enumerate(MESES):
        tp = MESES[idx-1] if idx>0 else None
        mdl += (lpSum(HORAS_PRODUCTO[p]*X[p,t] for p in PRODUCTOS) <= prod_hh[t], f"Cap_{t}")
        for p in PRODUCTOS:
            d = int(DEM_HISTORICA[p][idx]*factor_demanda)
            if idx==0: mdl += I[p,t]-S[p,t]==INV_INICIAL[p]+X[p,t]-d
            else:      mdl += I[p,t]-S[p,t]==I[p,tp]-S[p,tp]+X[p,t]-d

    mdl.solve(PULP_CBC_CMD(msg=False))

    resultados = {}
    for p in PRODUCTOS:
        filas = []
        for idx, t in enumerate(MESES):
            xv = round(X[p,t].varValue or 0, 2)
            iv = round(I[p,t].varValue or 0, 2)
            sv = round(S[p,t].varValue or 0, 2)
            ini = INV_INICIAL[p] if idx==0 else round(I[p,MESES[idx-1]].varValue or 0, 2)
            filas.append({
                "Mes": t, "Mes_ES": MESES_ES[idx],
                "Demanda": int(DEM_HISTORICA[p][idx]*factor_demanda),
                "Produccion": xv, "Inv_Ini": ini, "Inv_Fin": iv, "Backlog": sv,
            })
        resultados[p] = pd.DataFrame(filas)
    return resultados


@st.cache_data(show_spinner=False)
def run_simulacion_cached(plan_items, cap_items, falla, factor_t, semilla=42):
    plan_unidades = dict(plan_items)
    cap_recursos  = dict(cap_items)
    tamano_lote   = TAMANO_LOTE_BASE.copy()

    random.seed(semilla); np.random.seed(semilla)
    lotes_data, uso_rec, sensores = [], [], []

    def sensor_horno(env, recursos):
        while True:
            ocp  = recursos["horno"].count
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
        t0 = env.now
        esperas = {}
        for etapa, rec_nm, tmin, tmax in RUTAS[prod]:
            escala = math.sqrt(tam/TAMANO_LOTE_BASE[prod])
            tp     = random.uniform(tmin, tmax)*escala*factor_t
            if falla and rec_nm=="horno": tp += random.uniform(10, 30)
            reg_uso(env, recursos, prod)
            t_entrada = env.now
            with recursos[rec_nm].request() as req:
                yield req
                esperas[etapa] = round(env.now-t_entrada, 3)
                reg_uso(env, recursos, prod)
                yield env.timeout(tp)
            reg_uso(env, recursos, prod)
        lotes_data.append({
            "lote_id":lid,"producto":prod,"tamano":tam,
            "t_creacion":round(t0,3),"t_fin":round(env.now,3),
            "tiempo_sistema":round(env.now-t0,3),
            "total_espera":round(sum(esperas.values()),3),
        })

    env      = simpy.Environment()
    recursos = {nm: simpy.Resource(env, capacity=cap) for nm,cap in cap_recursos.items()}
    env.process(sensor_horno(env, recursos))

    dur_mes = 44*4*60
    lotes   = []
    ctr     = [0]
    for prod, unid in plan_unidades.items():
        if unid<=0: continue
        tam  = tamano_lote[prod]; n = math.ceil(unid/tam)
        tasa = dur_mes/max(n,1)
        ta   = random.expovariate(1/max(tasa,1))
        rem  = unid
        for _ in range(n):
            lotes.append((round(ta,2), prod, min(tam,int(rem))))
            rem -= tam
            ta  += random.expovariate(1/max(tasa,1))

    lotes.sort(key=lambda x: x[0])

    def lanzador():
        for ta, prod, tam in lotes:
            yield env.timeout(max(ta-env.now,0))
            lid = f"{prod[:3].upper()}_{ctr[0]:04d}"; ctr[0]+=1
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
        cap = grp["capacidad"].iloc[0]; t = grp["tiempo"].values; ocp = grp["ocupados"].values
        if len(t)>1 and (t[-1]-t[0])>0:
            fn = np.trapezoid if hasattr(np,"trapezoid") else np.trapz
            util = round(fn(ocp,t)/(cap*(t[-1]-t[0]))*100, 2)
        else: util=0.0
        filas.append({
            "Recurso":rec,"Utilización_%":util,
            "Cola Prom":round(grp["cola"].mean(),3),
            "Cola Máx":int(grp["cola"].max()),
            "Capacidad":int(cap),
            "Cuello Botella": util>=80 or grp["cola"].mean()>0.5,
        })
    return pd.DataFrame(filas).sort_values("Utilización_%",ascending=False).reset_index(drop=True)


def calc_kpis(df_lotes, plan):
    if df_lotes.empty: return pd.DataFrame()
    dur = (df_lotes["t_fin"].max()-df_lotes["t_creacion"].min())/60
    filas = []
    for p in PRODUCTOS:
        sub = df_lotes[df_lotes["producto"]==p]
        if sub.empty: continue
        und = sub["tamano"].sum(); plan_und = plan.get(p,0)
        tp  = round(und/max(dur,0.01),3)
        ct  = round((sub["tiempo_sistema"]/sub["tamano"]).mean(),3)
        lt  = round(sub["tiempo_sistema"].mean(),3)
        dem_avg = sum(DEM_HISTORICA[p])/12
        takt = round((44*4*60)/max(dem_avg/TAMANO_LOTE_BASE[p],1),2)
        wip  = round(tp*(lt/60),2)
        filas.append({
            "Producto":p,"Und Producidas":und,"Plan":plan_und,
            "Throughput (und/h)":tp,"Cycle Time (min/und)":ct,
            "Lead Time (min/lote)":lt,"WIP Prom":wip,
            "Takt Time (min/lote)":takt,
            "Cumplimiento %":round(min(und/max(plan_und,1)*100,100),2),
        })
    return pd.DataFrame(filas)


# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN DE PÁGINA
# ──────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Gemelo Digital · Dora del Hoyo",
    page_icon="🥐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS personalizado — look panadería artesanal: cálido y profesional
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=DM+Sans:wght@300;400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

/* Header principal */
.main-header {
    background: linear-gradient(135deg, #2C1A0E 0%, #5C3317 50%, #8B4513 100%);
    padding: 2rem 2.5rem 1.5rem;
    border-radius: 16px;
    margin-bottom: 1.5rem;
    box-shadow: 0 8px 32px rgba(44,26,14,0.3);
}
.main-header h1 {
    font-family: 'Playfair Display', serif;
    color: #F5DEB3;
    font-size: 2.2rem;
    margin: 0;
    letter-spacing: -0.5px;
}
.main-header p {
    color: #D2A679;
    margin: 0.3rem 0 0;
    font-size: 0.95rem;
    font-weight: 300;
}

/* Tarjetas de métricas */
.metric-card {
    background: #FFFDF8;
    border: 1px solid #E8D5B0;
    border-radius: 12px;
    padding: 1.1rem 1.3rem;
    text-align: center;
    box-shadow: 0 2px 8px rgba(139,69,19,0.08);
}
.metric-card .label {
    font-size: 0.75rem;
    color: #9B7B5A;
    text-transform: uppercase;
    letter-spacing: 1px;
    font-weight: 500;
}
.metric-card .value {
    font-family: 'Playfair Display', serif;
    font-size: 1.7rem;
    color: #2C1A0E;
    margin: 0.2rem 0 0;
    line-height: 1;
}
.metric-card .delta {
    font-size: 0.78rem;
    color: #81C784;
    margin-top: 0.2rem;
}
.metric-card .delta.neg { color: #EF5350; }

/* Sección headers */
.section-title {
    font-family: 'Playfair Display', serif;
    font-size: 1.3rem;
    color: #2C1A0E;
    border-bottom: 2px solid #E8A838;
    padding-bottom: 0.4rem;
    margin: 1.5rem 0 1rem;
}

/* Alerta de cuello de botella */
.alert-red {
    background: #FFF3F3;
    border-left: 4px solid #EF5350;
    padding: 0.7rem 1rem;
    border-radius: 0 8px 8px 0;
    font-size: 0.88rem;
    color: #C62828;
    margin: 0.5rem 0;
}
.alert-green {
    background: #F3FFF4;
    border-left: 4px solid #81C784;
    padding: 0.7rem 1rem;
    border-radius: 0 8px 8px 0;
    font-size: 0.88rem;
    color: #2E7D32;
    margin: 0.5rem 0;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #2C1A0E !important;
}
[data-testid="stSidebar"] * { color: #F5DEB3 !important; }
[data-testid="stSidebar"] .stSlider > div > div { background: #E8A838 !important; }

/* Tabs */
.stTabs [data-baseweb="tab"] {
    font-family: 'DM Sans', sans-serif;
    font-weight: 500;
}
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# SIDEBAR — CONTROLES
# ──────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🥐 Controles")
    st.markdown("---")

    st.markdown("### 📅 Simulación")
    mes_idx = st.selectbox("Mes a simular", range(12), index=1,
                           format_func=lambda i: MESES_ES[i])
    factor_demanda = st.slider("Factor de demanda", 0.5, 2.0, 1.0, 0.05,
                                help="Multiplica la demanda histórica")

    st.markdown("### 🏭 Capacidad")
    cap_horno = st.slider("Capacidad del horno", 1, 6, 3,
                           help="Número de estaciones simultáneas")
    falla_horno = st.checkbox("⚠️ Simular fallas en horno", value=False)
    doble_turno = st.checkbox("🕐 Doble turno (–20% tiempo)", value=False)

    st.markdown("### 💰 Costos (COP)")
    with st.expander("Ajustar parámetros"):
        ct  = st.number_input("Costo producción/und", value=4_310, step=100)
        crt = st.number_input("Costo hora regular",   value=11_364, step=100)
        cot = st.number_input("Costo hora extra",     value=14_205, step=100)
        ht  = st.number_input("Costo mantener inv.",  value=100_000, step=1000)

    st.markdown("### 🌱 Reproducibilidad")
    semilla = st.number_input("Semilla aleatoria", value=42, step=1)

    st.markdown("---")
    run_btn = st.button("▶ Ejecutar pipeline", type="primary", use_container_width=True)


# ──────────────────────────────────────────────────────────────────────────────
# HEADER
# ──────────────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="main-header">
  <h1>🥐 Gemelo Digital — Panadería Dora del Hoyo</h1>
  <p>Planeación agregada · Desagregación · Simulación de eventos discretos · Análisis what-if</p>
</div>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# EJECUCIÓN DEL PIPELINE
# ──────────────────────────────────────────────────────────────────────────────

params_custom = {**PARAMS_DEFAULT, "Ct": ct, "CRt": crt, "COt": cot, "Ht": ht}

with st.spinner("⚙️ Ejecutando planeación agregada..."):
    df_agr, costo = run_agregacion(
        factor_demanda,
        tuple(sorted(params_custom.items()))
    )

prod_hh = dict(zip(df_agr["Mes"], df_agr["Produccion_HH"]))

with st.spinner("🔢 Desagregando por producto..."):
    desag = run_desagregacion(tuple(prod_hh.items()), factor_demanda)

mes_nm = MESES[mes_idx]
plan_mes = {
    p: int(desag[p].loc[desag[p]["Mes"]==mes_nm, "Produccion"].values[0])
    for p in PRODUCTOS
}

cap_rec   = {**CAPACIDAD_BASE, "horno": int(cap_horno)}
factor_t  = 0.80 if doble_turno else 1.0

with st.spinner("🏭 Simulando producción..."):
    df_lotes, df_uso, df_sensores = run_simulacion_cached(
        tuple(plan_mes.items()), tuple(cap_rec.items()),
        falla_horno, factor_t, int(semilla)
    )

df_kpis = calc_kpis(df_lotes, plan_mes)
df_util  = calc_utilizacion(df_uso)


# ──────────────────────────────────────────────────────────────────────────────
# KPIs SUPERIORES
# ──────────────────────────────────────────────────────────────────────────────

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("💰 Costo Óptimo", f"${costo/1e6:.1f}M COP")
with col2:
    lotes_total = len(df_lotes) if not df_lotes.empty else 0
    st.metric("📦 Lotes simulados", f"{lotes_total:,}")
with col3:
    if not df_kpis.empty:
        cum_avg = df_kpis["Cumplimiento %"].mean()
        st.metric("✅ Cumplimiento prom.", f"{cum_avg:.1f}%")
    else:
        st.metric("✅ Cumplimiento prom.", "—")
with col4:
    if not df_util.empty:
        util_max = df_util["Utilización_%"].max()
        delta_color = "inverse" if util_max >= 80 else "normal"
        st.metric("⚙️ Util. máx. recurso", f"{util_max:.1f}%")
    else:
        st.metric("⚙️ Util. máx. recurso", "—")
with col5:
    if not df_sensores.empty:
        temp_avg = df_sensores["temperatura"].mean()
        excesos  = (df_sensores["temperatura"] > 200).sum()
        st.metric("🌡️ Temp. prom. horno", f"{temp_avg:.1f} °C",
                  delta=f"⚠️ {excesos} excesos" if excesos else "✓ Normal")
    else:
        st.metric("🌡️ Temp. prom. horno", "—")

st.markdown("---")


# ──────────────────────────────────────────────────────────────────────────────
# TABS PRINCIPALES
# ──────────────────────────────────────────────────────────────────────────────

tabs = st.tabs([
    "📊 Demanda", "📋 Plan Agregado", "📦 Desagregación",
    "🏭 Simulación", "🌡️ Sensores", "🔬 Escenarios"
])


# ════════════════════════════════════════════════════
# TAB 1 — DEMANDA
# ════════════════════════════════════════════════════
with tabs[0]:
    st.markdown('<div class="section-title">Demanda Histórica por Producto</div>', unsafe_allow_html=True)

    # Gráfica barras agrupadas
    fig = go.Figure()
    for p in PRODUCTOS:
        dem_aj = [v * factor_demanda for v in DEM_HISTORICA[p]]
        fig.add_trace(go.Bar(
            x=MESES_ES, y=dem_aj, name=p.replace("_"," "),
            marker_color=PROD_COLORS[p], opacity=0.85,
        ))
    fig.update_layout(
        barmode="group", title="Demanda por Producto y Mes",
        xaxis_title="Mes", yaxis_title="Unidades",
        template="plotly_white",
        legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center"),
        height=380,
    )
    st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)

    with col_a:
        # Heatmap
        z = [[DEM_HISTORICA[p][i]*factor_demanda for i in range(12)] for p in PRODUCTOS]
        fig2 = go.Figure(go.Heatmap(
            z=z, x=MESES_ES, y=[p.replace("_"," ") for p in PRODUCTOS],
            colorscale="YlOrBr",
        ))
        fig2.update_layout(title="Mapa de Calor — Estacionalidad", template="plotly_white", height=280)
        st.plotly_chart(fig2, use_container_width=True)

    with col_b:
        # Demanda en H-H
        dem_h = demanda_horas_hombre(factor_demanda)
        fig3 = go.Figure(go.Scatter(
            x=MESES_ES, y=list(dem_h.values()),
            mode="lines+markers", fill="tozeroy",
            line=dict(color="#E8A838", width=2.5),
            fillcolor="rgba(232,168,56,0.15)",
            marker=dict(size=7),
        ))
        fig3.update_layout(
            title="Demanda Total en Horas-Hombre",
            xaxis_title="Mes", yaxis_title="H-H",
            template="plotly_white", height=280,
        )
        st.plotly_chart(fig3, use_container_width=True)

    # Tabla resumen
    st.markdown('<div class="section-title">Resumen Estadístico</div>', unsafe_allow_html=True)
    df_dem = pd.DataFrame(DEM_HISTORICA, index=MESES_ES)
    df_dem = df_dem * factor_demanda
    stats = df_dem.describe().T.round(1)
    stats["CV %"] = (stats["std"]/stats["mean"]*100).round(1)
    st.dataframe(stats, use_container_width=True)


# ════════════════════════════════════════════════════
# TAB 2 — PLAN AGREGADO
# ════════════════════════════════════════════════════
with tabs[1]:
    st.markdown('<div class="section-title">Plan Agregado — Optimización LP</div>', unsafe_allow_html=True)

    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric("Costo Total Óptimo", f"COP ${costo:,.0f}")
    with col_m2:
        extras_total = df_agr["Horas_Extras"].sum()
        st.metric("Horas Extra Totales", f"{extras_total:,.0f} H-H")
    with col_m3:
        backlog_total = df_agr["Backlog_HH"].sum()
        st.metric("Backlog Total", f"{backlog_total:,.0f} H-H",
                  delta="⚠️ revisar" if backlog_total > 0 else "✓ Sin backlog",
                  delta_color="inverse" if backlog_total > 0 else "off")

    # Gráfica plan agregado
    fig4 = go.Figure()
    fig4.add_trace(go.Bar(
        x=df_agr["Mes_ES"], y=df_agr["Inventario_Inicial_HH"],
        name="Inv. Inicial H-H", marker_color="#5C6BC0", opacity=0.8,
    ))
    fig4.add_trace(go.Bar(
        x=df_agr["Mes_ES"], y=df_agr["Produccion_HH"],
        name="Producción H-H", marker_color="#E8A838", opacity=0.85,
    ))
    fig4.add_trace(go.Scatter(
        x=df_agr["Mes_ES"], y=df_agr["Demanda_HH"],
        mode="lines+markers", name="Demanda H-H",
        line=dict(color="#81C784", dash="dash", width=2.5), marker=dict(size=7),
    ))
    fig4.add_trace(go.Scatter(
        x=df_agr["Mes_ES"], y=df_agr["Horas_Regulares"],
        mode="lines", name="Cap. Regular",
        line=dict(color="#FF8A65", dash="dot", width=2),
    ))
    fig4.update_layout(
        barmode="stack", title=f"Plan Agregado — Costo Óptimo: COP ${costo:,.0f}",
        xaxis_title="Mes", yaxis_title="Horas-Hombre",
        template="plotly_white",
        legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center"),
        height=400,
    )
    st.plotly_chart(fig4, use_container_width=True)

    # Fuerza laboral
    col_fl1, col_fl2 = st.columns(2)
    with col_fl1:
        fig5 = go.Figure()
        fig5.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Contratacion"],
                              name="Contrataciones", marker_color="#4FC3F7"))
        fig5.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Despidos"],
                              name="Despidos", marker_color="#EF5350"))
        fig5.update_layout(barmode="group", title="Movimiento de Fuerza Laboral",
                           template="plotly_white", height=320)
        st.plotly_chart(fig5, use_container_width=True)

    with col_fl2:
        fig6 = go.Figure()
        fig6.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Horas_Extras"],
                              marker_color="#E8A838", name="Horas Extra"))
        fig6.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Backlog_HH"],
                              marker_color="#EF5350", name="Backlog"))
        fig6.update_layout(barmode="group", title="Horas Extra y Backlog",
                           template="plotly_white", height=320)
        st.plotly_chart(fig6, use_container_width=True)

    # Tabla completa
    st.markdown('<div class="section-title">Tabla Detallada del Plan</div>', unsafe_allow_html=True)
    df_show = df_agr.drop(columns=["Mes"]).rename(columns={"Mes_ES": "Mes"})
    st.dataframe(df_show.style.format({
        c: "{:,.1f}" for c in df_show.columns if c != "Mes"
    }), use_container_width=True, height=300)


# ════════════════════════════════════════════════════
# TAB 3 — DESAGREGACIÓN
# ════════════════════════════════════════════════════
with tabs[2]:
    st.markdown('<div class="section-title">Desagregación por Producto</div>', unsafe_allow_html=True)

    # Selector de mes para resaltar
    mes_resaltar = st.selectbox("Mes a resaltar ★", range(12),
                                index=mes_idx, format_func=lambda i: MESES_ES[i],
                                key="mes_desag")
    mes_nm_desag = MESES[mes_resaltar]

    # Subplots
    fig7 = make_subplots(
        rows=3, cols=2,
        subplot_titles=[p.replace("_"," ") for p in PRODUCTOS],
        vertical_spacing=0.1, horizontal_spacing=0.08,
    )
    for idx, p in enumerate(PRODUCTOS):
        r, c = idx//2+1, idx%2+1
        df_p = desag[p]
        fig7.add_trace(go.Bar(
            x=df_p["Mes_ES"], y=df_p["Produccion"],
            marker_color=PROD_COLORS[p], opacity=0.85, showlegend=False,
        ), row=r, col=c)
        fig7.add_trace(go.Scatter(
            x=df_p["Mes_ES"], y=df_p["Demanda"],
            mode="lines+markers", name="Demanda",
            line=dict(color="#81C784", dash="dash", width=1.5),
            marker=dict(size=5), showlegend=False,
        ), row=r, col=c)
        mes_row = df_p[df_p["Mes"]==mes_nm_desag]
        if not mes_row.empty:
            fig7.add_trace(go.Scatter(
                x=[MESES_ES[mes_resaltar]],
                y=[mes_row["Produccion"].values[0]],
                mode="markers", marker=dict(size=12, color="#E8A838", symbol="star"),
                showlegend=False,
            ), row=r, col=c)

    fig7.update_layout(
        height=700, barmode="group",
        title="Producción vs Demanda por Producto",
        template="plotly_white",
    )
    st.plotly_chart(fig7, use_container_width=True)

    # Cobertura
    st.markdown('<div class="section-title">Cobertura de Demanda</div>', unsafe_allow_html=True)
    prods_cob, cob_vals = [], []
    for p in PRODUCTOS:
        df_p  = desag[p]
        cob   = round(df_p["Produccion"].sum()/max(df_p["Demanda"].sum(),1)*100, 2)
        prods_cob.append(p.replace("_"," ")); cob_vals.append(cob)

    fig8 = go.Figure(go.Bar(
        x=prods_cob, y=cob_vals,
        marker_color=[PROD_COLORS[p] for p in PRODUCTOS],
        text=[f"{v:.1f}%" for v in cob_vals], textposition="outside",
    ))
    fig8.add_hline(y=100, line_dash="dash", line_color="green",
                   annotation_text="100% cobertura")
    fig8.update_layout(title="Cobertura de Demanda por Producto (%)",
                       yaxis_title="%", template="plotly_white", height=350)
    st.plotly_chart(fig8, use_container_width=True)


# ════════════════════════════════════════════════════
# TAB 4 — SIMULACIÓN
# ════════════════════════════════════════════════════
with tabs[3]:
    st.markdown(f'<div class="section-title">Simulación — {MESES_ES[mes_idx]}</div>',
                unsafe_allow_html=True)

    # Plan del mes
    st.markdown("**Plan del mes (unidades a producir):**")
    cols_plan = st.columns(5)
    for i, (p, u) in enumerate(plan_mes.items()):
        with cols_plan[i]:
            st.metric(p.replace("_"," "), f"{u:,}")

    st.markdown("---")

    # KPIs
    if not df_kpis.empty:
        st.markdown('<div class="section-title">KPIs por Producto</div>', unsafe_allow_html=True)
        st.dataframe(df_kpis.style.format({
            c: "{:,.2f}" for c in df_kpis.columns if c not in ["Producto"]
        }).background_gradient(subset=["Cumplimiento %"], cmap="RdYlGn"),
            use_container_width=True)

    # Utilización
    if not df_util.empty:
        st.markdown('<div class="section-title">Utilización de Recursos</div>', unsafe_allow_html=True)

        cuellos = df_util[df_util["Cuello Botella"]]
        if not cuellos.empty:
            for _, row in cuellos.iterrows():
                st.markdown(
                    f'<div class="alert-red">⚠️ <b>Cuello de botella: {row["Recurso"]}</b> — '
                    f'Utilización: {row["Utilización_%"]}% | Cola prom.: {row["Cola Prom"]}</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown('<div class="alert-green">✅ Sin cuellos de botella detectados</div>',
                        unsafe_allow_html=True)

        colores_util = [
            "#c0392b" if u >= 80 else "#E8A838" if u >= 60 else "#4FC3F7"
            for u in df_util["Utilización_%"]
        ]
        fig9 = make_subplots(rows=1, cols=2,
                             subplot_titles=["Utilización (%)", "Cola Promedio"])
        fig9.add_trace(go.Bar(
            x=df_util["Recurso"], y=df_util["Utilización_%"],
            marker_color=colores_util,
            text=df_util["Utilización_%"].apply(lambda v: f"{v:.1f}%"),
            textposition="outside", showlegend=False,
        ), row=1, col=1)
        fig9.add_trace(go.Bar(
            x=df_util["Recurso"], y=df_util["Cola Prom"],
            marker_color="#CE93D8",
            text=df_util["Cola Prom"].apply(lambda v: f"{v:.2f}"),
            textposition="outside", showlegend=False,
        ), row=1, col=2)
        fig9.add_hline(y=80, line_dash="dash", line_color="#c0392b",
                       annotation_text="⚠ 80%", row=1, col=1)
        fig9.update_layout(template="plotly_white", height=350)
        st.plotly_chart(fig9, use_container_width=True)

    # Gantt
    if not df_lotes.empty:
        st.markdown('<div class="section-title">Diagrama de Gantt (primeros 80 lotes)</div>',
                    unsafe_allow_html=True)
        n_gantt = min(80, len(df_lotes))
        sub     = df_lotes.head(n_gantt).reset_index(drop=True)
        fig10   = go.Figure()
        for _, row in sub.iterrows():
            col_g = PROD_COLORS.get(row["producto"], "#aaa")
            fig10.add_trace(go.Bar(
                x=[row["tiempo_sistema"]], y=[row["lote_id"]],
                base=[row["t_creacion"]], orientation="h",
                marker_color=col_g, opacity=0.8,
                showlegend=False,
                hovertemplate=(f"<b>{row['producto']}</b><br>"
                               f"Inicio: {row['t_creacion']:.0f} min<br>"
                               f"Dur: {row['tiempo_sistema']:.1f} min<extra></extra>"),
            ))
        for p, c in PROD_COLORS.items():
            fig10.add_trace(go.Bar(x=[None], y=[None], marker_color=c,
                                   name=p.replace("_"," "), showlegend=True))
        fig10.update_layout(
            barmode="overlay", title="Gantt — Lotes de Producción",
            xaxis_title="Tiempo simulado (min)", yaxis_title="Lote ID",
            template="plotly_white",
            height=max(400, n_gantt*7),
            legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"),
        )
        st.plotly_chart(fig10, use_container_width=True)


# ════════════════════════════════════════════════════
# TAB 5 — SENSORES
# ════════════════════════════════════════════════════
with tabs[4]:
    st.markdown('<div class="section-title">Sensores Virtuales — Horno</div>', unsafe_allow_html=True)

    if not df_sensores.empty:
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        with col_s1: st.metric("Temp. mínima",   f"{df_sensores['temperatura'].min():.1f} °C")
        with col_s2: st.metric("Temp. máxima",   f"{df_sensores['temperatura'].max():.1f} °C")
        with col_s3: st.metric("Temp. promedio", f"{df_sensores['temperatura'].mean():.1f} °C")
        with col_s4:
            excesos = (df_sensores["temperatura"] > 200).sum()
            st.metric("Excesos > 200°C", excesos,
                      delta="⚠️ Revisar" if excesos else "✓ OK",
                      delta_color="inverse" if excesos else "off")

        fig11 = make_subplots(rows=2, cols=1, shared_xaxes=True,
                              subplot_titles=["Temperatura del Horno (°C)", "Ocupación del Horno"])
        fig11.add_trace(go.Scatter(
            x=df_sensores["tiempo"], y=df_sensores["temperatura"],
            mode="lines", name="Temperatura", line=dict(color="#FF8A65", width=1.5),
        ), row=1, col=1)
        fig11.add_hline(y=200, line_dash="dash", line_color="#c0392b",
                        annotation_text="Límite 200°C", row=1, col=1)
        fig11.add_trace(go.Scatter(
            x=df_sensores["tiempo"], y=df_sensores["horno_ocup"],
            mode="lines", name="Ocupación", fill="tozeroy",
            fillcolor="rgba(79,195,247,0.12)", line=dict(color="#4FC3F7", width=1.5),
        ), row=2, col=1)
        fig11.update_layout(
            title="Monitor del Horno — Tiempo Real Simulado",
            template="plotly_white", height=460,
        )
        fig11.update_xaxes(title_text="Tiempo simulado (min)", row=2, col=1)
        fig11.update_yaxes(title_text="°C", row=1, col=1)
        fig11.update_yaxes(title_text="Estaciones", row=2, col=1)
        st.plotly_chart(fig11, use_container_width=True)

        # Distribución de temperatura
        fig12 = go.Figure(go.Histogram(
            x=df_sensores["temperatura"], nbinsx=40,
            marker_color="#E8A838", opacity=0.8,
        ))
        fig12.add_vline(x=200, line_dash="dash", line_color="#c0392b",
                        annotation_text="Límite 200°C")
        fig12.update_layout(
            title="Distribución de Temperatura del Horno",
            xaxis_title="°C", yaxis_title="Frecuencia",
            template="plotly_white", height=280,
        )
        st.plotly_chart(fig12, use_container_width=True)
    else:
        st.info("No hay datos de sensores disponibles. Ejecuta la simulación primero.")


# ════════════════════════════════════════════════════
# TAB 6 — ESCENARIOS WHAT-IF
# ════════════════════════════════════════════════════
with tabs[5]:
    st.markdown('<div class="section-title">Análisis de Escenarios What-If</div>', unsafe_allow_html=True)

    ESCENARIOS_DEF = {
        "Base":              {"fd":1.0, "falla":False, "ft":1.0,  "cap_delta":0},
        "Demanda +20%":      {"fd":1.2, "falla":False, "ft":1.0,  "cap_delta":0},
        "Falla en horno":    {"fd":1.0, "falla":True,  "ft":1.0,  "cap_delta":0},
        "Capacidad reducida":{"fd":1.0, "falla":False, "ft":1.0,  "cap_delta":-1},
        "Doble turno":       {"fd":1.0, "falla":False, "ft":0.80, "cap_delta":0},
        "Optimizado":        {"fd":1.0, "falla":False, "ft":0.85, "cap_delta":1},
    }

    escenarios_sel = st.multiselect(
        "Selecciona escenarios a comparar",
        list(ESCENARIOS_DEF.keys()),
        default=["Base", "Demanda +20%", "Falla en horno", "Doble turno"],
    )

    if st.button("🔬 Comparar escenarios seleccionados", type="secondary"):
        filas_esc = []
        prog = st.progress(0, text="Simulando escenarios...")

        for i, nm in enumerate(escenarios_sel):
            prog.progress((i+1)/len(escenarios_sel), text=f"Simulando: {nm}")
            cfg = ESCENARIOS_DEF[nm]
            plan_esc = {p: max(int(u*cfg["fd"]),0) for p,u in plan_mes.items()}
            cap_esc  = {**CAPACIDAD_BASE, "horno": max(cap_horno+cfg["cap_delta"],1)}

            df_l, df_u, _ = run_simulacion_cached(
                tuple(plan_esc.items()), tuple(cap_esc.items()),
                cfg["falla"], cfg["ft"], int(semilla)
            )
            kpis = calc_kpis(df_l, plan_esc)
            util = calc_utilizacion(df_u)

            fila = {"Escenario": nm}
            if not kpis.empty:
                fila["Throughput prom (und/h)"] = round(kpis["Throughput (und/h)"].mean(), 2)
                fila["Lead Time prom (min)"]    = round(kpis["Lead Time (min/lote)"].mean(), 2)
                fila["WIP Prom"]                = round(kpis["WIP Prom"].mean(), 2)
                fila["Cumplimiento % prom"]     = round(kpis["Cumplimiento %"].mean(), 2)
            if not util.empty:
                fila["Util. máx. %"] = round(util["Utilización_%"].max(), 2)
                fila["Cuellos botella"] = int(util["Cuello Botella"].sum())
            filas_esc.append(fila)

        prog.empty()
        df_comp = pd.DataFrame(filas_esc)
        st.dataframe(df_comp.style.highlight_max(
            subset=[c for c in df_comp.columns if c != "Escenario" and "Cuello" not in c],
            color="#E8F5E9",
        ).highlight_min(
            subset=["Cuellos botella"] if "Cuellos botella" in df_comp.columns else [],
            color="#E8F5E9",
        ), use_container_width=True)

        # Radar chart de comparación
        if len(df_comp) > 1:
            cols_radar = [c for c in df_comp.columns if c != "Escenario"]
            df_norm = df_comp[cols_radar].copy()
            for c in df_norm.columns:
                rng = df_norm[c].max() - df_norm[c].min()
                df_norm[c] = (df_norm[c] - df_norm[c].min()) / rng if rng else 0.5

            fig_r = go.Figure()
            colores_esc = ["#E8A838","#4FC3F7","#EF5350","#81C784","#CE93D8","#FF8A65"]
            for i, row in df_comp.iterrows():
                vals = [df_norm.loc[i,c] for c in cols_radar]
                fig_r.add_trace(go.Scatterpolar(
                    r=vals+[vals[0]], theta=cols_radar+[cols_radar[0]],
                    fill="toself", name=row["Escenario"],
                    line=dict(color=colores_esc[i % len(colores_esc)]),
                    fillcolor=colores_esc[i % len(colores_esc)].replace("#","rgba(") + ",0.1)",
                    opacity=0.8,
                ))
            fig_r.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0,1])),
                title="Comparación Normalizada de Escenarios",
                template="plotly_white", height=420,
            )
            st.plotly_chart(fig_r, use_container_width=True)
    else:
        st.info("👆 Selecciona los escenarios y haz clic en **Comparar** para ver los resultados.")


# ──────────────────────────────────────────────────────────────────────────────
# FOOTER
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<div style='text-align:center; color:#9B7B5A; font-size:0.82rem; font-family:DM Sans, sans-serif;'>"
    "🥐 Gemelo Digital — Panadería Dora del Hoyo &nbsp;|&nbsp; "
    "Planeación Agregada · SimPy · PuLP · Streamlit"
    "</div>",
    unsafe_allow_html=True,
)
