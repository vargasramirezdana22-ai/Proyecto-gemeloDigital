"""
app.py  —  Gemelo Digital · Panadería Dora del Hoyo
====================================================
Versión 3.0
- Diseño pastel artesanal y ejecutivo
- Pronóstico de demanda con proyección futura
- Planeación agregada parametrizable para panadería
- Desagregación con pesos de costo configurables
- Simulación SimPy con capacidades ajustables
- KPIs, sensores y escenarios con gráficas mejoradas

Ejecutar:
    streamlit run app.py
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
# PALETA · DORA DEL HOYO
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
    "Brownies": "Brownies",
    "Mantecadas": "Mantecadas",
    "Mantecadas_Amapola": "Mant. Amapola",
    "Torta_Naranja": "Torta Naranja",
    "Pan_Maiz": "Pan de Maíz",
}
EMOJIS = {
    "Brownies": "🍫",
    "Mantecadas": "🧁",
    "Mantecadas_Amapola": "🌸",
    "Torta_Naranja": "🍊",
    "Pan_Maiz": "🌽",
}
REC_LABELS = {
    "mezcla": "🥣 Mezcla",
    "dosificado": "🔧 Dosificado",
    "horno": "🔥 Horno",
    "enfriamiento": "❄️ Enfriamiento",
    "empaque": "📦 Empaque",
    "amasado": "👐 Amasado",
}


def hex_rgba(hex_color: str, alpha: float = 0.15) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ══════════════════════════════════════════════════════════════════════════════
# DATOS MAESTROS
# ══════════════════════════════════════════════════════════════════════════════
PRODUCTOS = ["Brownies", "Mantecadas", "Mantecadas_Amapola", "Torta_Naranja", "Pan_Maiz"]
MESES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]
MESES_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
MESES_F = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

DEM_HISTORICA = {
    "Brownies":           [315, 804, 734, 541, 494, 59, 315, 803, 734, 541, 494, 59],
    "Mantecadas":         [125, 780, 432, 910, 275, 68, 512, 834, 690, 455, 389, 120],
    "Mantecadas_Amapola": [320, 710, 520, 251, 631, 150, 330, 220, 710, 610, 489, 180],
    "Torta_Naranja":      [100, 250, 200, 101, 190, 50, 100, 220, 200, 170, 180, 187],
    "Pan_Maiz":           [330, 140, 143, 73, 83, 48, 70, 89, 118, 83, 67, 87],
}
HORAS_PRODUCTO = {
    "Brownies": 0.866,
    "Mantecadas": 0.175,
    "Mantecadas_Amapola": 0.175,
    "Torta_Naranja": 0.175,
    "Pan_Maiz": 0.312,
}
RUTAS = {
    "Brownies": [
        ("Mezclado", "mezcla", 12, 18),
        ("Moldeado", "dosificado", 8, 14),
        ("Horneado", "horno", 30, 40),
        ("Enfriamiento", "enfriamiento", 25, 35),
        ("Corte/Empaque", "empaque", 8, 12),
    ],
    "Mantecadas": [
        ("Mezclado", "mezcla", 12, 18),
        ("Dosificado", "dosificado", 16, 24),
        ("Horneado", "horno", 20, 30),
        ("Enfriamiento", "enfriamiento", 35, 55),
        ("Empaque", "empaque", 4, 6),
    ],
    "Mantecadas_Amapola": [
        ("Mezclado", "mezcla", 12, 18),
        ("Inc. Semillas", "mezcla", 8, 12),
        ("Dosificado", "dosificado", 16, 24),
        ("Horneado", "horno", 20, 30),
        ("Enfriamiento", "enfriamiento", 36, 54),
        ("Empaque", "empaque", 4, 6),
    ],
    "Torta_Naranja": [
        ("Mezclado", "mezcla", 16, 24),
        ("Dosificado", "dosificado", 8, 12),
        ("Horneado", "horno", 32, 48),
        ("Enfriamiento", "enfriamiento", 48, 72),
        ("Desmolde", "dosificado", 8, 12),
        ("Empaque", "empaque", 8, 12),
    ],
    "Pan_Maiz": [
        ("Mezclado", "mezcla", 12, 18),
        ("Amasado", "amasado", 16, 24),
        ("Moldeado", "dosificado", 12, 18),
        ("Horneado", "horno", 28, 42),
        ("Enfriamiento", "enfriamiento", 36, 54),
        ("Empaque", "empaque", 4, 6),
    ],
}
TAMANO_LOTE_BASE = {
    "Brownies": 12,
    "Mantecadas": 10,
    "Mantecadas_Amapola": 10,
    "Torta_Naranja": 12,
    "Pan_Maiz": 15,
}
CAPACIDAD_BASE = {
    "mezcla": 2,
    "dosificado": 2,
    "horno": 3,
    "enfriamiento": 4,
    "empaque": 2,
    "amasado": 1,
}
PARAMS_DEFAULT = {
    "Ct": 4310,
    "Ht": 100_000,
    "PIt": 120_000,
    "CRt": 11_364,
    "COt": 14_205,
    "CW_mas": 14_204,
    "CW_menos": 15_061,
    "M": 1,
    "LR_inicial": 44 * 4 * 10,
    "inv_seg": 0.05,
}
INV_INICIAL = {p: 0 for p in PRODUCTOS}


# ══════════════════════════════════════════════════════════════════════════════
# CORE
# ══════════════════════════════════════════════════════════════════════════════
def demanda_horas_hombre(factor: float = 1.0) -> dict:
    return {
        mes: round(sum(DEM_HISTORICA[p][i] * HORAS_PRODUCTO[p] for p in PRODUCTOS) * factor, 4)
        for i, mes in enumerate(MESES)
    }


def pronostico_simple(serie, meses_extra=3):
    alpha = 0.3
    nivel = serie[0]
    suavizada = []
    for v in serie:
        nivel = alpha * v + (1 - alpha) * nivel
        suavizada.append(nivel)
    futuro = []
    last = suavizada[-1]
    trend = (suavizada[-1] - suavizada[-4]) / 3 if len(suavizada) >= 4 else 0
    for _ in range(meses_extra):
        last = last + alpha * trend
        futuro.append(round(last, 1))
    return suavizada, futuro


@st.cache_data(show_spinner=False)
def run_agregacion(factor_demanda=1.0, params_tuple=None):
    params = PARAMS_DEFAULT.copy()
    if params_tuple:
        params.update(dict(params_tuple))

    dem_h = demanda_horas_hombre(factor_demanda)
    Ct = params["Ct"]
    Ht = params["Ht"]
    PIt = params["PIt"]
    CRt = params["CRt"]
    COt = params["COt"]
    Wm = params["CW_mas"]
    Wd = params["CW_menos"]
    M = params["M"]
    LRi = params["LR_inicial"]
    inv_seg = params["inv_seg"]

    mdl = LpProblem("Agregacion", LpMinimize)
    P = LpVariable.dicts("P", MESES, lowBound=0)
    I = LpVariable.dicts("I", MESES, lowBound=0)
    S = LpVariable.dicts("S", MESES, lowBound=0)
    LR = LpVariable.dicts("LR", MESES, lowBound=0)
    LO = LpVariable.dicts("LO", MESES, lowBound=0)
    LU = LpVariable.dicts("LU", MESES, lowBound=0)
    NI = LpVariable.dicts("NI", MESES)
    Wmas = LpVariable.dicts("Wm", MESES, lowBound=0)
    Wmenos = LpVariable.dicts("Wd", MESES, lowBound=0)

    mdl += lpSum(
        Ct * P[t] + Ht * I[t] + PIt * S[t] + CRt * LR[t] + COt * LO[t] + Wm * Wmas[t] + Wd * Wmenos[t]
        for t in MESES
    )

    for idx, t in enumerate(MESES):
        d = dem_h[t]
        tp = MESES[idx - 1] if idx > 0 else None
        if idx == 0:
            mdl += NI[t] == P[t] - d
        else:
            mdl += NI[t] == NI[tp] + P[t] - d

        mdl += NI[t] == I[t] - S[t]
        mdl += LU[t] + LO[t] == M * P[t]
        mdl += LU[t] <= LR[t]
        mdl += I[t] >= inv_seg * d

        if idx == 0:
            mdl += LR[t] == LRi + Wmas[t] - Wmenos[t]
        else:
            mdl += LR[t] == LR[tp] + Wmas[t] - Wmenos[t]

    mdl.solve(PULP_CBC_CMD(msg=False))
    costo = value(mdl.objective) or 0

    ini_l, fin_l = [], []
    for idx, t in enumerate(MESES):
        ini = 0.0 if idx == 0 else fin_l[-1]
        ini_l.append(ini)
        fin_l.append(ini + (P[t].varValue or 0) - dem_h[t])

    df = pd.DataFrame({
        "Mes": MESES,
        "Mes_F": MESES_F,
        "Mes_ES": MESES_ES,
        "Demanda_HH": [round(dem_h[t], 2) for t in MESES],
        "Produccion_HH": [round(P[t].varValue or 0, 2) for t in MESES],
        "Backlog_HH": [round(S[t].varValue or 0, 2) for t in MESES],
        "Horas_Regulares": [round(LR[t].varValue or 0, 2) for t in MESES],
        "Horas_Extras": [round(LO[t].varValue or 0, 2) for t in MESES],
        "Inv_Ini_HH": [round(v, 2) for v in ini_l],
        "Inv_Fin_HH": [round(v, 2) for v in fin_l],
        "Contratacion": [round(Wmas[t].varValue or 0, 2) for t in MESES],
        "Despidos": [round(Wmenos[t].varValue or 0, 2) for t in MESES],
    })
    return df, costo


@st.cache_data(show_spinner=False)
def run_desagregacion(prod_hh_items, factor_demanda=1.0, cost_prod=1.0, cost_inv=1.0):
    prod_hh = dict(prod_hh_items)
    mdl = LpProblem("Desagregacion", LpMinimize)
    X = {(p, t): LpVariable(f"X_{p}_{t}", lowBound=0) for p in PRODUCTOS for t in MESES}
    I = {(p, t): LpVariable(f"I_{p}_{t}", lowBound=0) for p in PRODUCTOS for t in MESES}
    S = {(p, t): LpVariable(f"S_{p}_{t}", lowBound=0) for p in PRODUCTOS for t in MESES}

    mdl += lpSum(cost_inv * 100_000 * I[p, t] + cost_prod * 150_000 * S[p, t] for p in PRODUCTOS for t in MESES)

    for idx, t in enumerate(MESES):
        tp = MESES[idx - 1] if idx > 0 else None
        mdl += lpSum(HORAS_PRODUCTO[p] * X[p, t] for p in PRODUCTOS) <= prod_hh[t]
        for p in PRODUCTOS:
            d = int(DEM_HISTORICA[p][idx] * factor_demanda)
            if idx == 0:
                mdl += I[p, t] - S[p, t] == INV_INICIAL[p] + X[p, t] - d
            else:
                mdl += I[p, t] - S[p, t] == I[p, tp] - S[p, tp] + X[p, t] - d

    mdl.solve(PULP_CBC_CMD(msg=False))

    resultados = {}
    for p in PRODUCTOS:
        filas = []
        for idx, t in enumerate(MESES):
            xv = round(X[p, t].varValue or 0, 2)
            iv = round(I[p, t].varValue or 0, 2)
            sv = round(S[p, t].varValue or 0, 2)
            ini = INV_INICIAL[p] if idx == 0 else round(I[p, MESES[idx - 1]].varValue or 0, 2)
            filas.append({
                "Mes": t,
                "Mes_ES": MESES_ES[idx],
                "Mes_F": MESES_F[idx],
                "Demanda": int(DEM_HISTORICA[p][idx] * factor_demanda),
                "Produccion": xv,
                "Produccion_HH": round(xv * HORAS_PRODUCTO[p], 2),
                "Inv_Ini": ini,
                "Inv_Fin": iv,
                "Backlog": sv,
            })
        resultados[p] = pd.DataFrame(filas)
    return resultados


@st.cache_data(show_spinner=False)
def run_simulacion_cached(plan_items, cap_items, falla, factor_t, tiempos_items, temp_horno_base=160, semilla=42):
    plan_unidades = dict(plan_items)
    cap_recursos = dict(cap_items)
    tiempos_cfg = dict(tiempos_items)

    random.seed(semilla)
    np.random.seed(semilla)

    lotes_data, uso_rec, sensores = [], [], []

    def rutas_efectivas():
        rutas = {}
        for p, etapas in RUTAS.items():
            rutas[p] = []
            for etapa, rec_nm, tmin, tmax in etapas:
                if rec_nm in tiempos_cfg:
                    rutas[p].append((etapa, rec_nm, tiempos_cfg[rec_nm][0], tiempos_cfg[rec_nm][1]))
                else:
                    rutas[p].append((etapa, rec_nm, tmin, tmax))
        return rutas

    rutas_eff = rutas_efectivas()

    def sensor_horno(env, recursos):
        while True:
            ocp = recursos["horno"].count
            temp = round(np.random.normal(temp_horno_base + ocp * 18, 4.5), 2)
            sensores.append({
                "tiempo": round(env.now, 1),
                "temperatura": temp,
                "horno_ocup": ocp,
                "horno_cola": len(recursos["horno"].queue),
            })
            yield env.timeout(10)

    def reg_uso(env, recursos, prod=""):
        ts = round(env.now, 3)
        for nm, r in recursos.items():
            uso_rec.append({
                "tiempo": ts,
                "recurso": nm,
                "ocupados": r.count,
                "cola": len(r.queue),
                "capacidad": r.capacity,
                "producto": prod,
            })

    def proceso_lote(env, lid, prod, tam, recursos):
        t0 = env.now
        esperas = {}
        for etapa, rec_nm, tmin, tmax in rutas_eff[prod]:
            escala = math.sqrt(tam / TAMANO_LOTE_BASE[prod])
            tp = random.uniform(tmin, tmax) * escala * factor_t
            if falla and rec_nm == "horno":
                tp += random.uniform(10, 25)
            reg_uso(env, recursos, prod)
            t_entrada = env.now
            with recursos[rec_nm].request() as req:
                yield req
                esperas[etapa] = round(env.now - t_entrada, 3)
                reg_uso(env, recursos, prod)
                yield env.timeout(tp)
            reg_uso(env, recursos, prod)

        lotes_data.append({
            "lote_id": lid,
            "producto": prod,
            "tamano": tam,
            "t_creacion": round(t0, 3),
            "t_fin": round(env.now, 3),
            "tiempo_sistema": round(env.now - t0, 3),
            "total_espera": round(sum(esperas.values()), 3),
        })

    env = simpy.Environment()
    recursos = {nm: simpy.Resource(env, capacity=cap) for nm, cap in cap_recursos.items()}
    env.process(sensor_horno(env, recursos))

    horas_mes = 44 * 4 * 60
    lotes = []
    ctr = [0]

    for prod, unid in plan_unidades.items():
        if unid <= 0:
            continue
        tam = TAMANO_LOTE_BASE[prod]
        n = math.ceil(unid / tam)
        tasa = horas_mes / max(n, 1)
        ta = random.expovariate(1 / max(tasa, 1))
        rem = unid
        for _ in range(n):
            lotes.append((round(ta, 2), prod, min(tam, int(rem))))
            rem -= tam
            ta += random.expovariate(1 / max(tasa, 1))

    lotes.sort(key=lambda x: x[0])

    def lanzador():
        for ta, prod, tam in lotes:
            yield env.timeout(max(ta - env.now, 0))
            lid = f"{prod[:3].upper()}_{ctr[0]:04d}"
            ctr[0] += 1
            env.process(proceso_lote(env, lid, prod, tam, recursos))

    env.process(lanzador())
    env.run(until=horas_mes * 1.8)

    df_lotes = pd.DataFrame(lotes_data) if lotes_data else pd.DataFrame()
    df_uso = pd.DataFrame(uso_rec) if uso_rec else pd.DataFrame()
    df_sensores = pd.DataFrame(sensores) if sensores else pd.DataFrame()
    return df_lotes, df_uso, df_sensores


def calc_utilizacion(df_uso):
    if df_uso.empty:
        return pd.DataFrame()
    filas = []
    for rec, grp in df_uso.groupby("recurso"):
        grp = grp.sort_values("tiempo").reset_index(drop=True)
        cap = grp["capacidad"].iloc[0]
        t = grp["tiempo"].values
        ocp = grp["ocupados"].values
        if len(t) > 1 and (t[-1] - t[0]) > 0:
            fn = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
            util = round(fn(ocp, t) / (cap * (t[-1] - t[0])) * 100, 2)
        else:
            util = 0.0
        filas.append({
            "Recurso": rec,
            "Utilizacion_%": util,
            "Cola Prom": round(grp["cola"].mean(), 3),
            "Cola Max": int(grp["cola"].max()),
            "Capacidad": int(cap),
            "Cuello Botella": util >= 80 or grp["cola"].mean() > 0.5,
        })
    return pd.DataFrame(filas).sort_values("Utilizacion_%", ascending=False).reset_index(drop=True)


def calc_kpis(df_lotes, plan):
    if df_lotes.empty:
        return pd.DataFrame()
    dur = (df_lotes["t_fin"].max() - df_lotes["t_creacion"].min()) / 60
    filas = []
    for p in PRODUCTOS:
        sub = df_lotes[df_lotes["producto"] == p]
        if sub.empty:
            continue
        und = sub["tamano"].sum()
        plan_und = plan.get(p, 0)
        tp = round(und / max(dur, 0.01), 3)
        ct = round((sub["tiempo_sistema"] / sub["tamano"]).mean(), 3)
        lt = round(sub["tiempo_sistema"].mean(), 3)
        dem_avg = sum(DEM_HISTORICA[p]) / 12
        takt = round((44 * 4 * 60) / max(dem_avg / TAMANO_LOTE_BASE[p], 1), 2)
        wip = round(tp * (lt / 60), 2)
        filas.append({
            "Producto": PROD_LABELS[p],
            "Und Producidas": und,
            "Plan": plan_und,
            "Throughput (und/h)": tp,
            "Cycle Time (min/und)": ct,
            "Lead Time (min/lote)": lt,
            "WIP Prom": wip,
            "Takt (min/lote)": takt,
            "Cumplimiento %": round(min(und / max(plan_und, 1) * 100, 100), 2),
        })
    return pd.DataFrame(filas)


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG · STREAMLIT
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Gemelo Digital · Dora del Hoyo",
    page_icon="🥐",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@500;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {{
    font-family:'Plus Jakarta Sans',sans-serif;
    background:{C["bg"]};
}}

.block-container {{
    padding-top: 1.2rem;
    padding-bottom: 1.5rem;
}}

.hero {{
    background: linear-gradient(135deg, {C["lavender"]} 0%, {C["sky"]} 35%, {C["peach"]} 100%);
    padding: 2rem 2.2rem 1.6rem;
    border-radius: 24px;
    margin-bottom: 1.2rem;
    border: 1px solid {C["line"]};
    box-shadow: 0 12px 28px rgba(120,100,90,0.10);
}}

.hero h1 {{
    font-family:'Fraunces',serif;
    color:{C["text"]};
    font-size:2.1rem;
    margin:0;
}}

.hero p {{
    color:{C["muted"]};
    margin:0.45rem 0 0;
    font-size:0.95rem;
}}

.hero .badge {{
    display:inline-block;
    background: rgba(255,255,255,0.75);
    color:{C["text"]};
    padding:0.28rem 0.8rem;
    border-radius:999px;
    font-size:0.75rem;
    margin-top:0.8rem;
    margin-right:0.35rem;
    border:1px solid {C["line"]};
}}

.kpi-card {{
    background:{C["panel"]};
    border-radius:18px;
    padding:1rem 1rem;
    border:1px solid {C["line"]};
    box-shadow:0 6px 18px rgba(120,100,90,0.07);
    text-align:center;
}}

.kpi-card .icon {{
    font-size:1.55rem;
    margin-bottom:0.2rem;
}}

.kpi-card .val {{
    font-family:'Fraunces',serif;
    font-size:1.65rem;
    color:{C["text"]};
    line-height:1;
}}

.kpi-card .lbl {{
    font-size:0.72rem;
    text-transform:uppercase;
    letter-spacing:0.08em;
    color:{C["muted"]};
    margin-top:0.25rem;
    font-weight:700;
}}

.kpi-card .sub {{
    font-size:0.78rem;
    color:{C["rosewood"]};
    margin-top:0.2rem;
}}

.sec-title {{
    font-family:'Fraunces',serif;
    color:{C["text"]};
    font-size:1.28rem;
    margin:1.2rem 0 0.7rem;
    padding-left:0.8rem;
    border-left:5px solid {C["gold"]};
}}

.info-box {{
    background:{C["panel_2"]};
    border:1px solid {C["line"]};
    border-radius:14px;
    padding:0.9rem 1rem;
    color:{C["text"]};
    font-size:0.9rem;
    margin:0.5rem 0 0.9rem;
}}

.pill-ok {{
    background:{C["mint"]};
    color:{C["text"]};
    padding:0.28rem 0.85rem;
    border-radius:999px;
    font-size:0.82rem;
    display:inline-block;
    font-weight:600;
}}

.pill-warn {{
    background:{C["pink"]};
    color:{C["text"]};
    padding:0.28rem 0.85rem;
    border-radius:999px;
    font-size:0.82rem;
    display:inline-block;
    font-weight:600;
}}

[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, {C["panel"]} 0%, {C["panel_2"]} 100%) !important;
    border-right: 1px solid {C["line"]};
}}

[data-testid="stSidebar"] * {{
    color: {C["text"]} !important;
}}

.stTabs [data-baseweb="tab"] {{
    font-weight:600;
}}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🥐 Dora del Hoyo")
    st.markdown("*Gemelo Digital v3.0*")
    st.markdown("---")

    st.markdown("### 📅 Horizonte de análisis")
    mes_idx = st.selectbox("Mes", range(12), index=1, format_func=lambda i: MESES_F[i], label_visibility="collapsed")
    meses_pronostico = st.slider("Meses a proyectar", 1, 6, 3)

    st.markdown("### 📈 Demanda")
    factor_demanda = st.slider("Factor de demanda", 0.5, 2.0, 1.0, 0.05)
    participacion_mercado = st.slider("Participación de mercado (%)", 0.01, 0.25, 0.08, 0.01)
    litros_por_unidad = st.slider("Litros por unidad", 0.20, 1.50, 0.50, 0.05)

    st.markdown("### 🧾 Planeación agregada")
    with st.expander("Configurar costos y mano de obra", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            ct = st.number_input("Costo producción (Ct)", value=4310, step=100)
            ht = st.number_input("Costo inventario (Ht)", value=100000, step=5000)
            pit = st.number_input("Costo backlog (PIt)", value=120000, step=5000)
            inv_seg = st.slider("Inventario mínimo relativo", 0.0, 0.30, 0.05, 0.01)
        with col2:
            crt = st.number_input("Costo laboral regular (CRt)", value=11364, step=100)
            cot = st.number_input("Costo hora extra (COt)", value=14205, step=100)
            cwp = st.number_input("Costo contratación (CW+)", value=14204, step=100)
            cwm = st.number_input("Costo despido (CW-)", value=15061, step=100)

    st.markdown("### 👩‍🍳 Estructura operativa")
    col3, col4 = st.columns(2)
    with col3:
        trab = st.number_input("Trabajadores por turno", value=10, step=1)
        turnos_dia = st.number_input("Turnos por día", value=2, step=1)
    with col4:
        horas_turno = st.number_input("Horas por turno", value=8, step=1)
        dias_mes = st.number_input("Días operativos por mes", value=26, step=1)
    eficiencia = st.slider("Eficiencia operativa (%)", 60, 110, 92)
    ausentismo = st.slider("Ausentismo (%)", 0, 20, 4)
    lr_inicial_calc = int(trab * turnos_dia * horas_turno * dias_mes * (eficiencia / 100) * (1 - ausentismo / 100))

    st.markdown("### ⚖️ Desagregación")
    costo_prod_des = st.number_input("Peso costo producción", value=1.0, step=0.1)
    costo_inv_des = st.number_input("Peso costo inventario", value=1.0, step=0.1)

    st.markdown("### 🏭 Simulación")
    cap_horno = st.slider("Hornos activos", 1, 6, 3)
    mezcla_cap = st.slider("Equipos de mezcla", 1, 4, 2)
    dosificado_cap = st.slider("Líneas de dosificado", 1, 4, 2)
    enfriamiento_cap = st.slider("Cámaras de enfriamiento", 1, 6, 4)
    empaque_cap = st.slider("Estaciones de empaque", 1, 4, 2)
    amasado_cap = st.slider("Puestos de amasado", 1, 3, 1)
    falla_horno = st.checkbox("Simular fallas en horno")
    doble_turno = st.checkbox("Doble turno (−20% tiempo)")
    temp_horno_base = st.slider("Temperatura base horno (°C)", 130, 190, 160)
    iter_sim = st.slider("Iteraciones de simulación", 1, 10, 2)
    semilla = st.number_input("Semilla aleatoria", value=42, step=1)

    st.markdown("### ⏱️ Tiempos de proceso")
    tm = st.slider("Mezcla (min)", 5, 30, (12, 18))
    td = st.slider("Dosificado (min)", 5, 30, (8, 24))
    th = st.slider("Horno (min)", 15, 60, (20, 48))
    te = st.slider("Enfriamiento (min)", 20, 80, (25, 72))
    tep = st.slider("Empaque (min)", 2, 20, (4, 12))
    ta = st.slider("Amasado (min)", 10, 35, (16, 24))

    st.markdown("---")
    st.caption("Panadería artesanal · Dora del Hoyo")


# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(f"""
<div class="hero">
  <h1>Gemelo Digital · Panadería Dora del Hoyo</h1>
  <p>Planeación agregada, desagregación por producto, simulación operativa y análisis de escenarios para una panadería artesanal.</p>
  <span class="badge">📅 {MESES_F[mes_idx]}</span>
  <span class="badge">📈 Demanda ×{factor_demanda:.2f}</span>
  <span class="badge">🔥 Horno {cap_horno} estaciones</span>
  <span class="badge">👩‍🍳 {trab} operarios/turno</span>
  <span class="badge">🛒 Mercado {participacion_mercado:.0%}</span>
  {"<span class='badge'>⚠️ Falla en horno</span>" if falla_horno else ""}
  {"<span class='badge'>🕐 Doble turno</span>" if doble_turno else ""}
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# CÁLCULOS
# ══════════════════════════════════════════════════════════════════════════════
params_custom = {
    **PARAMS_DEFAULT,
    "Ct": ct,
    "CRt": crt,
    "COt": cot,
    "Ht": ht,
    "PIt": pit,
    "CW_mas": cwp,
    "CW_menos": cwm,
    "LR_inicial": lr_inicial_calc,
    "inv_seg": inv_seg,
}

