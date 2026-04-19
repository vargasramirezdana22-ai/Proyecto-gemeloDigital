"""
app.py  —  Gemelo Digital · Panadería Dora del Hoyo
====================================================
Versión 3.1
- Estilo pastel más propio y menos parecido a referencias externas
- Parámetros generales en barra lateral
- Parámetros específicos dentro de cada sección funcional
- Pronóstico, agregación, desagregación, simulación, sensores y escenarios

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
    "bg": "#FFFDF8",
    "panel": "#FFFFFF",
    "panel_2": "#FFF7F1",
    "text": "#46352A",
    "muted": "#8C7B70",
    "line": "#EADFD7",
    "pink": "#F6C9D0",
    "peach": "#FFD7BA",
    "butter": "#FCE7A8",
    "mint": "#CFE9D9",
    "sky": "#CFE4F6",
    "lavender": "#DDD2F4",
    "salmon": "#F7B7A3",
    "sage": "#BFD8C1",
    "rosewood": "#B9857E",
    "gold": "#E8C27A",
    "coffee": "#8B5E3C",
}

PROD_COLORS = {
    "Brownies": "#D9B38C",
    "Mantecadas": "#CFE4F6",
    "Mantecadas_Amapola": "#CFE9D9",
    "Torta_Naranja": "#F6D0E6",
    "Pan_Maiz": "#FFD7BA",
}
PROD_COLORS_DARK = {
    "Brownies": "#9B7452",
    "Mantecadas": "#6B9CC9",
    "Mantecadas_Amapola": "#6FA889",
    "Torta_Naranja": "#A77DBA",
    "Pan_Maiz": "#D98E68",
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
    "Brownies": [315, 804, 734, 541, 494, 59, 315, 803, 734, 541, 494, 59],
    "Mantecadas": [125, 780, 432, 910, 275, 68, 512, 834, 690, 455, 389, 120],
    "Mantecadas_Amapola": [320, 710, 520, 251, 631, 150, 330, 220, 710, 610, 489, 180],
    "Torta_Naranja": [100, 250, 200, 101, 190, 50, 100, 220, 200, 170, 180, 187],
    "Pan_Maiz": [330, 140, 143, 73, 83, 48, 70, 89, 118, 83, 67, 87],
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
# ESTADO · VALORES INICIALES
# ══════════════════════════════════════════════════════════════════════════════
DEFAULTS = {
    "mes_idx": 1,
    "factor_demanda": 1.0,
    "meses_pronostico": 3,
    "participacion_mercado": 0.08,
    "litros_por_unidad": 0.50,
    "semilla": 42,
    "ct": 4310,
    "ht": 100000,
    "pit": 120000,
    "inv_seg": 0.05,
    "crt": 11364,
    "cot": 14205,
    "cwp": 14204,
    "cwm": 15061,
    "trab": 10,
    "turnos_dia": 2,
    "horas_turno": 8,
    "dias_mes": 26,
    "eficiencia": 92,
    "ausentismo": 4,
    "costo_prod_des": 1.0,
    "costo_inv_des": 1.0,
    "cap_horno": 3,
    "mezcla_cap": 2,
    "dosificado_cap": 2,
    "enfriamiento_cap": 4,
    "empaque_cap": 2,
    "amasado_cap": 1,
    "falla_horno": False,
    "doble_turno": False,
    "temp_horno_base": 160,
    "iter_sim": 2,
    "tm": (12, 18),
    "td": (8, 24),
    "th": (20, 48),
    "te": (25, 72),
    "tep": (4, 12),
    "ta": (16, 24),
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


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
html, body, [class*="css"] {{font-family:'Plus Jakarta Sans',sans-serif; background:{C["bg"]};}}
.block-container {{padding-top: 1.2rem; padding-bottom: 1.5rem;}}
.hero {{background: linear-gradient(135deg, {C["lavender"]} 0%, {C["sky"]} 35%, {C["peach"]} 100%); padding: 2rem 2.2rem 1.6rem; border-radius: 24px; margin-bottom: 1.2rem; border: 1px solid {C["line"]}; box-shadow: 0 12px 28px rgba(120,100,90,0.10);}}
.hero h1 {{font-family:'Fraunces',serif; color:{C["text"]}; font-size:2.1rem; margin:0;}}
.hero p {{color:{C["muted"]}; margin:0.45rem 0 0; font-size:0.95rem;}}
.hero .badge {{display:inline-block; background: rgba(255,255,255,0.75); color:{C["text"]}; padding:0.28rem 0.8rem; border-radius:999px; font-size:0.75rem; margin-top:0.8rem; margin-right:0.35rem; border:1px solid {C["line"]};}}
.kpi-card {{background:{C["panel"]}; border-radius:18px; padding:1rem 1rem; border:1px solid {C["line"]}; box-shadow:0 6px 18px rgba(120,100,90,0.07); text-align:center;}}
.kpi-card .icon {{font-size:1.55rem; margin-bottom:0.2rem;}}
.kpi-card .val {{font-family:'Fraunces',serif; font-size:1.65rem; color:{C["text"]}; line-height:1;}}
.kpi-card .lbl {{font-size:0.72rem; text-transform:uppercase; letter-spacing:0.08em; color:{C["muted"]}; margin-top:0.25rem; font-weight:700;}}
.kpi-card .sub {{font-size:0.78rem; color:{C["rosewood"]}; margin-top:0.2rem;}}
.sec-title {{font-family:'Fraunces',serif; color:{C["text"]}; font-size:1.28rem; margin:1.2rem 0 0.7rem; padding-left:0.8rem; border-left:5px solid {C["gold"]};}}
.info-box {{background:{C["panel_2"]}; border:1px solid {C["line"]}; border-radius:14px; padding:0.9rem 1rem; color:{C["text"]}; font-size:0.9rem; margin:0.5rem 0 0.9rem;}}
.pill-ok {{background:{C["mint"]}; color:{C["text"]}; padding:0.28rem 0.85rem; border-radius:999px; font-size:0.82rem; display:inline-block; font-weight:600;}}
.pill-warn {{background:{C["pink"]}; color:{C["text"]}; padding:0.28rem 0.85rem; border-radius:999px; font-size:0.82rem; display:inline-block; font-weight:600;}}
[data-testid="stSidebar"] {{background: linear-gradient(180deg, #fffaf3 0%, #fff3eb 100%) !important; border-right: 1px solid {C["line"]};}}
[data-testid="stSidebar"] * {{color: {C["text"]} !important;}}
.stTabs [data-baseweb="tab"] {{font-weight:600;}}
.sticky-top-wrap {{
    position: sticky;
    top: 0.5rem;
    z-index: 999;
    background: {C["bg"]};
    padding-top: 0.2rem;
    padding-bottom: 0.6rem;
}}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR · SOLO GENERALES
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🥐 Dora del Hoyo")
    st.markdown("*Gemelo Digital v3.1*")
    st.markdown("### Parámetros generales")
    st.session_state["mes_idx"] = st.selectbox(
        "Mes de análisis",
        range(12),
        index=st.session_state["mes_idx"],
        format_func=lambda i: MESES_F[i],
    )
    st.session_state["factor_demanda"] = st.slider("Impulso de demanda", 0.5, 2.0, st.session_state["factor_demanda"], 0.05)
    st.session_state["meses_pronostico"] = st.slider("Horizonte de proyección", 1, 6, st.session_state["meses_pronostico"])
    st.session_state["participacion_mercado"] = st.slider("Cobertura comercial (%)", 0.01, 0.25, st.session_state["participacion_mercado"], 0.01)
    st.session_state["litros_por_unidad"] = st.slider("Volumen por unidad", 0.20, 1.50, st.session_state["litros_por_unidad"], 0.05)
    st.session_state["semilla"] = st.number_input("Semilla aleatoria", value=st.session_state["semilla"], step=1)
    st.caption("Los demás parámetros viven dentro de cada sección funcional.")

# tabs primero para capturar widgets por sección
PLOT_CFG = dict(
    template="plotly_white",
    font=dict(family="Plus Jakarta Sans", color=C["text"]),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor=C["bg"],
)

tabs = st.tabs([
    "📊 Demanda",
    "📋 Agregación",
    "📦 Desagregación",
    "🏭 Simulación",
    "🌡️ Sensores",
    "🔬 Escenarios",
])

# parámetros por sección
with tabs[1]:
    st.markdown('<div class="sec-title">Configuración de planeación agregada</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Aquí se ajustan únicamente los costos y la estructura laboral que impactan la optimización agregada.</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    st.session_state["ct"] = c1.number_input("Costo de producción (Ct)", value=st.session_state["ct"], step=100)
    st.session_state["ht"] = c2.number_input("Costo de inventario (Ht)", value=st.session_state["ht"], step=5000)
    st.session_state["pit"] = c3.number_input("Costo de diferimiento (PIt)", value=st.session_state["pit"], step=5000)
    st.session_state["inv_seg"] = c4.slider("Reserva mínima", 0.0, 0.30, st.session_state["inv_seg"], 0.01)

    c5, c6, c7, c8 = st.columns(4)
    st.session_state["crt"] = c5.number_input("Costo regular (CRt)", value=st.session_state["crt"], step=100)
    st.session_state["cot"] = c6.number_input("Costo extra (COt)", value=st.session_state["cot"], step=100)
    st.session_state["cwp"] = c7.number_input("Costo contratación", value=st.session_state["cwp"], step=100)
    st.session_state["cwm"] = c8.number_input("Costo desvinculación", value=st.session_state["cwm"], step=100)

    c9, c10, c11, c12 = st.columns(4)
    st.session_state["trab"] = c9.number_input("Operarios por turno", value=st.session_state["trab"], step=1)
    st.session_state["turnos_dia"] = c10.number_input("Turnos diarios", value=st.session_state["turnos_dia"], step=1)
    st.session_state["horas_turno"] = c11.number_input("Horas por turno", value=st.session_state["horas_turno"], step=1)
    st.session_state["dias_mes"] = c12.number_input("Días hábiles del mes", value=st.session_state["dias_mes"], step=1)

    c13, c14 = st.columns(2)
    st.session_state["eficiencia"] = c13.slider("Rendimiento operativo (%)", 60, 110, st.session_state["eficiencia"])
    st.session_state["ausentismo"] = c14.slider("Ausencia de personal (%)", 0, 20, st.session_state["ausentismo"])

with tabs[2]:
    st.markdown('<div class="sec-title">Ajuste del reparto por producto</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Estos pesos alteran cómo se reparte la producción entre referencias cuando se balancea inventario y faltantes.</div>', unsafe_allow_html=True)
    d1, d2 = st.columns(2)
    st.session_state["costo_prod_des"] = d1.number_input("Peso de faltante", value=st.session_state["costo_prod_des"], step=0.1)
    st.session_state["costo_inv_des"] = d2.number_input("Peso de inventario", value=st.session_state["costo_inv_des"], step=0.1)

with tabs[3]:
    st.markdown('<div class="sec-title">Ajuste operativo de la simulación</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Aquí viven únicamente las variables de planta: estaciones, tiempos, fallas y comportamiento del horno.</div>', unsafe_allow_html=True)
    s1, s2, s3, s4, s5, s6 = st.columns(6)
    st.session_state["mezcla_cap"] = s1.number_input("Mezcla", value=st.session_state["mezcla_cap"], step=1)
    st.session_state["dosificado_cap"] = s2.number_input("Dosificado", value=st.session_state["dosificado_cap"], step=1)
    st.session_state["cap_horno"] = s3.number_input("Hornos", value=st.session_state["cap_horno"], step=1)
    st.session_state["enfriamiento_cap"] = s4.number_input("Enfriamiento", value=st.session_state["enfriamiento_cap"], step=1)
    st.session_state["empaque_cap"] = s5.number_input("Empaque", value=st.session_state["empaque_cap"], step=1)
    st.session_state["amasado_cap"] = s6.number_input("Amasado", value=st.session_state["amasado_cap"], step=1)

    s7, s8, s9, s10 = st.columns(4)
    st.session_state["falla_horno"] = s7.checkbox("Activar fallas en horno", value=st.session_state["falla_horno"])
    st.session_state["doble_turno"] = s8.checkbox("Ritmo extendido", value=st.session_state["doble_turno"])
    st.session_state["temp_horno_base"] = s9.slider("Base térmica (°C)", 130, 190, st.session_state["temp_horno_base"])
    st.session_state["iter_sim"] = s10.slider("Corridas a promediar", 1, 10, st.session_state["iter_sim"])

    st.markdown("**Ventanas de proceso (minutos)**")
    s11, s12, s13 = st.columns(3)
    st.session_state["tm"] = s11.slider("Mezcla", 5, 30, st.session_state["tm"])
    st.session_state["td"] = s12.slider("Dosificado", 5, 30, st.session_state["td"])
    st.session_state["th"] = s13.slider("Horneo", 15, 60, st.session_state["th"])
    s14, s15, s16 = st.columns(3)
    st.session_state["te"] = s14.slider("Enfriado", 20, 80, st.session_state["te"])
    st.session_state["tep"] = s15.slider("Empaque", 2, 20, st.session_state["tep"])
    st.session_state["ta"] = s16.slider("Amasado", 10, 35, st.session_state["ta"])

# tomar valores del estado
mes_idx = int(st.session_state["mes_idx"])
factor_demanda = float(st.session_state["factor_demanda"])
meses_pronostico = int(st.session_state["meses_pronostico"])
participacion_mercado = float(st.session_state["participacion_mercado"])
litros_por_unidad = float(st.session_state["litros_por_unidad"])
semilla = int(st.session_state["semilla"])

ct = st.session_state["ct"]
ht = st.session_state["ht"]
pit = st.session_state["pit"]
inv_seg = st.session_state["inv_seg"]
crt = st.session_state["crt"]
cot = st.session_state["cot"]
cwp = st.session_state["cwp"]
cwm = st.session_state["cwm"]
trab = st.session_state["trab"]
turnos_dia = st.session_state["turnos_dia"]
horas_turno = st.session_state["horas_turno"]
dias_mes = st.session_state["dias_mes"]
eficiencia = st.session_state["eficiencia"]
ausentismo = st.session_state["ausentismo"]

costo_prod_des = st.session_state["costo_prod_des"]
costo_inv_des = st.session_state["costo_inv_des"]

mezcla_cap = int(st.session_state["mezcla_cap"])
dosificado_cap = int(st.session_state["dosificado_cap"])
cap_horno = int(st.session_state["cap_horno"])
enfriamiento_cap = int(st.session_state["enfriamiento_cap"])
empaque_cap = int(st.session_state["empaque_cap"])
amasado_cap = int(st.session_state["amasado_cap"])
falla_horno = bool(st.session_state["falla_horno"])
doble_turno = bool(st.session_state["doble_turno"])
temp_horno_base = int(st.session_state["temp_horno_base"])
iter_sim = int(st.session_state["iter_sim"])
tm = st.session_state["tm"]
td = st.session_state["td"]
th = st.session_state["th"]
te = st.session_state["te"]
tep = st.session_state["tep"]
ta = st.session_state["ta"]

# cálculos globales compartidos
lr_inicial_calc = int(trab * turnos_dia * horas_turno * dias_mes * (eficiencia / 100) * (1 - ausentismo / 100))
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
    "horno": cap_horno,
    "enfriamiento": enfriamiento_cap,
    "empaque": empaque_cap,
    "amasado": amasado_cap,
}
factor_t = 0.80 if doble_turno else 1.0

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
        semilla + i,
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

# encabezado y kpis
st.markdown('<div class="sticky-top-wrap">', unsafe_allow_html=True)

st.markdown(f"""
<div class="hero">
  <h1>Gemelo Digital · Panadería Dora del Hoyo</h1>
  <p>Planeación, simulación y decisión operativa para una panadería artesanal con estética propia y parámetros organizados por función.</p>
  <span class="badge">📅 {MESES_F[mes_idx]}</span>
  <span class="badge">📈 Impulso x{factor_demanda:.2f}</span>
  <span class="badge">🥛 {volumen_litros:,.0f} litros estimados</span>
  <span class="badge">👩‍🍳 {trab} operarios por turno</span>
  {"<span class='badge'>⚠️ Horno inestable</span>" if falla_horno else ""}
  {"<span class='badge'>🕐 Ritmo extendido</span>" if doble_turno else ""}
