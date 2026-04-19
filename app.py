"""
app.py  —  Gemelo Digital · Panadería Dora del Hoyo
====================================================
Versión 4.0
- Portada arriba de todo
- Barra lateral solo con parámetros generales
- Parámetros especializados dentro de cada pestaña
- Sin IDs duplicados en Streamlit
- Incluye gráficas recuperadas del código base:
  * combinado Producción + Demanda + Inventario
  * Gantt de lotes
  * violín de tiempos en sistema
  * ocupación e histograma térmico
  * comparación de escenarios con barras, radar y ranking

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


def init_state(key: str, value):
    if key not in st.session_state:
        st.session_state[key] = value


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
LITROS_UNIDAD_BASE = {
    "Brownies": 0.50,
    "Mantecadas": 0.15,
    "Mantecadas_Amapola": 0.15,
    "Torta_Naranja": 0.80,
    "Pan_Maiz": 0.30,
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
    "stock_obj": 0.0,
}
INV_INICIAL = {p: 0 for p in PRODUCTOS}

# estado
DEFAULTS = {
    "mes_idx": 1,
    "factor_demanda": 1.0,
    "meses_pronostico": 3,
    "participacion_mercado": 75,
    "litros_por_unidad": 0.35,
    "semilla": 42,
    "mix_brownies": 1.0,
    "mix_mantecadas": 1.0,
    "mix_amapola": 1.0,
    "mix_torta": 1.0,
    "mix_panmaiz": 1.0,
    "ct": 4310,
    "ht": 100000,
    "pit": 100000,
    "crt": 11364,
    "cot": 14205,
    "cwp": 14204,
    "cwm": 15061,
    "trab": 10,
    "turnos_dia": 1,
    "horas_turno": 8,
    "dias_mes": 22,
    "eficiencia": 85,
    "ausentismo": 5,
    "flexibilidad": 10,
    "stock_obj": 0.0,
    "costo_pen_des": 150000,
    "costo_inv_des": 100000,
    "suavizado_des": 500,
    "proteccion_mix": False,
    "mezcla_cap": 2,
    "dosificado_cap": 2,
    "cap_horno": 3,
    "enfriamiento_cap": 4,
    "empaque_cap": 2,
    "amasado_cap": 1,
    "falla_horno": False,
    "doble_turno": False,
    "variabilidad": 1.0,
    "espaciamiento": 1.0,
    "iter_sim": 1,
}
for k, v in DEFAULTS.items():
    init_state(k, v)


# ══════════════════════════════════════════════════════════════════════════════
# CORE
# ══════════════════════════════════════════════════════════════════════════════
def get_demanda_historica(mix_factors: dict, factor_demanda: float) -> dict:
    dem = {}
    for p in PRODUCTOS:
        mf = mix_factors.get(p, 1.0)
        dem[p] = [round(v * factor_demanda * mf, 1) for v in DEM_HISTORICA[p]]
    return dem


def demanda_horas_hombre(dem_hist: dict) -> dict:
    return {
        mes: round(sum(dem_hist[p][i] * HORAS_PRODUCTO[p] for p in PRODUCTOS), 4)
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
def run_agregacion(dem_hh_items, params_tuple):
    params = dict(params_tuple)
    dem_h = dict(dem_hh_items)

    Ct = params["Ct"]
    Ht = params["Ht"]
    PIt = params["PIt"]
    CRt = params["CRt"]
    COt = params["COt"]
    Wm = params["CW_mas"]
    Wd = params["CW_menos"]
    M = params["M"]
    LRi = params["LR_inicial"]
    stock_obj = params.get("stock_obj", 0.0)

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
        if stock_obj > 0:
            mdl += I[t] >= stock_obj * d
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
def run_desagregacion(prod_hh_items, dem_hist_items, costo_pen, costo_inv, suavizado, proteccion_mix):
    prod_hh = dict(prod_hh_items)
    dem_hist = {k: list(v) for k, v in dem_hist_items}

    mdl = LpProblem("Desagregacion", LpMinimize)
    X = {(p, t): LpVariable(f"X_{p}_{t}", lowBound=0) for p in PRODUCTOS for t in MESES}
    I = {(p, t): LpVariable(f"I_{p}_{t}", lowBound=0) for p in PRODUCTOS for t in MESES}
    S = {(p, t): LpVariable(f"S_{p}_{t}", lowBound=0) for p in PRODUCTOS for t in MESES}
    DX = {(p, t): LpVariable(f"DX_{p}_{t}", lowBound=0) for p in PRODUCTOS for t in MESES}

    mdl += lpSum(costo_inv * I[p, t] + costo_pen * S[p, t] + suavizado * DX[p, t] for p in PRODUCTOS for t in MESES)

    for idx, t in enumerate(MESES):
        tp = MESES[idx - 1] if idx > 0 else None
        mdl += lpSum(HORAS_PRODUCTO[p] * X[p, t] for p in PRODUCTOS) <= prod_hh[t]
        for p in PRODUCTOS:
            d = dem_hist[p][idx]
            if idx == 0:
                mdl += I[p, t] - S[p, t] == INV_INICIAL[p] + X[p, t] - d
            else:
                mdl += I[p, t] - S[p, t] == I[p, tp] - S[p, tp] + X[p, t] - d
                mdl += DX[p, t] >= X[p, t] - X[p, tp]
                mdl += DX[p, t] >= X[p, tp] - X[p, t]

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
                "Demanda": dem_hist[p][idx],
                "Produccion": xv,
                "Inv_Ini": ini,
                "Inv_Fin": iv,
                "Backlog": sv,
            })
        resultados[p] = pd.DataFrame(filas)
    return resultados


@st.cache_data(show_spinner=False)
def run_simulacion_cached(plan_items, cap_items, falla, factor_t, variabilidad=1.0, espaciamiento=1.0, semilla=42):
    plan_unidades = dict(plan_items)
    cap_recursos = dict(cap_items)
    random.seed(semilla)
    np.random.seed(semilla)

    lotes_data, uso_rec, sensores = [], [], []

    def sensor_horno(env, recursos):
        while True:
            ocp = recursos["horno"].count
            temp = round(np.random.normal(160 + ocp * 20, 5 * variabilidad), 2)
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
        for etapa, rec_nm, tmin, tmax in RUTAS[prod]:
            escala = math.sqrt(tam / TAMANO_LOTE_BASE[prod])
            tp = random.uniform(tmin * variabilidad, tmax * variabilidad) * escala * factor_t
            if falla and rec_nm == "horno":
                tp += random.uniform(10, 30)
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

    dur_mes = 44 * 4 * 60
    lotes = []
    ctr = [0]
    for prod, unid in plan_unidades.items():
        if unid <= 0:
            continue
        tam = TAMANO_LOTE_BASE[prod]
        n = math.ceil(unid / tam)
        tasa = dur_mes / max(n, 1) * espaciamiento
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
    env.run(until=dur_mes * 1.8)
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
            "Util. max %": util,
            "Cola Prom": round(grp["cola"].mean(), 3),
            "Cola Max": int(grp["cola"].max()),
            "Capacidad": int(cap),
            "Cuello Botella": util >= 80 or grp["cola"].mean() > 0.5,
        })
    return pd.DataFrame(filas).sort_values("Util. max %", ascending=False).reset_index(drop=True)


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
# CONFIG STREAMLIT
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Gemelo Digital · Dora del Hoyo", page_icon="🥐", layout="wide", initial_sidebar_state="expanded")

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;600;700&family=DM+Sans:wght@300;400;500;600&display=swap');
html, body, [class*="css"] {{ font-family:'DM Sans',sans-serif; background:{C['bg']}; color:{C['text']}; }}
.block-container {{ padding-top:1.2rem; padding-bottom:1.5rem; }}
.hero {{ background:linear-gradient(135deg, {C['lavender']} 0%, {C['sky']} 35%, {C['peach']} 100%); padding:2rem 2.2rem 1.6rem; border-radius:24px; margin-bottom:1.2rem; border:1px solid {C['line']}; box-shadow:0 12px 28px rgba(120,100,90,0.10); }}
.hero h1 {{ font-family:'Cormorant Garamond',serif; color:{C['text']}; font-size:2.4rem; margin:0; font-weight:700; }}
.hero p {{ color:{C['muted']}; margin:0.45rem 0 0; font-size:0.95rem; }}
.hero .badge {{ display:inline-block; background:rgba(255,255,255,0.75); color:{C['text']}; padding:0.28rem 0.8rem; border-radius:999px; font-size:0.75rem; margin-top:0.8rem; margin-right:0.35rem; border:1px solid {C['line']}; }}
.kpi-card {{ background:{C['panel']}; border-radius:18px; padding:1rem 1rem; border:1px solid {C['line']}; box-shadow:0 6px 18px rgba(120,100,90,0.07); text-align:center; }}
.kpi-card .icon {{ font-size:1.55rem; margin-bottom:0.2rem; }}
.kpi-card .val {{ font-family:'Cormorant Garamond',serif; font-size:1.8rem; color:{C['text']}; line-height:1; }}
.kpi-card .lbl {{ font-size:0.72rem; text-transform:uppercase; letter-spacing:0.08em; color:{C['muted']}; margin-top:0.25rem; font-weight:700; }}
.kpi-card .sub {{ font-size:0.78rem; color:{C['rosewood']}; margin-top:0.2rem; }}
.sec-title {{ font-family:'Cormorant Garamond',serif; color:{C['text']}; font-size:1.35rem; margin:1.2rem 0 0.7rem; padding-left:0.8rem; border-left:5px solid {C['gold']}; }}
.info-box {{ background:{C['panel_2']}; border:1px solid {C['line']}; border-radius:14px; padding:0.9rem 1rem; color:{C['text']}; font-size:0.9rem; margin:0.5rem 0 0.9rem; }}
.pill-ok {{ background:{C['mint']}; color:{C['text']}; padding:0.28rem 0.85rem; border-radius:999px; font-size:0.82rem; display:inline-block; font-weight:600; }}
.pill-warn {{ background:{C['pink']}; color:{C['text']}; padding:0.28rem 0.85rem; border-radius:999px; font-size:0.82rem; display:inline-block; font-weight:600; }}
[data-testid="stSidebar"] {{ background: linear-gradient(180deg, #fffaf3 0%, #fff3eb 100%) !important; border-right:1px solid {C['line']}; }}
[data-testid="stSidebar"] * {{ color:{C['text']} !important; }}
.stTabs [data-baseweb="tab"] {{ font-weight:600; }}
</style>
""", unsafe_allow_html=True)