with st.spinner("Optimizando plan agregado..."):
    df_agr, costo = run_agregacion(factor_demanda, tuple(sorted(params_custom.items())))

prod_hh = dict(zip(df_agr["Mes"], df_agr["Produccion_HH"]))

with st.spinner("Desagregando por producto..."):
    desag = run_desagregacion(tuple(prod_hh.items()), factor_demanda, costo_prod_des, costo_inv_des)

mes_nm = MESES[mes_idx]
plan_mes = {p: int(desag[p].loc[desag[p]["Mes"] == mes_nm, "Produccion"].values[0]) for p in PRODUCTOS}
cap_rec = {
    "mezcla": mezcla_cap,
    "dosificado": dosificado_cap,
    "horno": int(cap_horno),
    "enfriamiento": enfriamiento_cap,
    "empaque": empaque_cap,
    "amasado": amasado_cap,
}
factor_t = 0.80 if doble_turno else 1.0

# promediar varias corridas
lotes_runs, uso_runs, sens_runs = [], [], []
for i in range(iter_sim):
    df_l, df_u, df_s = run_simulacion_cached(
        tuple(plan_mes.items()),
        tuple(cap_rec.items()),
        falla_horno,
        factor_t,
        tuple({
            "mezcla": tm,
            "dosificado": td,
            "horno": th,
            "enfriamiento": te,
            "empaque": tep,
            "amasado": ta,
        }.items()),
        temp_horno_base,
        int(semilla) + i,
    )
    if not df_l.empty:
        df_l["iteracion"] = i + 1
        lotes_runs.append(df_l)
    if not df_u.empty:
        df_u["iteracion"] = i + 1
        uso_runs.append(df_u)
    if not df_s.empty:
        df_s["iteracion"] = i + 1
        sens_runs.append(df_s)