</div>
""", unsafe_allow_html=True)

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

kpi_card(k1, "💰", f"${costo/1e6:.1f}M", "Costo óptimo", "plan anual")
kpi_card(k2, "📦", f"{lotes_n:,}", "Lotes simulados", MESES_F[mes_idx])
kpi_card(k3, "✅", f"{cum_avg:.1f}%", "Cumplimiento", "contra plan")
kpi_card(k4, "⚙️", f"{util_max:.0f}%", "Utilización pico", "vigilar" if util_max >= 80 else "estable")
kpi_card(k5, "🌡️", f"{temp_avg:.0f}°C", "Promedio térmico", f"{excesos} alarmas" if excesos else "sin alertas")
kpi_card(k6, "👩‍🍳", f"{capacidad_laboral:,.0f}", "Capacidad HH", "mes efectivo")

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────────────────────
# TAB 1 · DEMANDA
# ────────────────────────────────────────────────────────────────────────────
with tabs[0]:
    st.markdown('<div class="sec-title">Comportamiento de la demanda</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Se muestran históricos y proyección de corto plazo, con énfasis en la lectura comercial y no solo estadística.</div>', unsafe_allow_html=True)

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
        ))
        meses_fut = [f"P+{j+1}" for j in range(meses_pronostico)]
        fig_pro.add_trace(go.Scatter(
            x=[MESES_ES[-1]] + meses_fut,
            y=[suav[-1]] + futuro,
            mode="lines+markers",
            showlegend=False,
            line=dict(color=PROD_COLORS_DARK[p], width=2, dash="dot"),
            marker=dict(size=7, color=PROD_COLORS[p], symbol="diamond"),
        ))
    fig_pro.add_vrect(x0=len(MESES_ES)-0.5, x1=len(MESES_ES)+meses_pronostico-0.5, fillcolor=hex_rgba(C["lavender"], 0.18), line_width=0, annotation_text="proyección", annotation_position="top left")
    fig_pro.update_layout(**PLOT_CFG, height=430, title="Demanda histórica y horizonte proyectado", xaxis_title="Mes", yaxis_title="Unidades estimadas", legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center"), xaxis=dict(showgrid=True, gridcolor=C["line"]), yaxis=dict(showgrid=True, gridcolor=C["line"]))
    st.plotly_chart(fig_pro, use_container_width=True)

    a, b = st.columns(2)
    with a:
        z = [[DEM_HISTORICA[p][i] * factor_demanda for i in range(12)] for p in PRODUCTOS]
        fig_heat = go.Figure(go.Heatmap(z=z, x=MESES_ES, y=[PROD_LABELS[p] for p in PRODUCTOS], colorscale=[[0, C["bg"]], [0.35, C["butter"]], [0.65, C["peach"]], [1, C["rosewood"]]]))
        fig_heat.update_layout(**PLOT_CFG, height=260, title="Mapa estacional")
        st.plotly_chart(fig_heat, use_container_width=True)
    with b:
        totales = {p: sum(DEM_HISTORICA[p]) for p in PRODUCTOS}
        fig_pie = go.Figure(go.Pie(labels=[PROD_LABELS[p] for p in PRODUCTOS], values=list(totales.values()), hole=0.58, marker=dict(colors=list(PROD_COLORS.values()), line=dict(color="white", width=3))))
        fig_pie.update_layout(**PLOT_CFG, height=260, title="Aporte anual por línea")
        st.plotly_chart(fig_pie, use_container_width=True)

    dem_h_vals = demanda_horas_hombre(factor_demanda)
    fig_hh = go.Figure()
    fig_hh.add_trace(go.Bar(x=MESES_ES, y=list(dem_h_vals.values()), marker_color=[C["peach"] if i != mes_idx else C["rosewood"] for i in range(12)], marker_line_color="white", marker_line_width=1.3))
    fig_hh.add_trace(go.Scatter(x=MESES_ES, y=list(dem_h_vals.values()), mode="lines+markers", line=dict(color=C["rosewood"], width=2), marker=dict(size=6), showlegend=False))
    fig_hh.update_layout(**PLOT_CFG, height=280, title="Carga agregada en horas-hombre", xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]))
    st.plotly_chart(fig_hh, use_container_width=True)

# ────────────────────────────────────────────────────────────────────────────
# TAB 2 · AGREGACIÓN
# ────────────────────────────────────────────────────────────────────────────
with tabs[1]:
    st.markdown('<div class="sec-title">Resultado de planeación agregada</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="info-box">Capacidad efectiva del periodo: {capacidad_laboral:,.0f} H-H · inventario mínimo relativo: {inv_seg:.0%}.</div>', unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Costo total", f"${costo:,.0f}")
    m2.metric("Horas extra", f"{df_agr['Horas_Extras'].sum():,.0f} H-H")
    m3.metric("Backlog total", f"{df_agr['Backlog_HH'].sum():,.0f} H-H")
    m4.metric("Inventario final", f"{df_agr['Inv_Fin_HH'].iloc[-1]:,.0f} H-H")

    fig_agr = go.Figure()
    fig_agr.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Inv_Ini_HH"], name="Base inventario", marker_color=C["sky"], marker_line_color="white", marker_line_width=1))
    fig_agr.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Produccion_HH"], name="Producción", marker_color=C["peach"], marker_line_color="white", marker_line_width=1))
    fig_agr.add_trace(go.Scatter(x=df_agr["Mes_ES"], y=df_agr["Demanda_HH"], mode="lines+markers", name="Demanda", line=dict(color=C["rosewood"], width=2.5, dash="dash"), marker=dict(size=7)))
    fig_agr.add_trace(go.Scatter(x=df_agr["Mes_ES"], y=df_agr["Horas_Regulares"], mode="lines", name="Capacidad regular", line=dict(color=C["lavender"], width=2, dash="dot")))
    fig_agr.update_layout(**PLOT_CFG, barmode="stack", height=380, title="Balance mensual agregado", xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]), legend=dict(orientation="h", y=-0.23, x=0.5, xanchor="center"))
    st.plotly_chart(fig_agr, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        fig_fl = go.Figure()
        fig_fl.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Contratacion"], name="Vinculación", marker_color=C["mint"]))
        fig_fl.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Despidos"], name="Salida", marker_color=C["pink"]))
        fig_fl.update_layout(**PLOT_CFG, barmode="group", height=290, title="Movimiento de personal", xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]), legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"))
        st.plotly_chart(fig_fl, use_container_width=True)
    with c2:
        fig_ex = go.Figure()
        fig_ex.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Horas_Extras"], name="Extra", marker_color=C["butter"]))
        fig_ex.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Backlog_HH"], name="Diferido", marker_color=C["salmon"]))
        fig_ex.update_layout(**PLOT_CFG, barmode="group", height=290, title="Presión operativa", xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]), legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"))
        st.plotly_chart(fig_ex, use_container_width=True)

    with st.expander("Tabla del plan"):
        df_show = df_agr.drop(columns=["Mes", "Mes_ES"]).rename(columns={"Mes_F": "Mes"})
        st.dataframe(df_show, use_container_width=True)

# ────────────────────────────────────────────────────────────────────────────
# TAB 3 · DESAGREGACIÓN
# ────────────────────────────────────────────────────────────────────────────
with tabs[2]:
    st.markdown('<div class="sec-title">Desagregación del plan maestro</div>', unsafe_allow_html=True)
    mes_resaltar = st.selectbox("Mes destacado", range(12), index=mes_idx, format_func=lambda i: MESES_F[i], key="mes_desag")
    mes_nm_desag = MESES[mes_resaltar]

    fig_des = make_subplots(rows=3, cols=2, subplot_titles=[PROD_LABELS[p] for p in PRODUCTOS], vertical_spacing=0.12, horizontal_spacing=0.08)
    for idx, p in enumerate(PRODUCTOS):
        r, c = idx // 2 + 1, idx % 2 + 1
        df_p = desag[p]
        fig_des.add_trace(go.Bar(x=df_p["Mes_ES"], y=df_p["Produccion"], marker_color=PROD_COLORS[p], marker_line_color="white", marker_line_width=1, opacity=0.92, showlegend=False), row=r, col=c)
        fig_des.add_trace(go.Scatter(x=df_p["Mes_ES"], y=df_p["Demanda"], mode="lines+markers", line=dict(color=PROD_COLORS_DARK[p], width=1.6, dash="dash"), marker=dict(size=5), showlegend=False), row=r, col=c)
        mes_row = df_p[df_p["Mes"] == mes_nm_desag]
        if not mes_row.empty:
            fig_des.add_trace(go.Scatter(x=[MESES_ES[mes_resaltar]], y=[mes_row["Produccion"].values[0]], mode="markers", marker=dict(size=14, color=C["rosewood"], symbol="star"), showlegend=False), row=r, col=c)
    fig_des.update_layout(**PLOT_CFG, height=700, title="Plan por referencia y mes", margin=dict(t=60))
    for i in range(1, 4):
        for j in range(1, 3):
            fig_des.update_xaxes(showgrid=False, row=i, col=j)
            fig_des.update_yaxes(gridcolor=C["line"], row=i, col=j)
    st.plotly_chart(fig_des, use_container_width=True)

    cc1, cc2 = st.columns([2, 1])
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
    with cc1:
        fig_cob = go.Figure(go.Bar(y=prods_c, x=cob_vals, orientation="h", marker=dict(color=list(PROD_COLORS.values()), line=dict(color="white", width=2)), text=[f"{v:.1f}%" for v in cob_vals], textposition="inside"))
        fig_cob.add_vline(x=100, line_dash="dash", line_color=C["rosewood"])
        fig_cob.update_layout(**PLOT_CFG, height=270, title="Cobertura anual", xaxis=dict(range=[0, 115], gridcolor=C["line"]), yaxis=dict(showgrid=False))
        st.plotly_chart(fig_cob, use_container_width=True)
    with cc2:
        st.dataframe(pd.DataFrame({"Producto": prods_c, "Producido": und_prod, "Demanda": und_dem, "Cob %": cob_vals}), use_container_width=True, height=270)

    fig_inv = go.Figure()
    for p in PRODUCTOS:
        fig_inv.add_trace(go.Scatter(x=desag[p]["Mes_ES"], y=desag[p]["Inv_Fin"], mode="lines+markers", name=PROD_LABELS[p], line=dict(color=PROD_COLORS_DARK[p], width=2), marker=dict(size=7, color=PROD_COLORS[p], line=dict(color=PROD_COLORS_DARK[p], width=1.4)), fill="tozeroy", fillcolor=hex_rgba(PROD_COLORS[p], 0.16)))
    fig_inv.update_layout(**PLOT_CFG, height=300, title="Trayectoria de inventario final", xaxis_title="Mes", yaxis_title="Unidades", legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center"), xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]))
    st.plotly_chart(fig_inv, use_container_width=True)

# ────────────────────────────────────────────────────────────────────────────
# TAB 4 · SIMULACIÓN
# ────────────────────────────────────────────────────────────────────────────
with tabs[3]:
    st.markdown(f'<div class="sec-title">Lectura operativa del mes · {MESES_F[mes_idx]}</div>', unsafe_allow_html=True)
    cols_p = st.columns(5)
    for i, (p, u) in enumerate(plan_mes.items()):
        hh_req = round(u * HORAS_PRODUCTO[p], 1)
        cols_p[i].markdown(f"""
            <div class="kpi-card" style="background:{hex_rgba(PROD_COLORS[p],0.26)};border-color:{PROD_COLORS_DARK[p]}">
              <div class="icon">{EMOJIS[p]}</div>
              <div class="val" style="font-size:1.45rem">{u:,}</div>
              <div class="lbl">{PROD_LABELS[p]}</div>
              <div class="sub">{hh_req} H-H</div>
            </div>
            """, unsafe_allow_html=True)

    if not df_kpis.empty:
        fig_cum = go.Figure()
        for i, row in df_kpis.iterrows():
            p_key = next((p for p in PRODUCTOS if PROD_LABELS[p] == row["Producto"]), PRODUCTOS[i % len(PRODUCTOS)])
            fig_cum.add_trace(go.Bar(x=[row["Cumplimiento %"]], y=[row["Producto"]], orientation="h", marker=dict(color=PROD_COLORS[p_key], line=dict(color=PROD_COLORS_DARK[p_key], width=1.4)), text=f"{row['Cumplimiento %']:.1f}%", textposition="inside", showlegend=False))
        fig_cum.add_vline(x=100, line_dash="dash", line_color=C["rosewood"])
        fig_cum.update_layout(**PLOT_CFG, height=260, title="Ajuste del plan en planta", xaxis=dict(range=[0, 115], gridcolor=C["line"]), yaxis=dict(showgrid=False))
        st.plotly_chart(fig_cum, use_container_width=True)

        t1, t2 = st.columns(2)
        prods_kpi = list(df_kpis["Producto"].values)
        colores_kpi = [PROD_COLORS[next((p for p in PRODUCTOS if PROD_LABELS[p] == prod), PRODUCTOS[0])] for prod in prods_kpi]
        with t1:
            fig_tp = go.Figure(go.Bar(x=prods_kpi, y=df_kpis["Throughput (und/h)"].values, marker_color=colores_kpi, marker_line_color="white", marker_line_width=2, text=[f"{v:.1f}" for v in df_kpis["Throughput (und/h)"].values], textposition="outside"))
            fig_tp.update_layout(**PLOT_CFG, height=280, title="Flujo por referencia", xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]), showlegend=False)
            st.plotly_chart(fig_tp, use_container_width=True)
        with t2:
            fig_lt = go.Figure(go.Bar(x=prods_kpi, y=df_kpis["Lead Time (min/lote)"].values, marker_color=[PROD_COLORS_DARK[next((p for p in PRODUCTOS if PROD_LABELS[p] == prod), PRODUCTOS[0])] for prod in prods_kpi], marker_line_color="white", marker_line_width=2, text=[f"{v:.0f}" for v in df_kpis["Lead Time (min/lote)"].values], textposition="outside"))
            fig_lt.update_layout(**PLOT_CFG, height=280, title="Tiempo por lote", xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]), showlegend=False)
            st.plotly_chart(fig_lt, use_container_width=True)

    if not df_util.empty:
        st.markdown('<div class="sec-title">Mapa de saturación de recursos</div>', unsafe_allow_html=True)
        cuellos = df_util[df_util["Cuello Botella"]]
        if not cuellos.empty:
            for _, row in cuellos.iterrows():
                st.markdown(f'<div class="pill-warn">⚠️ {REC_LABELS.get(row["Recurso"], row["Recurso"])} · {row["Utilizacion_%"]:.1f}% · cola {row["Cola Prom"]:.2f}</div><br>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="pill-ok">✅ La red operativa no muestra cuellos críticos</div><br>', unsafe_allow_html=True)

        rec_lb = [REC_LABELS.get(r, r) for r in df_util["Recurso"]]
        col_util = [C["pink"] if u >= 80 else C["butter"] if u >= 60 else C["mint"] for u in df_util["Utilizacion_%"]]
        fig_util_g = make_subplots(rows=1, cols=2, subplot_titles=["Carga del recurso", "Espera promedio"])
        fig_util_g.add_trace(go.Bar(x=rec_lb, y=df_util["Utilizacion_%"], marker_color=col_util, text=[f"{v:.0f}%" for v in df_util["Utilizacion_%"]], textposition="outside", showlegend=False), row=1, col=1)
        fig_util_g.add_trace(go.Bar(x=rec_lb, y=df_util["Cola Prom"], marker_color=C["lavender"], text=[f"{v:.2f}" for v in df_util["Cola Prom"]], textposition="outside", showlegend=False), row=1, col=2)
        fig_util_g.add_hline(y=80, line_dash="dash", line_color=C["rosewood"], row=1, col=1)
        fig_util_g.update_layout(**PLOT_CFG, height=320)
        fig_util_g.update_xaxes(showgrid=False)
        fig_util_g.update_yaxes(gridcolor=C["line"])
        st.plotly_chart(fig_util_g, use_container_width=True)

    if not df_lotes.empty:
        sub = df_lotes.head(min(60, len(df_lotes))).reset_index(drop=True)
        fig_gantt = go.Figure()
        for _, row in sub.iterrows():
            fig_gantt.add_trace(go.Bar(x=[row["tiempo_sistema"]], y=[row["lote_id"]], base=[row["t_creacion"]], orientation="h", marker_color=PROD_COLORS.get(row["producto"], "#ccc"), marker_line_color="white", marker_line_width=0.5, opacity=0.88, showlegend=False))
        for p, c in PROD_COLORS.items():
            fig_gantt.add_trace(go.Bar(x=[None], y=[None], marker_color=c, name=PROD_LABELS[p]))
        fig_gantt.update_layout(**PLOT_CFG, barmode="overlay", height=max(380, len(sub) * 8), title="Flujo temporal de lotes", xaxis_title="Tiempo simulado (min)", legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"), yaxis=dict(showticklabels=False))
        st.plotly_chart(fig_gantt, use_container_width=True)

        fig_burb = go.Figure()
        for p in PRODUCTOS:
            subp = df_lotes[df_lotes["producto"] == p]
            if subp.empty:
                continue
            fig_burb.add_trace(go.Scatter(x=subp["t_creacion"], y=subp["tiempo_sistema"], mode="markers", name=PROD_LABELS[p], marker=dict(size=np.clip(subp["tamano"], 8, 24), color=PROD_COLORS[p], line=dict(color=PROD_COLORS_DARK[p], width=1.2), opacity=0.75)))
        fig_burb.update_layout(**PLOT_CFG, height=330, title="Mapa dinámico de lotes", xaxis_title="Liberación del lote", yaxis_title="Tiempo en sistema", legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center"), xaxis=dict(gridcolor=C["line"]), yaxis=dict(gridcolor=C["line"]))
        st.plotly_chart(fig_burb, use_container_width=True)

# ────────────────────────────────────────────────────────────────────────────
# TAB 5 · SENSORES
# ────────────────────────────────────────────────────────────────────────────
with tabs[4]:
    st.markdown('<div class="sec-title">Monitoreo térmico</div>', unsafe_allow_html=True)
    if not df_sensores.empty:
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Mínima", f"{df_sensores['temperatura'].min():.1f} °C")
        s2.metric("Máxima", f"{df_sensores['temperatura'].max():.1f} °C")
        s3.metric("Promedio", f"{df_sensores['temperatura'].mean():.1f} °C")
        s4.metric("Alertas >200°C", excesos)

        fig_temp = go.Figure()
        fig_temp.add_hrect(y0=150, y1=200, fillcolor=hex_rgba(C["mint"], 0.21), line_width=0)
        fig_temp.add_trace(go.Scatter(x=df_sensores["tiempo"], y=df_sensores["temperatura"], mode="lines", name="Temperatura", fill="tozeroy", fillcolor=hex_rgba(C["salmon"], 0.15), line=dict(color=C["rosewood"], width=1.8)))
        if len(df_sensores) > 10:
            mm = df_sensores["temperatura"].rolling(5, min_periods=1).mean()
            fig_temp.add_trace(go.Scatter(x=df_sensores["tiempo"], y=mm, mode="lines", name="Media móvil", line=dict(color=C["lavender"], width=2, dash="dot")))
        fig_temp.add_hline(y=200, line_dash="dash", line_color="#C0392B")
        fig_temp.update_layout(**PLOT_CFG, height=320, title="Señal térmica del horno", xaxis_title="Tiempo", yaxis_title="°C", legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center"), xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]))
        st.plotly_chart(fig_temp, use_container_width=True)

        sx1, sx2 = st.columns(2)
        with sx1:
            fig_ocup = go.Figure()
            fig_ocup.add_trace(go.Scatter(x=df_sensores["tiempo"], y=df_sensores["horno_ocup"], mode="lines", fill="tozeroy", fillcolor=hex_rgba(C["sky"], 0.25), line=dict(color=PROD_COLORS_DARK["Mantecadas"], width=2)))
            fig_ocup.add_hline(y=cap_horno, line_dash="dot", line_color=C["rosewood"])
            fig_ocup.update_layout(**PLOT_CFG, height=260, title="Uso del horno", xaxis_title="Tiempo", yaxis_title="Estaciones", showlegend=False, xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]))
            st.plotly_chart(fig_ocup, use_container_width=True)
        with sx2:
            fig_hist = go.Figure(go.Histogram(x=df_sensores["temperatura"], nbinsx=35, marker_color=C["peach"], marker_line_color="white", marker_line_width=1))
            fig_hist.add_vline(x=200, line_dash="dash", line_color="#C0392B")
            fig_hist.update_layout(**PLOT_CFG, height=260, title="Distribución térmica", xaxis_title="°C", yaxis_title="Frecuencia", showlegend=False, xaxis=dict(showgrid=False), yaxis=dict(gridcolor=C["line"]))
            st.plotly_chart(fig_hist, use_container_width=True)
    else:
        st.info("No hay datos térmicos disponibles.")

# ────────────────────────────────────────────────────────────────────────────
# TAB 6 · ESCENARIOS
# ────────────────────────────────────────────────────────────────────────────
with tabs[5]:
    st.markdown('<div class="sec-title">Lectura comparativa de escenarios</div>', unsafe_allow_html=True)
    ESCENARIOS_DEF = {
        "Base": {"fd": 1.0, "falla": False, "ft": 1.0, "cap_delta": 0},
        "Impulso comercial": {"fd": 1.2, "falla": False, "ft": 1.0, "cap_delta": 0},
        "Caída puntual": {"fd": 0.8, "falla": False, "ft": 1.0, "cap_delta": 0},
        "Horno inestable": {"fd": 1.0, "falla": True, "ft": 1.0, "cap_delta": 0},
        "Refuerzo térmico": {"fd": 1.0, "falla": False, "ft": 1.0, "cap_delta": 1},
        "Restricción de capacidad": {"fd": 1.0, "falla": False, "ft": 1.0, "cap_delta": -1},
        "Ritmo extendido": {"fd": 1.0, "falla": False, "ft": 0.80, "cap_delta": 0},
        "Modo fino": {"fd": 1.0, "falla": False, "ft": 0.85, "cap_delta": 1},
    }
    escenarios_sel = st.multiselect("Escenarios a contrastar", list(ESCENARIOS_DEF.keys()), default=["Base", "Impulso comercial", "Horno inestable", "Ritmo extendido", "Modo fino"])
    if st.button("Construir comparación", type="primary"):
        filas_esc = []
        prog = st.progress(0)
        for i, nm in enumerate(escenarios_sel):
            prog.progress((i + 1) / len(escenarios_sel), text=f"Evaluando {nm}...")
            cfg = ESCENARIOS_DEF[nm]
            plan_esc = {p: max(int(u * cfg["fd"]), 0) for p, u in plan_mes.items()}
            cap_esc = {**cap_rec, "horno": max(cap_rec["horno"] + cfg["cap_delta"], 1)}
            df_l, df_u, _ = run_simulacion_cached(tuple(plan_esc.items()), tuple(cap_esc.items()), cfg["falla"], cfg["ft"], tuple({"mezcla": tm, "dosificado": td, "horno": th, "enfriamiento": te, "empaque": tep, "amasado": ta}.items()), temp_horno_base, semilla + i + 20)
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
            e1, e2 = st.columns(2)
            with e1:
                if "Cumplimiento %" in df_comp.columns:
                    col_c = [C["mint"] if v >= 90 else C["butter"] if v >= 70 else C["pink"] for v in df_comp["Cumplimiento %"]]
                    fig_ec = go.Figure(go.Bar(x=df_comp["Escenario"], y=df_comp["Cumplimiento %"], marker_color=col_c, marker_line_color="white", marker_line_width=2, text=[f"{v:.1f}%" for v in df_comp["Cumplimiento %"]], textposition="outside"))
                    fig_ec.add_hline(y=100, line_dash="dash", line_color=C["rosewood"])
                    fig_ec.update_layout(**PLOT_CFG, height=300, title="Cumplimiento comparado", xaxis=dict(showgrid=False, tickangle=-25), yaxis=dict(gridcolor=C["line"]), showlegend=False, margin=dict(t=30, b=90))
                    st.plotly_chart(fig_ec, use_container_width=True)
            with e2:
                if "Util. max %" in df_comp.columns:
                    col_u = [C["pink"] if v >= 80 else C["butter"] if v >= 60 else C["mint"] for v in df_comp["Util. max %"]]
                    fig_eu = go.Figure(go.Bar(x=df_comp["Escenario"], y=df_comp["Util. max %"], marker_color=col_u, marker_line_color="white", marker_line_width=2, text=[f"{v:.0f}%" for v in df_comp["Util. max %"]], textposition="outside"))
                    fig_eu.add_hline(y=80, line_dash="dash", line_color=C["rosewood"])
                    fig_eu.update_layout(**PLOT_CFG, height=300, title="Presión máxima", xaxis=dict(showgrid=False, tickangle=-25), yaxis=dict(gridcolor=C["line"]), showlegend=False, margin=dict(t=30, b=90))
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
                    fig_radar.add_trace(go.Scatterpolar(r=vals + [vals[0]], theta=cols_radar + [cols_radar[0]], fill="toself", name=row["Escenario"], line=dict(color=radar_colors[i % len(radar_colors)], width=2), fillcolor=hex_rgba(radar_colors[i % len(radar_colors)], 0.15)))
                fig_radar.update_layout(**PLOT_CFG, height=430, title="Perfil relativo de escenarios", polar=dict(radialaxis=dict(visible=True, range=[0, 1], gridcolor=C["line"]), angularaxis=dict(gridcolor=C["line"])), legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"))
                st.plotly_chart(fig_radar, use_container_width=True)

            if {"Cumplimiento %", "Lead Time (min)", "Util. max %", "Cuellos botella"}.issubset(df_comp.columns):
                df_rank = df_comp.copy()
                df_rank["Score"] = (
                    df_rank["Cumplimiento %"] * 0.45
                    + (100 - df_rank["Util. max %"].clip(upper=100)) * 0.20
                    + (100 - df_rank["Lead Time (min)"].rank(pct=True) * 100) * 0.20
                    + (100 - df_rank["Cuellos botella"].rank(pct=True) * 100) * 0.15
                )
                df_rank = df_rank.sort_values("Score", ascending=False).reset_index(drop=True)
                fig_rank = go.Figure(go.Bar(x=df_rank["Score"], y=df_rank["Escenario"], orientation="h", marker=dict(color=[C["mint"], C["sky"], C["lavender"], C["peach"], C["pink"]][:len(df_rank)], line=dict(color="white", width=2)), text=[f"{v:.1f}" for v in df_rank["Score"]], textposition="outside"))
                fig_rank.update_layout(**PLOT_CFG, height=320, title="Jerarquía integrada", xaxis_title="Score compuesto", yaxis=dict(autorange="reversed", showgrid=False), xaxis=dict(gridcolor=C["line"]), showlegend=False)
                st.plotly_chart(fig_rank, use_container_width=True)
    else:
        st.markdown('<div class="info-box" style="text-align:center;padding:2rem;">Selecciona escenarios y construye la comparación. La idea es mostrar alternativas del proyecto, no copiar una plantilla externa.</div>', unsafe_allow_html=True)

st.markdown("---")
st.markdown("""
<div style='text-align:center;color:#8C7B70;font-size:0.82rem;padding:0.3rem 0 1rem'>
  🥐 <b>Gemelo Digital · Panadería Dora del Hoyo</b> · versión reorganizada por secciones funcionales
</div>
""", unsafe_allow_html=True)