# sidebar general
with st.sidebar:
    st.markdown("## 🥐 Dora del Hoyo")
    st.markdown("*Gemelo Digital v4.0*")
    st.markdown("### Parámetros generales")
    st.selectbox("Mes de análisis", range(12), index=st.session_state["mes_idx"], format_func=lambda i: MESES_F[i], key="mes_idx")
    st.slider("Impulso de demanda", 0.5, 2.0, key="factor_demanda", step=0.05)
    st.slider("Horizonte de proyección", 1, 6, key="meses_pronostico")
    st.slider("Cobertura comercial (%)", 10, 100, key="participacion_mercado", step=5)
    st.slider("Litros promedio por unidad", 0.1, 2.0, key="litros_por_unidad", step=0.05)
    st.number_input("Semilla aleatoria", key="semilla", step=1)
    st.caption("Los parámetros especializados aparecen dentro de cada módulo.")

# valores generales
mes_idx = int(st.session_state["mes_idx"])
factor_demanda = float(st.session_state["factor_demanda"])
meses_pronostico = int(st.session_state["meses_pronostico"])
participacion_mercado = int(st.session_state["participacion_mercado"])
litros_por_unidad = float(st.session_state["litros_por_unidad"])
semilla = int(st.session_state["semilla"])

PLOT_CFG = dict(
    template="plotly_white",
    font=dict(family="DM Sans", color=C["text"]),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(255,253,248,0.5)",
)

# portada arriba
st.markdown(f"""
<div class="hero">
  <h1>Gemelo Digital · Panadería Dora del Hoyo</h1>
  <p>Planeación, simulación y decisión operativa para una panadería artesanal con una vista integral de demanda, capacidad, inventario, sensores y escenarios.</p>
  <span class="badge">📅 {MESES_F[mes_idx]}</span>
  <span class="badge">📈 Impulso x{factor_demanda:.2f}</span>
  <span class="badge">🛒 Cobertura {participacion_mercado}%</span>
  <span class="badge">🧁 {litros_por_unidad:.2f} L por unidad</span>
</div>
""", unsafe_allow_html=True)

# pestañas
TAB_DEM, TAB_AGR, TAB_DES, TAB_SIM, TAB_SEN, TAB_ESC = st.tabs([
    "📊 Demanda y proyección",
    "📋 Planeación agregada",
    "📦 Desagregación por producto",
    "🏭 Simulación operativa",
    "🌡️ Sensores y horno",
    "🔬 Escenarios what-if",
])