df_lotes = pd.concat(lotes_runs, ignore_index=True) if lotes_runs else pd.DataFrame()
df_uso = pd.concat(uso_runs, ignore_index=True) if uso_runs else pd.DataFrame()
df_sensores = pd.concat(sens_runs, ignore_index=True) if sens_runs else pd.DataFrame()

df_kpis = calc_kpis(df_lotes, plan_mes)
df_util = calc_utilizacion(df_uso)

cum_avg = df_kpis["Cumplimiento %"].mean() if not df_kpis.empty else 0
util_max = df_util["Utilizacion_%"].max() if not df_util.empty else 0
lotes_n = len(df_lotes) if not df_lotes.empty else 0
temp_avg = df_sensores["temperatura"].mean() if not df_sensores.empty else 0
excesos = int((df_sensores["temperatura"] > 200).sum()) if not df_sensores.empty else 0
capacidad_laboral = lr_inicial_calc
volumen_litros = sum(plan_mes[p] * litros_por_unidad for p in PRODUCTOS)

PLOT_CFG = dict(
    template="plotly_white",
    font=dict(family="Plus Jakarta Sans", color=C["text"]),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor=C["bg"],
)


# ══════════════════════════════════════════════════════════════════════════════
# KPI SUPERIORES
# ══════════════════════════════════════════════════════════════════════════════
k1, k2, k3, k4, k5, k6 = st.columns(6)