# parámetros por pestaña
with TAB_DEM:
    st.markdown('<div class="sec-title">Configuración comercial de demanda</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Ajusta la participación relativa por familia de producto para representar campañas o cambios del mix comercial.</div>', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.slider("Brownies", 0.3, 2.0, key="mix_brownies", step=0.05)
    c2.slider("Mantecadas", 0.3, 2.0, key="mix_mantecadas", step=0.05)
    c3.slider("Amapola", 0.3, 2.0, key="mix_amapola", step=0.05)
    c4.slider("Torta", 0.3, 2.0, key="mix_torta", step=0.05)
    c5.slider("Pan maíz", 0.3, 2.0, key="mix_panmaiz", step=0.05)

with TAB_AGR:
    st.markdown('<div class="sec-title">Configuración de planeación agregada</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Costos, mano de obra y stock objetivo que afectan la optimización del plan agregado.</div>', unsafe_allow_html=True)
    a1, a2, a3, a4 = st.columns(4)
    a1.number_input("Costo producción (Ct)", key="ct", step=100)
    a2.number_input("Costo inventario (Ht)", key="ht", step=1000)
    a3.number_input("Costo backlog (PIt)", key="pit", step=1000)
    a4.slider("Stock seguridad", 0.0, 0.5, key="stock_obj", step=0.05)
    a5, a6, a7, a8 = st.columns(4)
    a5.number_input("Costo regular (CRt)", key="crt", step=100)
    a6.number_input("Costo extra (COt)", key="cot", step=100)
    a7.number_input("Costo contratación", key="cwp", step=100)
    a8.number_input("Costo despido", key="cwm", step=100)
    a9, a10, a11, a12 = st.columns(4)
    a9.number_input("Trabajadores iniciales", key="trab", step=1)
    a10.slider("Turnos / día", 1, 3, key="turnos_dia")
    a11.slider("Horas / turno", 6, 12, key="horas_turno")
    a12.slider("Días / mes", 18, 26, key="dias_mes")
    a13, a14, a15 = st.columns(3)
    a13.slider("Eficiencia (%)", 50, 100, key="eficiencia")
    a14.slider("Ausentismo (%)", 0, 20, key="ausentismo")
    a15.slider("Flexibilidad HH (%)", 0, 30, key="flexibilidad")

with TAB_DES:
    st.markdown('<div class="sec-title">Ajuste del reparto por producto</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Parámetros para castigar faltantes, mantener inventario y suavizar cambios bruscos en la producción mensual.</div>', unsafe_allow_html=True)
    d1, d2, d3 = st.columns(3)
    d1.number_input("Penalización backlog", key="costo_pen_des", step=5000)
    d2.number_input("Costo inventario/und", key="costo_inv_des", step=5000)
    d3.slider("Suavizado producción", 0, 5000, key="suavizado_des", step=100)
    st.checkbox("Proteger proporciones del mix", key="proteccion_mix")

with TAB_SIM:
    st.markdown('<div class="sec-title">Ajuste operativo de la simulación</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Capacidades de recursos, fallas, doble turno y comportamiento estocástico de la planta.</div>', unsafe_allow_html=True)
    s1, s2, s3, s4, s5, s6 = st.columns(6)
    s1.slider("Mezcla", 1, 6, key="mezcla_cap")
    s2.slider("Dosificado", 1, 6, key="dosificado_cap")
    s3.slider("Horno", 1, 8, key="cap_horno")
    s4.slider("Enfriamiento", 1, 8, key="enfriamiento_cap")
    s5.slider("Empaque", 1, 6, key="empaque_cap")
    s6.slider("Amasado", 1, 4, key="amasado_cap")
    s7, s8, s9, s10 = st.columns(4)
    s7.checkbox("Fallas en horno", key="falla_horno")
    s8.checkbox("Doble turno", key="doble_turno")
    s9.slider("Variabilidad", 0.5, 2.0, key="variabilidad", step=0.1)
    s10.slider("Espaciamiento", 0.5, 2.0, key="espaciamiento", step=0.1)
    st.slider("Iteraciones de simulación", 1, 5, key="iter_sim")

# tomar valores
mix_factors = {
    "Brownies": float(st.session_state["mix_brownies"]),
    "Mantecadas": float(st.session_state["mix_mantecadas"]),
    "Mantecadas_Amapola": float(st.session_state["mix_amapola"]),
    "Torta_Naranja": float(st.session_state["mix_torta"]),
    "Pan_Maiz": float(st.session_state["mix_panmaiz"]),
}
ct = st.session_state["ct"]
ht = st.session_state["ht"]
pit = st.session_state["pit"]
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
flexibilidad = st.session_state["flexibilidad"]
stock_obj = st.session_state["stock_obj"]
costo_pen_des = st.session_state["costo_pen_des"]
costo_inv_des = st.session_state["costo_inv_des"]
suavizado_des = st.session_state["suavizado_des"]
proteccion_mix = st.session_state["proteccion_mix"]
mezcla_cap = st.session_state["mezcla_cap"]
dosificado_cap = st.session_state["dosificado_cap"]
cap_horno = st.session_state["cap_horno"]
enfriamiento_cap = st.session_state["enfriamiento_cap"]
empaque_cap = st.session_state["empaque_cap"]
amasado_cap = st.session_state["amasado_cap"]
falla_horno = st.session_state["falla_horno"]
doble_turno = st.session_state["doble_turno"]
variabilidad = st.session_state["variabilidad"]
espaciamiento = st.session_state["espaciamiento"]
iter_sim = st.session_state["iter_sim"]

# precálculos
DEM_HIST = get_demanda_historica(mix_factors, factor_demanda)
dem_h = demanda_horas_hombre(DEM_HIST)
factor_ef = (eficiencia / 100) * (1 - ausentismo / 100) * (1 + flexibilidad / 100)
LR_inicial = trab * turnos_dia * horas_turno * dias_mes * factor_ef
params_custom = {
    "Ct": ct,
    "Ht": ht,
    "PIt": pit,
    "CRt": crt,
    "COt": cot,
    "CW_mas": cwp,
    "CW_menos": cwm,
    "M": 1,
    "LR_inicial": round(LR_inicial, 2),
    "stock_obj": stock_obj,
}

with st.spinner("Optimizando plan agregado..."):
    df_agr, costo = run_agregacion(tuple(dem_h.items()), tuple(sorted(params_custom.items())))
prod_hh = dict(zip(df_agr["Mes"], df_agr["Produccion_HH"]))
dem_hist_items = tuple((p, tuple(DEM_HIST[p])) for p in PRODUCTOS)
with st.spinner("Desagregando por producto..."):
    desag = run_desagregacion(tuple(prod_hh.items()), dem_hist_items, costo_pen_des, costo_inv_des, suavizado_des, proteccion_mix)

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
    df_l, df_u, df_s = run_simulacion_cached(tuple(plan_mes.items()), tuple(cap_rec.items()), falla_horno, factor_t, variabilidad, espaciamiento, semilla + i)
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

# kpis globales
prod_total = sum(desag[p]["Produccion"].sum() for p in PRODUCTOS)
litros_total = round(prod_total * litros_por_unidad, 1)
cum_avg = df_kpis["Cumplimiento %"].mean() if not df_kpis.empty else 0
util_max = df_util["Util. max %"].max() if not df_util.empty else 0
lotes_n = len(df_lotes) if not df_lotes.empty else 0
temp_avg = df_sensores["temperatura"].mean() if not df_sensores.empty else 0
excesos = int((df_sensores["temperatura"] > 200).sum()) if not df_sensores.empty else 0

# kpis superiores
k1, k2, k3, k4, k5, k6 = st.columns(6)
def kpi_card(col, icon, val, lbl, sub=""):
    col.markdown(f"""
    <div class="kpi-card">
      <div class="icon">{icon}</div>
      <div class="val">{val}</div>
      <div class="lbl">{lbl}</div>
      {"<div class='sub'>" + sub + "</div>" if sub else ""}
    </div>
    """, unsafe_allow_html=True)

kpi_card(k1, "💰", f"${costo/1e6:.1f}M", "Costo óptimo", "plan anual")
kpi_card(k2, "🧁", f"{litros_total:,.0f}L", "Volumen anual", f"× {litros_por_unidad:.2f} L/und")
kpi_card(k3, "🛒", f"{participacion_mercado}%", "Cobertura comercial", f"{prod_total:,.0f} und/año")
kpi_card(k4, "✅", f"{cum_avg:.1f}%", "Cumplimiento sim.", MESES_F[mes_idx])
kpi_card(k5, "⚙️", f"{util_max:.0f}%", "Utilización máx.", "vigilar" if util_max >= 80 else "estable")
kpi_card(k6, "🌡️", f"{temp_avg:.0f}°C", "Temp. horno", f"{excesos} alertas" if excesos else "sin alertas")
st.markdown("<br>", unsafe_allow_html=True)

# contenido demanda
with TAB_DEM:
    st.markdown('<div class="sec-title">Demanda histórica y pronóstico por producto</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Datos ajustados por mix de producto y factor de impulso global. Las líneas punteadas representan la proyección futura.</div>', unsafe_allow_html=True)
    fig_pro = go.Figure()
    for p in PRODUCTOS:
        serie = DEM_HIST[p]
        suav, futuro = pronostico_simple(serie, meses_pronostico)
        fig_pro.add_trace(go.Scatter(x=MESES_ES, y=serie, mode="lines", name=PROD_LABELS[p], line=dict(color=PROD_COLORS_DARK[p], width=2.5)))
        meses_fut = [f"P+{j+1}" for j in range(meses_pronostico)]
        x_fut = [MESES_ES[-1]] + meses_fut
        y_fut = [suav[-1]] + futuro
        fig_pro.add_trace(go.Scatter(x=x_fut, y=y_fut, mode="lines+markers", showlegend=False, line=dict(color=PROD_COLORS_DARK[p], width=2, dash="dash"), marker=dict(size=10, symbol="circle", color=PROD_COLORS[p], line=dict(color=PROD_COLORS_DARK[p], width=2))))
    fig_pro.add_vline(x=len(MESES_ES)-1, line_dash="dot", line_color=C["gold"], annotation_text="▶ Pronóstico", annotation_font_color=C["gold"], annotation_position="top right")
    fig_pro.update_layout(**PLOT_CFG, height=400, title="Demanda & Proyección — Panadería Dora del Hoyo", xaxis_title="Mes", yaxis_title="Unidades", legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center"), xaxis=dict(showgrid=True, gridcolor="#F0E8D8"), yaxis=dict(showgrid=True, gridcolor="#F0E8D8"))
    st.plotly_chart(fig_pro, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown('<div class="sec-title">Mapa de calor — estacionalidad</div>', unsafe_allow_html=True)
        z = [[DEM_HIST[p][i] for i in range(12)] for p in PRODUCTOS]
        fig_heat = go.Figure(go.Heatmap(z=z, x=MESES_ES, y=[PROD_LABELS[p] for p in PRODUCTOS], colorscale=[[0, C["bg"]], [0.3, C["butter"]], [0.65, C["gold"]], [1, C["coffee"]]], hovertemplate="%{y}<br>%{x}: %{z:.0f} und<extra></extra>"))
        fig_heat.update_layout(**PLOT_CFG, height=250, margin=dict(t=20, b=10))
        st.plotly_chart(fig_heat, use_container_width=True)
    with col_b:
        st.markdown('<div class="sec-title">Participación anual de ventas</div>', unsafe_allow_html=True)
        totales = {p: sum(DEM_HIST[p]) for p in PRODUCTOS}
        fig_pie = go.Figure(go.Pie(labels=[PROD_LABELS[p] for p in PRODUCTOS], values=list(totales.values()), hole=0.55, marker=dict(colors=list(PROD_COLORS.values()), line=dict(color="white", width=3))))
        fig_pie.update_layout(**PLOT_CFG, height=250, annotations=[dict(text="<b>Mix</b><br>anual", x=0.5, y=0.5, font=dict(size=11, color=C["text"]), showarrow=False)])
        st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown('<div class="sec-title">Demanda total en horas-hombre por mes</div>', unsafe_allow_html=True)
    fig_hh = go.Figure()
    colores_hh = [C["butter"] if i != mes_idx else C["coffee"] for i in range(12)]
    fig_hh.add_trace(go.Bar(x=MESES_ES, y=list(dem_h.values()), marker_color=colores_hh, marker_line_color="white", marker_line_width=1.5, showlegend=False))
    fig_hh.add_trace(go.Scatter(x=MESES_ES, y=list(dem_h.values()), mode="lines+markers", line=dict(color=C["coffee"], width=2), marker=dict(size=6), showlegend=False))
    fig_hh.add_hline(y=LR_inicial, line_dash="dash", line_color=C["coffee"], annotation_text=f"Capacidad: {LR_inicial:,.0f} H-H", annotation_font_color=C["coffee"])
    fig_hh.update_layout(**PLOT_CFG, height=270, xaxis_title="Mes", yaxis_title="H-H", xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#F0E8D8"))
    st.plotly_chart(fig_hh, use_container_width=True)

# contenido agregación
with TAB_AGR:
    st.markdown('<div class="sec-title">Planeación agregada — Optimización LP</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="info-box"><b>{trab} trabajadores</b> · {turnos_dia} turno(s)/día · {horas_turno}h/turno · {dias_mes} días/mes · eficiencia efectiva <b>{factor_ef*100:.1f}%</b> → capacidad <b>{LR_inicial:,.0f} H-H/mes</b>.</div>', unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Costo total", f"${costo:,.0f} COP")
    m2.metric("Horas extra", f"{df_agr['Horas_Extras'].sum():,.0f} H-H")
    m3.metric("Backlog total", f"{df_agr['Backlog_HH'].sum():,.0f} H-H")
    m4.metric("Contratación neta", f"{df_agr['Contratacion'].sum()-df_agr['Despidos'].sum():+.0f}")

    fig_agr = go.Figure()
    fig_agr.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Inv_Ini_HH"], name="Inv. inicial H-H", marker_color=C["sky"], marker_line_color="white", marker_line_width=1))
    fig_agr.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Produccion_HH"], name="Producción H-H", marker_color=C["butter"], marker_line_color="white", marker_line_width=1))
    fig_agr.add_trace(go.Scatter(x=df_agr["Mes_ES"], y=df_agr["Demanda_HH"], mode="lines+markers", name="Demanda H-H", line=dict(color=C["coffee"], dash="dash", width=2.5), marker=dict(size=8)))
    fig_agr.add_trace(go.Scatter(x=df_agr["Mes_ES"], y=df_agr["Horas_Regulares"], mode="lines", name="Cap. regular", line=dict(color=C["rosewood"], dash="dot", width=2)))
    fig_agr.update_layout(**PLOT_CFG, barmode="stack", height=370, title=f"Costo óptimo LP: COP ${costo:,.0f}", xaxis_title="Mes", yaxis_title="Horas-Hombre", legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center"), xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#F0E8D8"))
    st.plotly_chart(fig_agr, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        fig_fl = go.Figure()
        fig_fl.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Contratacion"], name="Contrataciones", marker_color=C["mint"], marker_line_color="white", marker_line_width=1))
        fig_fl.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Despidos"], name="Despidos", marker_color=C["pink"], marker_line_color="white", marker_line_width=1))
        fig_fl.update_layout(**PLOT_CFG, barmode="group", height=290, title="Fuerza laboral", legend=dict(orientation="h", y=-0.3, x=0.5, xanchor="center"), xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#F0E8D8"))
        st.plotly_chart(fig_fl, use_container_width=True)
    with col2:
        fig_ex = go.Figure()
        fig_ex.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Horas_Extras"], name="Horas extra", marker_color=C["peach"], marker_line_color="white", marker_line_width=1))
        fig_ex.add_trace(go.Bar(x=df_agr["Mes_ES"], y=df_agr["Backlog_HH"], name="Backlog", marker_color=C["pink"], marker_line_color="white", marker_line_width=1))
        fig_ex.update_layout(**PLOT_CFG, barmode="group", height=290, title="Presión operativa", legend=dict(orientation="h", y=-0.3, x=0.5, xanchor="center"), xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#F0E8D8"))
        st.plotly_chart(fig_ex, use_container_width=True)

    with st.expander("Ver tabla completa del plan"):
        df_show = df_agr.drop(columns=["Mes", "Mes_ES"]).rename(columns={"Mes_F": "Mes"})
        st.dataframe(df_show, use_container_width=True)

# contenido desagregación
with TAB_DES:
    st.markdown('<div class="sec-title">Desagregación del plan en unidades por producto</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="info-box">Plan en H-H convertido a unidades vía LP · suavizado {suavizado_des} · penalización backlog ${costo_pen_des:,.0f} · inventario ${costo_inv_des:,.0f}.</div>', unsafe_allow_html=True)
    mes_resaltar = st.selectbox("Mes a resaltar", range(12), index=mes_idx, format_func=lambda i: MESES_F[i], key="mes_desag")
    mes_nm_desag = MESES[mes_resaltar]

    st.markdown('<div class="sec-title">Producción · Inventario · Demanda — vista combinada</div>', unsafe_allow_html=True)
    prod_sel_combo = st.selectbox("Producto a analizar", PRODUCTOS, format_func=lambda p: PROD_LABELS[p], key="combo_prod")
    df_combo = desag[prod_sel_combo]
    pc = PROD_COLORS[prod_sel_combo]
    pcd = PROD_COLORS_DARK[prod_sel_combo]
    fig_combo = make_subplots(rows=2, cols=1, row_heights=[0.65, 0.35], shared_xaxes=True, vertical_spacing=0.08, subplot_titles=[f"Producción & Demanda — {PROD_LABELS[prod_sel_combo]}", "Inventario final"])
    fig_combo.add_trace(go.Bar(x=df_combo["Mes_ES"], y=df_combo["Produccion"], name="Producción", marker_color=pc, opacity=0.85, marker_line_color=pcd, marker_line_width=1.5), row=1, col=1)
    fig_combo.add_trace(go.Scatter(x=df_combo["Mes_ES"], y=df_combo["Demanda"], name="Demanda", mode="lines+markers", line=dict(color=pcd, width=2.5, dash="dash"), marker=dict(size=9, color=pc, line=dict(color=pcd, width=2))), row=1, col=1)
    fig_combo.add_trace(go.Scatter(x=df_combo["Mes_ES"], y=df_combo["Produccion"], fill=None, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"), row=1, col=1)
    fig_combo.add_trace(go.Scatter(x=df_combo["Mes_ES"], y=df_combo["Demanda"], fill="tonexty", fillcolor=hex_rgba(pc, 0.18), mode="lines", line=dict(width=0), name="Brecha", hoverinfo="skip"), row=1, col=1)
    mes_row_c = df_combo[df_combo["Mes"] == mes_nm_desag]
    if not mes_row_c.empty:
        fig_combo.add_trace(go.Scatter(x=[MESES_ES[mes_resaltar]], y=[mes_row_c["Produccion"].values[0]], mode="markers", marker=dict(size=16, color=C["gold"], symbol="star", line=dict(color=pcd, width=2)), name=f"★ {MESES_F[mes_resaltar]}"), row=1, col=1)
    fig_combo.add_trace(go.Scatter(x=df_combo["Mes_ES"], y=df_combo["Inv_Fin"], fill="tozeroy", mode="lines+markers", fillcolor=hex_rgba(C["mint"], 0.35), line=dict(color="#5BAF7A", width=2), marker=dict(size=7, color="#5BAF7A"), name="Inventario final"), row=2, col=1)
    if df_combo["Backlog"].sum() > 0:
        fig_combo.add_trace(go.Bar(x=df_combo["Mes_ES"], y=df_combo["Backlog"], name="Backlog", marker_color=C["pink"], opacity=0.8), row=2, col=1)
    fig_combo.update_layout(**PLOT_CFG, height=500, barmode="group", legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center"), margin=dict(t=60, b=20))
    fig_combo.update_xaxes(showgrid=False)
    fig_combo.update_yaxes(gridcolor="#F0E8D8", row=1, col=1)
    fig_combo.update_yaxes(gridcolor="#F0E8D8", row=2, col=1)
    st.plotly_chart(fig_combo, use_container_width=True)

    st.markdown('<div class="sec-title">Plan desagregado — todos los productos</div>', unsafe_allow_html=True)
    fig_des = make_subplots(rows=3, cols=2, subplot_titles=[PROD_LABELS[p] for p in PRODUCTOS], vertical_spacing=0.12, horizontal_spacing=0.08)
    for idx, p in enumerate(PRODUCTOS):
        r, c = idx // 2 + 1, idx % 2 + 1
        df_p = desag[p]
        fig_des.add_trace(go.Bar(x=df_p["Mes_ES"], y=df_p["Produccion"], marker_color=PROD_COLORS[p], opacity=0.88, showlegend=False, marker_line_color="white", marker_line_width=1), row=r, col=c)
        fig_des.add_trace(go.Scatter(x=df_p["Mes_ES"], y=df_p["Demanda"], mode="lines+markers", line=dict(color=PROD_COLORS_DARK[p], dash="dash", width=1.5), marker=dict(size=5), showlegend=False), row=r, col=c)
        mes_row = df_p[df_p["Mes"] == mes_nm_desag]
        if not mes_row.empty:
            fig_des.add_trace(go.Scatter(x=[MESES_ES[mes_resaltar]], y=[mes_row["Produccion"].values[0]], mode="markers", marker=dict(size=14, color=C["gold"], symbol="star"), showlegend=False), row=r, col=c)
    fig_des.update_layout(**PLOT_CFG, height=680, barmode="group", margin=dict(t=60))
    for i in range(1, 4):
        for j in range(1, 3):
            fig_des.update_xaxes(showgrid=False, row=i, col=j)
            fig_des.update_yaxes(gridcolor="#F0E8D8", row=i, col=j)
    st.plotly_chart(fig_des, use_container_width=True)

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
    col_cob1, col_cob2 = st.columns([2, 1])
    with col_cob1:
        fig_cob = go.Figure(go.Bar(y=prods_c, x=cob_vals, orientation="h", marker=dict(color=list(PROD_COLORS.values()), line=dict(color=list(PROD_COLORS_DARK.values()), width=1.5)), text=[f"{v:.1f}%" for v in cob_vals], textposition="inside"))
        fig_cob.add_vline(x=100, line_dash="dash", line_color=C["coffee"], annotation_text="Meta 100%")
        fig_cob.update_layout(**PLOT_CFG, height=280, xaxis_title="Cobertura (%)", xaxis=dict(range=[0, 115]), yaxis=dict(showgrid=False), showlegend=False)
        st.plotly_chart(fig_cob, use_container_width=True)
    with col_cob2:
        st.dataframe(pd.DataFrame({"Producto": prods_c, "Producido": und_prod, "Demanda": und_dem, "Cob %": cob_vals}), use_container_width=True, height=280)

    fig_inv = go.Figure()
    for p in PRODUCTOS:
        fig_inv.add_trace(go.Scatter(x=desag[p]["Mes_ES"], y=desag[p]["Inv_Fin"], name=PROD_LABELS[p], mode="lines+markers", line=dict(color=PROD_COLORS_DARK[p], width=2), marker=dict(size=7, color=PROD_COLORS[p], line=dict(color=PROD_COLORS_DARK[p], width=1.5)), fill="tozeroy", fillcolor=hex_rgba(PROD_COLORS[p], 0.16)))
    fig_inv.update_layout(**PLOT_CFG, height=280, xaxis_title="Mes", yaxis_title="Unidades en inventario", legend=dict(orientation="h", y=-0.28, x=0.5, xanchor="center"), xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#F0E8D8"))
    st.plotly_chart(fig_inv, use_container_width=True)

# contenido simulación
with TAB_SIM:
    st.markdown(f'<div class="sec-title">Simulación de planta — {MESES_F[mes_idx]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="info-box">Variabilidad {variabilidad:.1f}× · espaciamiento de lotes {espaciamiento:.1f}× · capacidades: mezcla {mezcla_cap}, dosificado {dosificado_cap}, horno {cap_horno}, enfriamiento {enfriamiento_cap}, empaque {empaque_cap}, amasado {amasado_cap}.</div>', unsafe_allow_html=True)
    cols_p = st.columns(5)
    for i, (p, u) in enumerate(plan_mes.items()):
        hh_req = round(u * HORAS_PRODUCTO[p], 1)
        lit = round(u * LITROS_UNIDAD_BASE[p], 1)
        cols_p[i].markdown(f"""
            <div class="kpi-card" style="background:{hex_rgba(PROD_COLORS[p],0.26)};border-color:{PROD_COLORS_DARK[p]}">
              <div class="icon">{EMOJIS[p]}</div>
              <div class="val" style="font-size:1.5rem">{u:,}</div>
              <div class="lbl">{PROD_LABELS[p]}</div>
              <div class="sub">{hh_req} H-H · {lit}L</div>
            </div>
        """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    if not df_kpis.empty:
        fig_cum = go.Figure()
        for i, row in df_kpis.iterrows():
            p_key = next((p for p in PRODUCTOS if PROD_LABELS[p] == row["Producto"]), PRODUCTOS[i % len(PRODUCTOS)])
            fig_cum.add_trace(go.Bar(x=[row["Cumplimiento %"]], y=[row["Producto"]], orientation="h", marker=dict(color=PROD_COLORS[p_key], line=dict(color=PROD_COLORS_DARK[p_key], width=1.5)), text=f"{row['Cumplimiento %']:.1f}%", textposition="inside", showlegend=False))
        fig_cum.add_vline(x=100, line_dash="dash", line_color=C["coffee"])
        fig_cum.update_layout(**PLOT_CFG, height=250, xaxis=dict(range=[0, 115]), yaxis=dict(showgrid=False), xaxis_title="Cumplimiento (%)", title="Cumplimiento del plan por producto")
        st.plotly_chart(fig_cum, use_container_width=True)

        col_t1, col_t2 = st.columns(2)
        prods_kpi = [PROD_LABELS[p] for p in PRODUCTOS if PROD_LABELS[p] in df_kpis["Producto"].values]
        colores_kpi = [PROD_COLORS[p] for p in PRODUCTOS if PROD_LABELS[p] in df_kpis["Producto"].values]
        with col_t1:
            fig_tp = go.Figure(go.Bar(x=prods_kpi, y=df_kpis["Throughput (und/h)"].values, marker_color=colores_kpi, marker_line_color="white", marker_line_width=2, text=[f"{v:.1f}" for v in df_kpis["Throughput (und/h)"].values], textposition="outside"))
            fig_tp.update_layout(**PLOT_CFG, height=270, yaxis_title="und/h", showlegend=False, xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#F0E8D8"), title="Throughput por referencia")
            st.plotly_chart(fig_tp, use_container_width=True)
        with col_t2:
            fig_lt = go.Figure(go.Bar(x=prods_kpi, y=df_kpis["Lead Time (min/lote)"].values, marker_color=[PROD_COLORS_DARK[p] for p in PRODUCTOS if PROD_LABELS[p] in df_kpis["Producto"].values], marker_line_color="white", marker_line_width=2, text=[f"{v:.0f}" for v in df_kpis["Lead Time (min/lote)"].values], textposition="outside"))
            fig_lt.update_layout(**PLOT_CFG, height=270, yaxis_title="min/lote", showlegend=False, xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#F0E8D8"), title="Lead time por referencia")
            st.plotly_chart(fig_lt, use_container_width=True)

    if not df_util.empty:
        st.markdown('<div class="sec-title">Utilización de recursos y cuellos de botella</div>', unsafe_allow_html=True)
        cuellos = df_util[df_util["Cuello Botella"]]
        if not cuellos.empty:
            for _, row in cuellos.iterrows():
                st.markdown(f'<div class="pill-warn">⚠️ {REC_LABELS.get(row["Recurso"], row["Recurso"])} · {row["Util. max %"]:.1f}% · cola prom {row["Cola Prom"]:.2f}</div><br>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="pill-ok">✅ Sin cuellos de botella detectados</div><br>', unsafe_allow_html=True)

        rec_lb = [REC_LABELS.get(r, r) for r in df_util["Recurso"]]
        col_util = [C["pink"] if u >= 80 else C["butter"] if u >= 60 else C["mint"] for u in df_util["Util. max %"]]
        fig_util_g = make_subplots(rows=1, cols=2, subplot_titles=["Utilización (%)", "Cola Promedio"])
        fig_util_g.add_trace(go.Bar(x=rec_lb, y=df_util["Util. max %"], marker_color=col_util, marker_line_color="white", marker_line_width=2, text=[f"{v:.0f}%" for v in df_util["Util. max %"]], textposition="outside", showlegend=False), row=1, col=1)
        fig_util_g.add_trace(go.Bar(x=rec_lb, y=df_util["Cola Prom"], marker_color=C["lavender"], marker_line_color="white", marker_line_width=2, text=[f"{v:.2f}" for v in df_util["Cola Prom"]], textposition="outside", showlegend=False), row=1, col=2)
        fig_util_g.add_hline(y=80, line_dash="dash", line_color=C["pink"], annotation_text="⚠ 80%", row=1, col=1)
        fig_util_g.update_layout(**PLOT_CFG, height=310)
        fig_util_g.update_xaxes(showgrid=False)
        fig_util_g.update_yaxes(gridcolor="#F0E8D8")
        st.plotly_chart(fig_util_g, use_container_width=True)

    if not df_lotes.empty:
        st.markdown('<div class="sec-title">Diagrama de Gantt — flujo de lotes</div>', unsafe_allow_html=True)
        n_gantt = min(60, len(df_lotes))
        sub = df_lotes.head(n_gantt).reset_index(drop=True)
        fig_gantt = go.Figure()
        for _, row in sub.iterrows():
            fig_gantt.add_trace(go.Bar(x=[row["tiempo_sistema"]], y=[row["lote_id"]], base=[row["t_creacion"]], orientation="h", marker_color=PROD_COLORS.get(row["producto"], "#ccc"), opacity=0.85, showlegend=False, marker_line_color="white", marker_line_width=0.5, hovertemplate=(f"<b>{PROD_LABELS.get(row['producto'], row['producto'])}</b><br>Inicio: {row['t_creacion']:.0f} min<br>Duración: {row['tiempo_sistema']:.1f} min<extra></extra>")))
        for p, c in PROD_COLORS.items():
            fig_gantt.add_trace(go.Bar(x=[None], y=[None], marker_color=c, name=PROD_LABELS[p]))
        fig_gantt.update_layout(**PLOT_CFG, barmode="overlay", height=max(370, n_gantt * 8), title=f"Gantt — primeros {n_gantt} lotes", xaxis_title="Tiempo simulado (min)", legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"), yaxis=dict(showticklabels=False))
        st.plotly_chart(fig_gantt, use_container_width=True)

        st.markdown('<div class="sec-title">Distribución de tiempos en sistema por producto</div>', unsafe_allow_html=True)
        fig_violin = go.Figure()
        for p in PRODUCTOS:
            sub_v = df_lotes[df_lotes["producto"] == p]["tiempo_sistema"]
            if len(sub_v) < 3:
                continue
            fig_violin.add_trace(go.Violin(y=sub_v, name=PROD_LABELS[p], box_visible=True, meanline_visible=True, fillcolor=PROD_COLORS[p], line_color=PROD_COLORS_DARK[p], opacity=0.82))
        fig_violin.update_layout(**PLOT_CFG, height=310, yaxis_title="Tiempo en sistema (min)", showlegend=False, violinmode="overlay")
        st.plotly_chart(fig_violin, use_container_width=True)

        with st.expander("Ver KPIs detallados"):
            st.dataframe(df_kpis, use_container_width=True)

# contenido sensores
with TAB_SEN:
    st.markdown('<div class="sec-title">Sensores virtuales — monitor del horno</div>', unsafe_allow_html=True)
    if not df_sensores.empty:
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Temp. mínima", f"{df_sensores['temperatura'].min():.1f} °C")
        s2.metric("Temp. máxima", f"{df_sensores['temperatura'].max():.1f} °C")
        s3.metric("Temp. promedio", f"{df_sensores['temperatura'].mean():.1f} °C")
        s4.metric("Lecturas >200°C", excesos)

        fig_sens = make_subplots(rows=2, cols=1, shared_xaxes=True, subplot_titles=["Temperatura del horno (°C)", "Ocupación del horno"])
        fig_sens.add_trace(go.Scatter(x=df_sensores["tiempo"], y=df_sensores["temperatura"], mode="lines", name="Temp", line=dict(color=C["salmon"], width=1.8), hovertemplate="t=%{x:.0f} min<br>%{y:.1f}°C<extra></extra>"), row=1, col=1)
        fig_sens.add_hline(y=200, line_dash="dash", line_color="#c0392b", annotation_text="Límite 200°C", row=1, col=1)
        fig_sens.add_trace(go.Scatter(x=df_sensores["tiempo"], y=df_sensores["horno_ocup"], mode="lines", name="Ocupación", fill="tozeroy", fillcolor=hex_rgba(C["sky"], 0.25), line=dict(color=C["sky"], width=1.8)), row=2, col=1)
        fig_sens.update_layout(**PLOT_CFG, height=460, title="Sensores virtuales — horno en tiempo real", showlegend=False)
        fig_sens.update_xaxes(gridcolor="#F0E8D8", title_text="Tiempo simulado (min)", row=2, col=1)
        fig_sens.update_yaxes(gridcolor="#F0E8D8", row=1, col=1)
        fig_sens.update_yaxes(gridcolor="#F0E8D8", row=2, col=1)
        st.plotly_chart(fig_sens, use_container_width=True)

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            fig_ocup = go.Figure()
            fig_ocup.add_trace(go.Scatter(x=df_sensores["tiempo"], y=df_sensores["horno_ocup"], mode="lines", fill="tozeroy", fillcolor=hex_rgba(C["sky"], 0.25), line=dict(color=PROD_COLORS_DARK["Mantecadas"], width=2)))
            fig_ocup.add_hline(y=cap_horno, line_dash="dot", line_color=C["rosewood"])
            fig_ocup.update_layout(**PLOT_CFG, height=260, title="Ocupación del horno", xaxis_title="Tiempo", yaxis_title="Estaciones", showlegend=False, xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#F0E8D8"))
            st.plotly_chart(fig_ocup, use_container_width=True)
        with col_s2:
            fig_hist = go.Figure(go.Histogram(x=df_sensores["temperatura"], nbinsx=35, marker_color=C["peach"], marker_line_color="white", marker_line_width=1))
            fig_hist.add_vline(x=200, line_dash="dash", line_color="#C0392B")
            fig_hist.update_layout(**PLOT_CFG, height=260, title="Distribución de temperatura", xaxis_title="°C", yaxis_title="Frecuencia", showlegend=False, xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#F0E8D8"))
            st.plotly_chart(fig_hist, use_container_width=True)

        with st.expander("Ver tabla de lecturas"):
            st.dataframe(df_sensores.round(2), use_container_width=True)
    else:
        st.info("No hay datos de sensores para mostrar.")

# contenido escenarios
with TAB_ESC:
    st.markdown('<div class="sec-title">Análisis comparativo de escenarios</div>', unsafe_allow_html=True)
    ESCENARIOS_DEF = {
        "Base": {"fd": 1.0, "falla": False, "ft": 1.0, "cap_delta": 0, "var": variabilidad},
        "Impulso comercial +20%": {"fd": 1.2, "falla": False, "ft": 1.0, "cap_delta": 0, "var": variabilidad},
        "Caída puntual -20%": {"fd": 0.8, "falla": False, "ft": 1.0, "cap_delta": 0, "var": variabilidad},
        "Horno inestable": {"fd": 1.0, "falla": True, "ft": 1.0, "cap_delta": 0, "var": variabilidad * 1.15},
        "Restricción capacidad": {"fd": 1.0, "falla": False, "ft": 1.0, "cap_delta": -1, "var": variabilidad},
        "Capacidad ampliada": {"fd": 1.0, "falla": False, "ft": 1.0, "cap_delta": 1, "var": variabilidad},
        "Ritmo extendido": {"fd": 1.0, "falla": False, "ft": 0.80, "cap_delta": 0, "var": variabilidad},
        "Optimizado": {"fd": 1.0, "falla": False, "ft": 0.85, "cap_delta": 1, "var": max(0.8, variabilidad * 0.95)},
    }
    ESC_ICONS = {
        "Base": "🏠",
        "Impulso comercial +20%": "📈",
        "Caída puntual -20%": "📉",
        "Horno inestable": "⚠️",
        "Restricción capacidad": "⬇️",
        "Capacidad ampliada": "⬆️",
        "Ritmo extendido": "🕐",
        "Optimizado": "🚀",
    }
    escenarios_sel = st.multiselect("Selecciona escenarios a comparar", list(ESCENARIOS_DEF.keys()), default=["Base", "Impulso comercial +20%", "Horno inestable", "Ritmo extendido", "Optimizado"], key="escenarios_multiselect")

    if st.button("🚀 Comparar escenarios seleccionados", type="primary", key="btn_escenarios"):
        filas_esc = []
        prog = st.progress(0)
        for i, nm in enumerate(escenarios_sel):
            prog.progress((i + 1) / len(escenarios_sel), text=f"Simulando: {nm}")
            cfg = ESCENARIOS_DEF[nm]
            plan_esc = {p: max(int(u * cfg["fd"]), 0) for p, u in plan_mes.items()}
            cap_esc = {**cap_rec, "horno": max(cap_horno + cfg["cap_delta"], 1)}
            df_l, df_u, _ = run_simulacion_cached(tuple(plan_esc.items()), tuple(cap_esc.items()), cfg["falla"], cfg["ft"], cfg["var"], espaciamiento, semilla + i + 20)
            k = calc_kpis(df_l, plan_esc)
            u = calc_utilizacion(df_u)
            fila = {"Escenario": ESC_ICONS.get(nm, "") + " " + nm}
            if not k.empty:
                fila["Throughput (und/h)"] = round(k["Throughput (und/h)"].mean(), 2)
                fila["Lead Time (min)"] = round(k["Lead Time (min/lote)"].mean(), 2)
                fila["WIP Prom"] = round(k["WIP Prom"].mean(), 2)
                fila["Cumplimiento %"] = round(k["Cumplimiento %"].mean(), 2)
            if not u.empty:
                fila["Util. max %"] = round(u["Util. max %"].max(), 2)
                fila["Cuellos botella"] = int(u["Cuello Botella"].sum())
            fila["Lotes prod."] = len(df_l)
            filas_esc.append(fila)
        prog.empty()
        df_comp = pd.DataFrame(filas_esc)

        st.markdown('<div class="sec-title">Resultados comparativos</div>', unsafe_allow_html=True)
        st.dataframe(df_comp, use_container_width=True)

        if len(df_comp) > 1:
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                st.markdown('<div class="sec-title">Cumplimiento por escenario</div>', unsafe_allow_html=True)
                if "Cumplimiento %" in df_comp.columns:
                    col_c = [C["mint"] if v >= 90 else C["butter"] if v >= 70 else C["pink"] for v in df_comp["Cumplimiento %"]]
                    fig_ec = go.Figure(go.Bar(x=df_comp["Escenario"], y=df_comp["Cumplimiento %"], marker_color=col_c, marker_line_color="white", marker_line_width=2, text=[f"{v:.1f}%" for v in df_comp["Cumplimiento %"]], textposition="outside"))
                    fig_ec.add_hline(y=100, line_dash="dash", line_color=C["coffee"])
                    fig_ec.update_layout(**PLOT_CFG, height=300, yaxis_title="%", showlegend=False, xaxis=dict(showgrid=False, tickangle=-25), yaxis=dict(gridcolor="#F0E8D8"), margin=dict(t=30, b=90))
                    st.plotly_chart(fig_ec, use_container_width=True)
            with col_e2:
                st.markdown('<div class="sec-title">Utilización máxima</div>', unsafe_allow_html=True)
                if "Util. max %" in df_comp.columns:
                    col_u = [C["pink"] if v >= 80 else C["butter"] if v >= 60 else C["mint"] for v in df_comp["Util. max %"]]
                    fig_eu = go.Figure(go.Bar(x=df_comp["Escenario"], y=df_comp["Util. max %"], marker_color=col_u, marker_line_color="white", marker_line_width=2, text=[f"{v:.0f}%" for v in df_comp["Util. max %"]], textposition="outside"))
                    fig_eu.add_hline(y=80, line_dash="dash", line_color=C["pink"], annotation_text="⚠ 80%")
                    fig_eu.update_layout(**PLOT_CFG, height=300, yaxis_title="%", showlegend=False, xaxis=dict(showgrid=False, tickangle=-25), yaxis=dict(gridcolor="#F0E8D8"), margin=dict(t=30, b=90))
                    st.plotly_chart(fig_eu, use_container_width=True)

            st.markdown('<div class="sec-title">Radar comparativo de escenarios</div>', unsafe_allow_html=True)
            cols_radar = [c for c in df_comp.columns if c not in ["Escenario", "Cuellos botella"] and df_comp[c].dtype != "object"]
            if len(cols_radar) >= 3:
                df_norm = df_comp[cols_radar].copy()
                for c in df_norm.columns:
                    rng = df_norm[c].max() - df_norm[c].min()
                    df_norm[c] = (df_norm[c] - df_norm[c].min()) / rng if rng else 0.5
                radar_colors = list(PROD_COLORS.values()) + [C["pink"], C["sky"], C["lavender"]]
                fig_radar = go.Figure()
                for i, row in df_comp.iterrows():
                    vals = [df_norm.loc[i, c] for c in cols_radar]
                    fig_radar.add_trace(go.Scatterpolar(r=vals + [vals[0]], theta=cols_radar + [cols_radar[0]], fill="toself", name=row["Escenario"], line=dict(color=radar_colors[i % len(radar_colors)], width=2), fillcolor=hex_rgba(radar_colors[i % len(radar_colors)], 0.15)))
                fig_radar.update_layout(**PLOT_CFG, height=440, polar=dict(radialaxis=dict(visible=True, range=[0, 1], gridcolor="#E8D5B0", linecolor="#E8D5B0"), angularaxis=dict(gridcolor="#E8D5B0")), title="Comparación normalizada de escenarios", legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"))
                st.plotly_chart(fig_radar, use_container_width=True)

            if {"Cumplimiento %", "Lead Time (min)", "Util. max %", "Cuellos botella"}.issubset(df_comp.columns):
                st.markdown('<div class="sec-title">Ranking integral de escenarios</div>', unsafe_allow_html=True)
                df_rank = df_comp.copy()
                df_rank["Score"] = (
                    df_rank["Cumplimiento %"] * 0.45
                    + (100 - df_rank["Util. max %"].clip(upper=100)) * 0.20
                    + (100 - df_rank["Lead Time (min)"].rank(pct=True) * 100) * 0.20
                    + (100 - df_rank["Cuellos botella"].rank(pct=True) * 100) * 0.15
                )
                df_rank = df_rank.sort_values("Score", ascending=False).reset_index(drop=True)
                fig_rank = go.Figure(go.Bar(x=df_rank["Score"], y=df_rank["Escenario"], orientation="h", marker=dict(color=[C["mint"], C["sky"], C["lavender"], C["peach"], C["pink"]][:len(df_rank)], line=dict(color="white", width=2)), text=[f"{v:.1f}" for v in df_rank["Score"]], textposition="outside"))
                fig_rank.update_layout(**PLOT_CFG, height=320, title="Jerarquía integral", xaxis_title="Score compuesto", yaxis=dict(autorange="reversed", showgrid=False), xaxis=dict(gridcolor="#F0E8D8"), showlegend=False)
                st.plotly_chart(fig_rank, use_container_width=True)
    else:
        st.markdown('<div class="info-box" style="text-align:center;padding:2rem;">Selecciona escenarios y haz clic en comparar para construir la lectura comparativa completa.</div>', unsafe_allow_html=True)

st.markdown("---")
st.markdown("""
<div style='text-align:center;color:#B9857E;font-size:0.82rem;padding:0.4rem 0 1rem'>
  🥐 <b>Gemelo Digital — Panadería Dora del Hoyo v4.0</b> · LP agregada · desagregación · SimPy · sensores · escenarios
</div>
""", unsafe_allow_html=True)