def kpi_card(col, icon, val, lbl, sub=""):
    col.markdown(
        f"""
        <div class="kpi-card">
          <div class="icon">{icon}</div>
          <div class="val">{val}</div>
          <div class="lbl">{lbl}</div>
          {"<div class='sub'>" + sub + "</div>" if sub else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )


kpi_card(k1, "💰", f"${costo/1e6:.1f}M", "Costo óptimo", "Plan anual")
kpi_card(k2, "📦", f"{lotes_n:,}", "Lotes simulados", MESES_F[mes_idx])
kpi_card(k3, "✅", f"{cum_avg:.1f}%", "Cumplimiento", "Producción vs plan")
kpi_card(k4, "⚙️", f"{util_max:.0f}%", "Util. máxima", "Cuello botella" if util_max >= 80 else "Operación estable")
kpi_card(k5, "🌡️", f"{temp_avg:.0f}°C", "Temp. horno", f"{excesos} excesos" if excesos else "Sin excesos")
kpi_card(k6, "🥛", f"{volumen_litros:,.0f}", "Volumen estimado", "litros proyectados")

st.markdown("<br>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tabs = st.tabs([
    "📊 Demanda",
    "📋 Agregación",
    "📦 Desagregación",
    "🏭 Simulación",
    "🌡️ Sensores",
    "🔬 Escenarios",
])


# ────────────────────────────────────────────────────────────────────────────
# TAB 1 · DEMANDA
# ────────────────────────────────────────────────────────────────────────────
with tabs[0]:
    st.markdown('<div class="sec-title">Pronóstico de demanda e históricos</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="info-box">Serie histórica de referencia de Dora del Hoyo con proyección de corto plazo. '
        'La zona sombreada representa el horizonte pronosticado.</div>',
        unsafe_allow_html=True,
    )

    fig_pro = go.Figure()
    for p in PRODUCTOS:
        serie = [v * factor_demanda for v in DEM_HISTORICA[p]]
        suav, futuro = pronostico_simple(serie, meses_pronostico)

        fig_pro.add_trace(go.Scatter(
            x=MESES_ES,
            y=serie,
            mode="lines+markers",
            name=PROD_LABELS[p],
            line=dict(color=PROD_COLORS_DARK[p], width=2.5),
            marker=dict(size=6, color=PROD_COLORS[p], line=dict(color="white", width=1.5)),
            hovertemplate=f"<b>{PROD_LABELS[p]}</b><br>%{{x}}: %{{y:.0f}} und<extra></extra>",
        ))

        meses_fut = [f"P+{j+1}" for j in range(meses_pronostico)]
        x_fut = [MESES_ES[-1]] + meses_fut
        y_fut = [suav[-1]] + futuro

        fig_pro.add_trace(go.Scatter(
            x=x_fut,
            y=y_fut,
            mode="lines+markers",
            showlegend=False,
            line=dict(color=PROD_COLORS_DARK[p], width=2, dash="dot"),
            marker=dict(size=7, color=PROD_COLORS[p], symbol="diamond"),
            hovertemplate=f"<b>{PROD_LABELS[p]} · Pronóstico</b><br>%{{x}}: %{{y:.0f}} und<extra></extra>",
        ))

    fig_pro.add_vrect(
        x0=len(MESES_ES)-0.5,
        x1=len(MESES_ES)+meses_pronostico-0.5,
        fillcolor=hex_rgba(C["lavender"], 0.18),
        line_width=0,
        annotation_text="Zona proyectada",
        annotation_position="top left",
    )
    fig_pro.update_layout(
        **PLOT_CFG,
        height=430,
        title="Pronóstico de Demanda e Históricos",
        xaxis_title="Mes-Año",
        yaxis_title="Demanda esperada",
        legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center"),
        xaxis=dict(showgrid=True, gridcolor=C["line"]),
        yaxis=dict(showgrid=True, gridcolor=C["line"]),
    )
    st.plotly_chart(fig_pro, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown('<div class="sec-title">Estacionalidad por producto</div>', unsafe_allow_html=True)
        z = [[DEM_HISTORICA[p][i] * factor_demanda for i in range(12)] for p in PRODUCTOS]
        fig_heat = go.Figure(go.Heatmap(
            z=z,
            x=MESES_ES,
            y=[PROD_LABELS[p] for p in PRODUCTOS],
            colorscale=[[0, C["bg"]], [0.35, C["butter"]], [0.65, C["peach"]], [1, C["rosewood"]]],
            hovertemplate="%{y}<br>%{x}: %{z:.0f} und<extra></extra>",
        ))
        fig_heat.update_layout(**PLOT_CFG, height=260, margin=dict(t=20, b=10))
        st.plotly_chart(fig_heat, use_container_width=True)

    with col_b:
        st.markdown('<div class="sec-title">Participación anual de productos</div>', unsafe_allow_html=True)
        totales = {p: sum(DEM_HISTORICA[p]) for p in PRODUCTOS}
        fig_pie = go.Figure(go.Pie(
            labels=[PROD_LABELS[p] for p in PRODUCTOS],
            values=list(totales.values()),
            hole=0.58,
            marker=dict(colors=list(PROD_COLORS.values()), line=dict(color="white", width=3)),
        ))
        fig_pie.update_layout(
            **PLOT_CFG,
            height=260,
            annotations=[dict(text="<b>Mix</b><br>anual", x=0.5, y=0.5, showarrow=False, font=dict(color=C["text"], size=12))],
            margin=dict(t=20, b=10),
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown('<div class="sec-title">Demanda agregada en horas-hombre</div>', unsafe_allow_html=True)
    dem_h_vals = demanda_horas_hombre(factor_demanda)
    colores_hh = [C["peach"] if i != mes_idx else C["rosewood"] for i in range(12)]
    fig_hh = go.Figure()
    fig_hh.add_trace(go.Bar(
        x=MESES_ES,
        y=list(dem_h_vals.values()),
        marker_color=colores_hh,
        marker_line_color="white",
        marker_line_width=1.3,
        showlegend=False,
    ))
    fig_hh.add_trace(go.Scatter(
        x=MESES_ES,
        y=list(dem_h_vals.values()),
        mode="lines+markers",
        line=dict(color=C["rosewood"], width=2),
        marker=dict(size=6),
        showlegend=False,
    ))
    fig_hh.update_layout(
        **PLOT_CFG,
        height=280,
        xaxis_title="Mes",
        yaxis_title="H-H",
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor=C["line"]),
        margin=dict(t=15, b=20),
    )
    st.plotly_chart(fig_hh, use_container_width=True)


# ────────────────────────────────────────────────────────────────────────────
# TAB 2 · AGREGACIÓN
# ────────────────────────────────────────────────────────────────────────────
with tabs[1]:
    st.markdown('<div class="sec-title">Planeación agregada</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="info-box"><b>Capacidad laboral efectiva:</b> {capacidad_laboral:,.0f} horas-hombre por periodo · '
        f'{trab} trabajadores/turno · {turnos_dia} turnos/día · {dias_mes} días/mes.</div>',
        unsafe_allow_html=True,
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Costo total", f"${costo:,.0f}")
    m2.metric("Horas extra", f"{df_agr['Horas_Extras'].sum():,.0f} H-H")
    m3.metric("Backlog total", f"{df_agr['Backlog_HH'].sum():,.0f} H-H")
    m4.metric("Inventario final", f"{df_agr['Inv_Fin_HH'].iloc[-1]:,.0f} H-H")

    fig_agr = go.Figure()
    fig_agr.add_trace(go.Bar(
        x=df_agr["Mes_ES"], y=df_agr["Inv_Ini_HH"],
        name="Inventario inicial", marker_color=C["sky"],
        marker_line_color="white", marker_line_width=1
    ))
    fig_agr.add_trace(go.Bar(
        x=df_agr["Mes_ES"], y=df_agr["Produccion_HH"],
        name="Producción", marker_color=C["peach"],
        marker_line_color="white", marker_line_width=1
    ))
    fig_agr.add_trace(go.Scatter(
        x=df_agr["Mes_ES"], y=df_agr["Demanda_HH"],
        mode="lines+markers", name="Demanda",
        line=dict(color=C["rosewood"], width=2.5, dash="dash"),
        marker=dict(size=7)
    ))
    fig_agr.add_trace(go.Scatter(
        x=df_agr["Mes_ES"], y=df_agr["Horas_Regulares"],
        mode="lines", name="Capacidad regular",
        line=dict(color=C["lavender"], width=2, dash="dot")
    ))
    fig_agr.update_layout(
        **PLOT_CFG,
        barmode="stack",
        height=380,
        title="Producción vs demanda agregada",
        xaxis_title="Mes",
        yaxis_title="Horas-hombre",
        legend=dict(orientation="h", y=-0.23, x=0.5, xanchor="center"),
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor=C["line"]),
    )
    st.plotly_chart(fig_agr, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        fig_fl = go.Figure()
        fig_fl.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Contratacion"], name="Contratación", marker_color=C["mint"]))
        fig_fl.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Despidos"], name="Despidos", marker_color=C["pink"]))
        fig_fl.update_layout(
            **PLOT_CFG,
            barmode="group",
            height=290,
            title="Dinámica de fuerza laboral",
            legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
            xaxis=dict(showgrid=False),
            yaxis=dict(gridcolor=C["line"]),
        )
        st.plotly_chart(fig_fl, use_container_width=True)

    with col2:
        fig_ex = go.Figure()
        fig_ex.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Horas_Extras"], name="Horas extra", marker_color=C["butter"]))
        fig_ex.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Backlog_HH"], name="Backlog", marker_color=C["salmon"]))
        fig_ex.update_layout(
            **PLOT_CFG,
            barmode="group",
            height=290,
            title="Horas extra y backlog",
            legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
            xaxis=dict(showgrid=False),
            yaxis=dict(gridcolor=C["line"]),
        )
        st.plotly_chart(fig_ex, use_container_width=True)

    with st.expander("Ver tabla detallada"):
        df_show = df_agr.drop(columns=["Mes", "Mes_ES"]).rename(columns={"Mes_F": "Mes"})
        st.dataframe(df_show, use_container_width=True)


# ────────────────────────────────────────────────────────────────────────────
# TAB 3 · DESAGREGACIÓN
# ────────────────────────────────────────────────────────────────────────────
with tabs[2]:
    st.markdown('<div class="sec-title">Desagregación del plan</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="info-box">Asignación del plan agregado en unidades por referencia. '
        'Los pesos de costo permiten balancear inventario y faltantes sin copiar una interfaz estándar.</div>',
        unsafe_allow_html=True,
    )

    mes_resaltar = st.selectbox("Mes a resaltar", range(12), index=mes_idx, format_func=lambda i: MESES_F[i], key="mes_desag")
    mes_nm_desag = MESES[mes_resaltar]

    fig_des = make_subplots(rows=3, cols=2, subplot_titles=[PROD_LABELS[p] for p in PRODUCTOS], vertical_spacing=0.12, horizontal_spacing=0.08)
    for idx, p in enumerate(PRODUCTOS):
        r, c = idx // 2 + 1, idx % 2 + 1
        df_p = desag[p]
        fig_des.add_trace(go.Bar(
            x=df_p["Mes_ES"], y=df_p["Produccion"],
            marker_color=PROD_COLORS[p], marker_line_color="white", marker_line_width=1,
            opacity=0.92, showlegend=False
        ), row=r, col=c)
        fig_des.add_trace(go.Scatter(
            x=df_p["Mes_ES"], y=df_p["Demanda"],
            mode="lines+markers",
            line=dict(color=PROD_COLORS_DARK[p], width=1.6, dash="dash"),
            marker=dict(size=5), showlegend=False
        ), row=r, col=c)
        mes_row = df_p[df_p["Mes"] == mes_nm_desag]
        if not mes_row.empty:
            fig_des.add_trace(go.Scatter(
                x=[MESES_ES[mes_resaltar]], y=[mes_row["Produccion"].values[0]],
                mode="markers",
                marker=dict(size=14, color=C["rosewood"], symbol="star"),
                showlegend=False,
            ), row=r, col=c)
    fig_des.update_layout(**PLOT_CFG, height=700, title="Producción planificada vs demanda por producto", margin=dict(t=60))
    for i in range(1, 4):
        for j in range(1, 3):
            fig_des.update_xaxes(showgrid=False, row=i, col=j)
            fig_des.update_yaxes(gridcolor=C["line"], row=i, col=j)
    st.plotly_chart(fig_des, use_container_width=True)

    col_cob1, col_cob2 = st.columns([2, 1])
    prods_c, cob_vals, und_prod, und_dem = [], [], [], []
    for p in PRODUCTOS:
        df_p = desag[p]
        tot_p = df_p["Produccion"].sum()
        tot_d = df_p["Demanda"].sum()
        cob = round(min(tot_p / max(tot_d, 1) * 100, 100), 1)
        prods_c.append(PROD_LABELS[p])
        cob_vals.append(cob)
        und_prod.append(int(tot_p))
        und_dem.append(int(tot_d))

    with col_cob1:
        fig_cob = go.Figure(go.Bar(
            y=prods_c,
            x=cob_vals,
            orientation="h",
            marker=dict(color=list(PROD_COLORS.values()), line=dict(color="white", width=2)),
            text=[f"{v:.1f}%" for v in cob_vals],
            textposition="inside",
        ))
        fig_cob.add_vline(x=100, line_dash="dash", line_color=C["rosewood"])
        fig_cob.update_layout(**PLOT_CFG, height=270, xaxis=dict(range=[0, 115], gridcolor=C["line"]), yaxis=dict(showgrid=False), title="Cobertura de demanda anual")
        st.plotly_chart(fig_cob, use_container_width=True)

    with col_cob2:
        df_cob = pd.DataFrame({"Producto": prods_c, "Producido": und_prod, "Demanda": und_dem, "Cob %": cob_vals})
        st.dataframe(df_cob, use_container_width=True, height=270)

    fig_inv = go.Figure()
    for p in PRODUCTOS:
        fig_inv.add_trace(go.Scatter(
            x=desag[p]["Mes_ES"],
            y=desag[p]["Inv_Fin"],
            mode="lines+markers",
            name=PROD_LABELS[p],
            line=dict(color=PROD_COLORS_DARK[p], width=2),
            marker=dict(size=7, color=PROD_COLORS[p], line=dict(color=PROD_COLORS_DARK[p], width=1.4)),
            fill="tozeroy",
            fillcolor=hex_rgba(PROD_COLORS[p], 0.16),
        ))
    fig_inv.update_layout(
        **PLOT_CFG,
        height=300,
        title="Inventario final proyectado",
        xaxis_title="Mes",
        yaxis_title="Unidades",
        legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center"),
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor=C["line"]),
    )
    st.plotly_chart(fig_inv, use_container_width=True)


# ────────────────────────────────────────────────────────────────────────────
# TAB 4 · SIMULACIÓN
# ────────────────────────────────────────────────────────────────────────────
with tabs[3]:
    st.markdown(f'<div class="sec-title">Simulación operativa · {MESES_F[mes_idx]}</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="info-box">Modelo SimPy ajustado a la lógica de Dora del Hoyo: mezcla, dosificado, horneo, enfriamiento y empaque. '
        'La visualización incluye flujo de lotes, cumplimiento y saturación operativa.</div>',
        unsafe_allow_html=True,
    )

    cols_p = st.columns(5)
    for i, (p, u) in enumerate(plan_mes.items()):
        hh_req = round(u * HORAS_PRODUCTO[p], 1)
        cols_p[i].markdown(
            f"""
            <div class="kpi-card" style="background:{hex_rgba(PROD_COLORS[p],0.26)};border-color:{PROD_COLORS_DARK[p]}">
              <div class="icon">{EMOJIS[p]}</div>
              <div class="val" style="font-size:1.45rem">{u:,}</div>
              <div class="lbl">{PROD_LABELS[p]}</div>
              <div class="sub">{hh_req} H-H</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    if not df_kpis.empty:
        fig_cum = go.Figure()
        for i, row in df_kpis.iterrows():
            p_key = next((p for p in PRODUCTOS if PROD_LABELS[p] == row["Producto"]), PRODUCTOS[i % len(PRODUCTOS)])
            fig_cum.add_trace(go.Bar(
                x=[row["Cumplimiento %"]], y=[row["Producto"]], orientation="h",
                marker=dict(color=PROD_COLORS[p_key], line=dict(color=PROD_COLORS_DARK[p_key], width=1.4)),
                text=f"{row['Cumplimiento %']:.1f}%", textposition="inside", showlegend=False,
            ))
        fig_cum.add_vline(x=100, line_dash="dash", line_color=C["rosewood"])
        fig_cum.update_layout(**PLOT_CFG, height=260, title="Cumplimiento del plan por producto", xaxis=dict(range=[0, 115], gridcolor=C["line"]), yaxis=dict(showgrid=False))
        st.plotly_chart(fig_cum, use_container_width=True)

        col_t1, col_t2 = st.columns(2)
        prods_kpi = list(df_kpis["Producto"].values)
        colores_kpi = [PROD_COLORS[next((p for p in PRODUCTOS if PROD_LABELS[p] == prod), PRODUCTOS[0])] for prod in prods_kpi]
        with col_t1:
            fig_tp = go.Figure(go.Bar(
                x=prods_kpi, y=df_kpis["Throughput (und/h)"].values,
                marker_color=colores_kpi, marker_line_color="white", marker_line_width=2,
                text=[f"{v:.1f}" for v in df_kpis["Throughput (und/h)"].values], textposition="outside",
            ))
            fig_tp.update_layout(**PLOT_CFG, height=280, title="Throughput por producto", xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]), showlegend=False)
            st.plotly_chart(fig_tp, use_container_width=True)

        with col_t2:
            fig_lt = go.Figure(go.Bar(
                x=prods_kpi, y=df_kpis["Lead Time (min/lote)"].values,
                marker_color=[PROD_COLORS_DARK[next((p for p in PRODUCTOS if PROD_LABELS[p] == prod), PRODUCTOS[0])] for prod in prods_kpi],
                marker_line_color="white", marker_line_width=2,
                text=[f"{v:.0f}" for v in df_kpis["Lead Time (min/lote)"].values], textposition="outside",
            ))
            fig_lt.update_layout(**PLOT_CFG, height=280, title="Lead time por producto", xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]), showlegend=False)
            st.plotly_chart(fig_lt, use_container_width=True)

    if not df_util.empty:
        st.markdown('<div class="sec-title">Utilización de recursos</div>', unsafe_allow_html=True)
        cuellos = df_util[df_util["Cuello Botella"]]
        if not cuellos.empty:
            for _, row in cuellos.iterrows():
                st.markdown(
                    f'<div class="pill-warn">⚠️ {REC_LABELS.get(row["Recurso"], row["Recurso"])} · {row["Utilizacion_%"]:.1f}% · Cola {row["Cola Prom"]:.2f}</div><br>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown('<div class="pill-ok">✅ Sin cuellos de botella críticos</div><br>', unsafe_allow_html=True)

        rec_lb = [REC_LABELS.get(r, r) for r in df_util["Recurso"]]
        col_util = [C["pink"] if u >= 80 else C["butter"] if u >= 60 else C["mint"] for u in df_util["Utilizacion_%"]]
        fig_util_g = make_subplots(rows=1, cols=2, subplot_titles=["Utilización (%)", "Cola promedio"])
        fig_util_g.add_trace(go.Bar(x=rec_lb, y=df_util["Utilizacion_%"], marker_color=col_util, text=[f"{v:.0f}%" for v in df_util["Utilizacion_%"]], textposition="outside", showlegend=False), row=1, col=1)
        fig_util_g.add_trace(go.Bar(x=rec_lb, y=df_util["Cola Prom"], marker_color=C["lavender"], text=[f"{v:.2f}" for v in df_util["Cola Prom"]], textposition="outside", showlegend=False), row=1, col=2)
        fig_util_g.add_hline(y=80, line_dash="dash", line_color=C["rosewood"], row=1, col=1)
        fig_util_g.update_layout(**PLOT_CFG, height=320)
        fig_util_g.update_xaxes(showgrid=False)
        fig_util_g.update_yaxes(gridcolor=C["line"])
        st.plotly_chart(fig_util_g, use_container_width=True)

    if not df_lotes.empty:
        fig_gantt = go.Figure()
        sub = df_lotes.head(min(60, len(df_lotes))).reset_index(drop=True)
        for _, row in sub.iterrows():
            fig_gantt.add_trace(go.Bar(
                x=[row["tiempo_sistema"]], y=[row["lote_id"]], base=[row["t_creacion"]],
                orientation="h", marker_color=PROD_COLORS.get(row["producto"], "#ccc"),
                marker_line_color="white", marker_line_width=0.5, opacity=0.88, showlegend=False,
            ))
        for p, c in PROD_COLORS.items():
            fig_gantt.add_trace(go.Bar(x=[None], y=[None], marker_color=c, name=PROD_LABELS[p]))
        fig_gantt.update_layout(
            **PLOT_CFG,
            barmode="overlay",
            height=max(380, len(sub) * 8),
            title="Gantt de lotes simulados",
            xaxis_title="Tiempo simulado (min)",
            legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"),
            yaxis=dict(showticklabels=False),
        )
        st.plotly_chart(fig_gantt, use_container_width=True)

        fig_burb = go.Figure()
        for p in PRODUCTOS:
            subp = df_lotes[df_lotes["producto"] == p]
            if subp.empty:
                continue
            fig_burb.add_trace(go.Scatter(
                x=subp["t_creacion"],
                y=subp["tiempo_sistema"],
                mode="markers",
                name=PROD_LABELS[p],
                marker=dict(size=np.clip(subp["tamano"], 8, 24), color=PROD_COLORS[p], line=dict(color=PROD_COLORS_DARK[p], width=1.2), opacity=0.75),
                hovertemplate=f"<b>{PROD_LABELS[p]}</b><br>Inicio: %{{x:.1f}} min<br>Tiempo sistema: %{{y:.1f}} min<extra></extra>",
            ))
        fig_burb.update_layout(
            **PLOT_CFG,
            height=330,
            title="Mapa de lotes: liberación vs tiempo en sistema",
            xaxis_title="Tiempo de liberación (min)",
            yaxis_title="Tiempo total en sistema (min)",
            legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center"),
            xaxis=dict(gridcolor=C["line"]),
            yaxis=dict(gridcolor=C["line"]),
        )
        st.plotly_chart(fig_burb, use_container_width=True)

        fig_violin = go.Figure()
        for p in PRODUCTOS:
            sub_v = df_lotes[df_lotes["producto"] == p]["tiempo_sistema"]
            if len(sub_v) < 3:
                continue
            fig_violin.add_trace(go.Violin(
                y=sub_v,
                name=PROD_LABELS[p],
                box_visible=True,
                meanline_visible=True,
                fillcolor=PROD_COLORS[p],
                line_color=PROD_COLORS_DARK[p],
                opacity=0.8,
            ))
        fig_violin.update_layout(**PLOT_CFG, height=320, title="Distribución de tiempos en sistema", yaxis_title="Minutos", showlegend=False)
        st.plotly_chart(fig_violin, use_container_width=True)

        with st.expander("Ver KPIs detallados"):
            st.dataframe(df_kpis, use_container_width=True)


# ────────────────────────────────────────────────────────────────────────────
# TAB 5 · SENSORES
# ────────────────────────────────────────────────────────────────────────────
with tabs[4]:
    st.markdown('<div class="sec-title">Sensores virtuales del horno</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="info-box">La temperatura del horno se simula según ocupación y ruido operacional. '
        'Se monitorea la temperatura, la ocupación y la distribución térmica del proceso.</div>',
        unsafe_allow_html=True,
    )

    if not df_sensores.empty:
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Temp. mínima", f"{df_sensores['temperatura'].min():.1f} °C")
        s2.metric("Temp. máxima", f"{df_sensores['temperatura'].max():.1f} °C")
        s3.metric("Temp. promedio", f"{df_sensores['temperatura'].mean():.1f} °C")
        s4.metric("Excesos >200°C", excesos)

        fig_temp = go.Figure()
        fig_temp.add_hrect(y0=150, y1=200, fillcolor=hex_rgba(C["mint"], 0.21), line_width=0)
        fig_temp.add_trace(go.Scatter(
            x=df_sensores["tiempo"], y=df_sensores["temperatura"],
            mode="lines", name="Temperatura",
            fill="tozeroy", fillcolor=hex_rgba(C["salmon"], 0.15), line=dict(color=C["rosewood"], width=1.8),
        ))
        if len(df_sensores) > 10:
            mm = df_sensores["temperatura"].rolling(5, min_periods=1).mean()
            fig_temp.add_trace(go.Scatter(x=df_sensores["tiempo"], y=mm, mode="lines", name="Media móvil", line=dict(color=C["lavender"], width=2, dash="dot")))
        fig_temp.add_hline(y=200, line_dash="dash", line_color="#C0392B")
        fig_temp.update_layout(**PLOT_CFG, height=320, title="Temperatura del horno", xaxis_title="Tiempo simulado", yaxis_title="°C", legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center"), xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]))
        st.plotly_chart(fig_temp, use_container_width=True)

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            fig_ocup = go.Figure()
            fig_ocup.add_trace(go.Scatter(
                x=df_sensores["tiempo"], y=df_sensores["horno_ocup"], mode="lines",
                fill="tozeroy", fillcolor=hex_rgba(C["sky"], 0.25), line=dict(color=PROD_COLORS_DARK["Mantecadas"], width=2),
            ))
            fig_ocup.add_hline(y=cap_horno, line_dash="dot", line_color=C["rosewood"])
            fig_ocup.update_layout(**PLOT_CFG, height=260, title="Ocupación del horno", xaxis_title="Tiempo", yaxis_title="Estaciones", showlegend=False, xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]))
            st.plotly_chart(fig_ocup, use_container_width=True)

        with col_s2:
            fig_hist = go.Figure(go.Histogram(
                x=df_sensores["temperatura"], nbinsx=35,
                marker_color=C["peach"], marker_line_color="white", marker_line_width=1,
            ))
            fig_hist.add_vline(x=200, line_dash="dash", line_color="#C0392B")
            fig_hist.update_layout(**PLOT_CFG, height=260, title="Distribución de temperatura", xaxis_title="°C", yaxis_title="Frecuencia", showlegend=False, xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]))
            st.plotly_chart(fig_hist, use_container_width=True)
    else:
        st.info("No hay datos de sensores para mostrar.")


# ────────────────────────────────────────────────────────────────────────────
# TAB 6 · ESCENARIOS
# ────────────────────────────────────────────────────────────────────────────
with tabs[5]:
    st.markdown('<div class="sec-title">Escenarios what-if</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="info-box">Comparación de estrategias operativas para Dora del Hoyo. '
        'Se contrastan demanda, capacidad, fallas y tiempos de procesamiento.</div>',
        unsafe_allow_html=True,
    )

    ESCENARIOS_DEF = {
        "Base": {"fd": 1.0, "falla": False, "ft": 1.0, "cap_delta": 0},
        "Demanda +20%": {"fd": 1.2, "falla": False, "ft": 1.0, "cap_delta": 0},
        "Demanda -20%": {"fd": 0.8, "falla": False, "ft": 1.0, "cap_delta": 0},
        "Falla horno": {"fd": 1.0, "falla": True, "ft": 1.0, "cap_delta": 0},
        "Horno adicional": {"fd": 1.0, "falla": False, "ft": 1.0, "cap_delta": 1},
        "Capacidad reducida": {"fd": 1.0, "falla": False, "ft": 1.0, "cap_delta": -1},
        "Doble turno": {"fd": 1.0, "falla": False, "ft": 0.80, "cap_delta": 0},
        "Optimizado": {"fd": 1.0, "falla": False, "ft": 0.85, "cap_delta": 1},
    }

    escenarios_sel = st.multiselect(
        "Selecciona escenarios",
        list(ESCENARIOS_DEF.keys()),
        default=["Base", "Demanda +20%", "Falla horno", "Doble turno", "Optimizado"],
    )

    if st.button("Comparar escenarios", type="primary"):
        filas_esc = []
        prog = st.progress(0)
        for i, nm in enumerate(escenarios_sel):
            prog.progress((i + 1) / len(escenarios_sel), text=f"Simulando {nm}...")
            cfg = ESCENARIOS_DEF[nm]
            plan_esc = {p: max(int(u * cfg["fd"]), 0) for p, u in plan_mes.items()}
            cap_esc = {**cap_rec, "horno": max(cap_rec["horno"] + cfg["cap_delta"], 1)}
            df_l, df_u, _ = run_simulacion_cached(
                tuple(plan_esc.items()),
                tuple(cap_esc.items()),
                cfg["falla"],
                cfg["ft"],
                tuple({
                    "mezcla": tm,
                    "dosificado": td,
                    "horno": th,
                    "enfriamiento": te,
                    "empaque": tep,
                    "amasado": ta,
                }.items()),
                temp_horno_base,
                int(semilla) + i + 20,
            )
            k = calc_kpis(df_l, plan_esc)
            u = calc_utilizacion(df_u)
            fila = {"Escenario": nm}
            if not k.empty:
                fila["Throughput (und/h)"] = round(k["Throughput (und/h)"].mean(), 2)
                fila["Lead Time (min)"] = round(k["Lead Time (min/lote)"].mean(), 2)
                fila["WIP Prom"] = round(k["WIP Prom"].mean(), 2)
                fila["Cumplimiento %"] = round(k["Cumplimiento %"].mean(), 2)
            if not u.empty:
                fila["Util. max %"] = round(u["Utilizacion_%"].max(), 2)
                fila["Cuellos botella"] = int(u["Cuello Botella"].sum())
            fila["Lotes prod."] = len(df_l)
            filas_esc.append(fila)
        prog.empty()

        df_comp = pd.DataFrame(filas_esc)
        st.dataframe(df_comp, use_container_width=True)

        if len(df_comp) > 1:
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                if "Cumplimiento %" in df_comp.columns:
                    col_c = [C["mint"] if v >= 90 else C["butter"] if v >= 70 else C["pink"] for v in df_comp["Cumplimiento %"]]
                    fig_ec = go.Figure(go.Bar(
                        x=df_comp["Escenario"], y=df_comp["Cumplimiento %"],
                        marker_color=col_c, marker_line_color="white", marker_line_width=2,
                        text=[f"{v:.1f}%" for v in df_comp["Cumplimiento %"]], textposition="outside",
                    ))
                    fig_ec.add_hline(y=100, line_dash="dash", line_color=C["rosewood"])
                    fig_ec.update_layout(**PLOT_CFG, height=300, title="Cumplimiento por escenario", xaxis=dict(showgrid=False, tickangle=-25), yaxis=dict(gridcolor=C["line"]), showlegend=False, margin=dict(t=30, b=90))
                    st.plotly_chart(fig_ec, use_container_width=True)

            with col_e2:
                if "Util. max %" in df_comp.columns:
                    col_u = [C["pink"] if v >= 80 else C["butter"] if v >= 60 else C["mint"] for v in df_comp["Util. max %"]]
                    fig_eu = go.Figure(go.Bar(
                        x=df_comp["Escenario"], y=df_comp["Util. max %"],
                        marker_color=col_u, marker_line_color="white", marker_line_width=2,
                        text=[f"{v:.0f}%" for v in df_comp["Util. max %"]], textposition="outside",
                    ))
                    fig_eu.add_hline(y=80, line_dash="dash", line_color=C["rosewood"])
                    fig_eu.update_layout(**PLOT_CFG, height=300, title="Utilización máxima", xaxis=dict(showgrid=False, tickangle=-25), yaxis=dict(gridcolor=C["line"]), showlegend=False, margin=dict(t=30, b=90))
                    st.plotly_chart(fig_eu, use_container_width=True)

            cols_radar = [c for c in df_comp.columns if c not in ["Escenario", "Cuellos botella"] and df_comp[c].dtype != "object"]
            if len(cols_radar) >= 3:
                df_norm = df_comp[cols_radar].copy()
                for c in df_norm.columns:
                    rng = df_norm[c].max() - df_norm[c].min()
                    df_norm[c] = (df_norm[c] - df_norm[c].min()) / rng if rng else 0.5

                radar_colors = [C["peach"], C["sky"], C["pink"], C["mint"], C["lavender"], C["salmon"], C["butter"], C["sage"]]
                fig_radar = go.Figure()
                for i, row in df_comp.iterrows():
                    vals = [df_norm.loc[i, c] for c in cols_radar]
                    fig_radar.add_trace(go.Scatterpolar(
                        r=vals + [vals[0]],
                        theta=cols_radar + [cols_radar[0]],
                        fill="toself",
                        name=row["Escenario"],
                        line=dict(color=radar_colors[i % len(radar_colors)], width=2),
                        fillcolor=hex_rgba(radar_colors[i % len(radar_colors)], 0.15),
                    ))
                fig_radar.update_layout(
                    **PLOT_CFG,
                    height=430,
                    title="Radar comparativo de escenarios",
                    polar=dict(radialaxis=dict(visible=True, range=[0, 1], gridcolor=C["line"]), angularaxis=dict(gridcolor=C["line"])),
                    legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"),
                )
                st.plotly_chart(fig_radar, use_container_width=True)

            if "Cumplimiento %" in df_comp.columns and "Lead Time (min)" in df_comp.columns and "Util. max %" in df_comp.columns and "Cuellos botella" in df_comp.columns:
                df_rank = df_comp.copy()
                df_rank["Score"] = (
                    df_rank["Cumplimiento %"] * 0.45
                    + (100 - df_rank["Util. max %"].clip(upper=100)) * 0.20
                    + (100 - df_rank["Lead Time (min)"].rank(pct=True) * 100) * 0.20
                    + (100 - df_rank["Cuellos botella"].rank(pct=True) * 100) * 0.15
                )
                df_rank = df_rank.sort_values("Score", ascending=False).reset_index(drop=True)
                fig_rank = go.Figure(go.Bar(
                    x=df_rank["Score"], y=df_rank["Escenario"], orientation="h",
                    marker=dict(color=[C["mint"], C["sky"], C["lavender"], C["peach"], C["pink"]][:len(df_rank)], line=dict(color="white", width=2)),
                    text=[f"{v:.1f}" for v in df_rank["Score"]], textposition="outside",
                ))
                fig_rank.update_layout(**PLOT_CFG, height=320, title="Ranking integral de escenarios", xaxis_title="Score compuesto", yaxis=dict(autorange="reversed", showgrid=False), xaxis=dict(gridcolor=C["line"]), showlegend=False)
                st.plotly_chart(fig_rank, use_container_width=True)
    else:
        st.markdown(
            '<div class="info-box" style="text-align:center;padding:2rem;">'
            '<div style="font-size:2rem">🔬</div>'
            '<b>Selecciona escenarios y presiona comparar</b><br>'
            'La app simulará cada alternativa y mostrará KPIs, radar y ranking.'
            '</div>',
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown(
    """
    <div style='text-align:center;color:#8C7B70;font-size:0.82rem;padding:0.3rem 0 1rem'>
      🥐 <b>Gemelo Digital · Panadería Dora del Hoyo</b> · Planeación agregada · Desagregación · Simulación · Escenarios
    </div>
    """,
    unsafe_allow_html=True,
)
