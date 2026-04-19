#!/usr/bin/env python3
"""
Gemelo Digital — Panadería Dora del Hoyo (v2.1)
------------------------------------------------

Esta aplicación Streamlit implementa un gemelo digital para la panadería
Dora del Hoyo. A diferencia de versiones anteriores, esta edición utiliza
una paleta de colores pastel suave y añade controles generales de
parámetros (tales como tamaño máximo de lote y participación de mercado)
así como visualizaciones adicionales que permiten explorar la demanda
histórica, su proyección, el plan agregado de producción, la
desagregación por producto y la simulación de operaciones.  El
objetivo de este rediseño es ofrecer gráficas más agradables y
flexibles sin replicar exactamente las referencias de terceros, de
modo que se ajuste a la identidad visual de la panadería.
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

###############################################################################
# PALETAS DE COLORES PASTEL
###############################################################################
# Se definen tonos pastel más suaves para evitar el café oscuro de versiones
# anteriores.  Estos colores se utilizan tanto para la interfaz como para
# las gráficas de Plotly.  Si desea ajustar algún tono, modifique los
# valores hexadecimales aquí.

PALETTE = {
    "cream":    "#FFF7E6",  # crema muy clara
    "peach":    "#FFE0C3",  # melocotón pálido
    "rose":     "#F6C9C9",  # rosa empolvado
    "mint":     "#CFF4D2",  # verde menta suave
    "sky":      "#DDECFB",  # azul cielo pastel
    "lavender": "#E7D8FA",  # lavanda ligera
    "butter":   "#F8E8B0",  # amarillo mantequilla
    "sage":     "#E3F2C1",  # verde salvia
    "caramel":  "#F4D9A9",  # caramelo claro
    "bluebell": "#D7D7F9",  # azul campanilla
}

# Colores específicos por producto usando la paleta pastel
PROD_COLORS = {
    "Brownies":           PALETTE["rose"],
    "Mantecadas":         PALETTE["mint"],
    "Mantecadas_Amapola": PALETTE["lavender"],
    "Torta_Naranja":      PALETTE["peach"],
    "Pan_Maiz":           PALETTE["sky"],
}
# Tonos ligeramente más oscuros para los contornos de barras y líneas
PROD_COLORS_DARK = {
    "Brownies":           "#D48A8A",
    "Mantecadas":         "#78C987",
    "Mantecadas_Amapola": "#9D7AC4",
    "Torta_Naranja":      "#E6A96C",
    "Pan_Maiz":           "#80A8D7",
}
# Etiquetas legibles de los productos
PROD_LABELS = {
    "Brownies": "Brownies",
    "Mantecadas": "Mantecadas",
    "Mantecadas_Amapola": "Mant. Amapola",
    "Torta_Naranja": "Torta Naranja",
    "Pan_Maiz": "Pan de Maíz",
}

###############################################################################
# DATOS MAESTROS
###############################################################################
# Conjunto de productos, meses y demanda histórica.  Estos valores son
# arbitrarios y pueden ajustarse para representar otras realidades.

PRODUCTOS = ["Brownies", "Mantecadas", "Mantecadas_Amapola", "Torta_Naranja", "Pan_Maiz"]
MESES     = ["January","February","March","April","May","June","July","August","September","October","November","December"]
MESES_ES  = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]
MESES_F   = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

# Demanda histórica en unidades para cada producto por mes (12 meses).  Para
# proyectar demanda futura se utilizará un suavizado simple.  Si se desea
# utilizar litros en lugar de unidades, se puede multiplicar por el valor
# introducido en la barra lateral "Litros por unidad" más adelante.
DEM_HISTORICA = {
    "Brownies":           [315,804,734,541,494, 59,315,803,734,541,494, 59],
    "Mantecadas":         [125,780,432,910,275, 68,512,834,690,455,389,120],
    "Mantecadas_Amapola": [320,710,520,251,631,150,330,220,710,610,489,180],
    "Torta_Naranja":      [100,250,200,101,190, 50,100,220,200,170,180,187],
    "Pan_Maiz":           [330,140,143, 73, 83, 48, 70, 89,118, 83, 67, 87],
}
# Horas de trabajo necesarias para producir una unidad de cada producto
HORAS_PRODUCTO = {
    "Brownies": 0.866,
    "Mantecadas": 0.175,
    "Mantecadas_Amapola": 0.175,
    "Torta_Naranja": 0.175,
    "Pan_Maiz": 0.312,
}
# Rutas de procesamiento: cada producto pasa por recursos en cierto orden con
# tiempos mínimos y máximos (en minutos).  Estos tiempos se ajustarán con
# factores estocásticos en la simulación.
RUTAS = {
    "Brownies": [
        ("Mezclado",    "mezcla",      12, 18),
        ("Moldeado",    "dosificado",  8, 14),
        ("Horneado",    "horno",       30, 40),
        ("Enfriamiento","enfriamiento",25, 35),
        ("Corte/Empaque","empaque",     8, 12),
    ],
    "Mantecadas": [
        ("Mezclado",    "mezcla",      12, 18),
        ("Dosificado",  "dosificado", 16, 24),
        ("Horneado",    "horno",       20, 30),
        ("Enfriamiento","enfriamiento",35, 55),
        ("Empaque",     "empaque",      4,  6),
    ],
    "Mantecadas_Amapola": [
        ("Mezclado",    "mezcla",      12, 18),
        ("Inc. Semillas","mezcla",      8, 12),
        ("Dosificado",  "dosificado", 16, 24),
        ("Horneado",    "horno",       20, 30),
        ("Enfriamiento","enfriamiento",36, 54),
        ("Empaque",     "empaque",      4,  6),
    ],
    "Torta_Naranja": [
        ("Mezclado",    "mezcla",      16, 24),
        ("Dosificado",  "dosificado",  8, 12),
        ("Horneado",    "horno",       32, 48),
        ("Enfriamiento","enfriamiento",48, 72),
        ("Desmolde",    "dosificado",  8, 12),
        ("Empaque",     "empaque",      8, 12),
    ],
    "Pan_Maiz": [
        ("Mezclado",    "mezcla",      12, 18),
        ("Amasado",     "amasado",     16, 24),
        ("Moldeado",    "dosificado", 12, 18),
        ("Horneado",    "horno",       28, 42),
        ("Enfriamiento","enfriamiento",36, 54),
        ("Empaque",     "empaque",      4,  6),
    ],
}
# Tamaño base de lote y capacidad base de cada recurso
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
# Parámetros por defecto utilizados en el modelo de programación lineal
PARAMS_DEFAULT = {
    "Ct": 4_310,
    "Ht": 100_000,
    "PIt": 100_000,
    "CRt": 11_364,
    "COt": 14_205,
    "CW_mas": 14_204,
    "CW_menos": 15_061,
    "M": 1,
    "LR_inicial": 44*4*10,
    "inv_seg": 0.0,
}
# Inventario inicial por producto
INV_INICIAL = {p: 0 for p in PRODUCTOS}

###############################################################################
# FUNCIONES AUXILIARES
###############################################################################

def demanda_horas_hombre(factor=1.0):
    """Calcula la demanda mensual en horas-hombre agregando todos los productos.
    El parámetro `factor` ajusta la demanda proporcionalmente.
    """
    return {
        mes: round(sum(DEM_HISTORICA[p][i] * HORAS_PRODUCTO[p] for p in PRODUCTOS) * factor, 4)
        for i, mes in enumerate(MESES)
    }

def pronostico_simple(serie, meses_extra=3):
    """Aplica suavizado exponencial simple con α=0.3 y genera una proyección.
    Devuelve la serie suavizada y la serie futura de longitud `meses_extra`.
    """
    alpha = 0.3
    nivel = serie[0]
    suavizada = []
    for v in serie:
        nivel = alpha * v + (1 - alpha) * nivel
        suavizada.append(nivel)
    futuro = []
    last = suavizada[-1]
    # estimación de tendencia simple
    trend = (suavizada[-1] - suavizada[-4]) / 3 if len(suavizada) >= 4 else 0
    for _ in range(meses_extra):
        last = last + alpha * trend
        futuro.append(round(last, 1))
    return suavizada, futuro

@st.cache_data(show_spinner=False)
def run_agregacion(factor_demanda=1.0, params_tuple=None):
    """Resuelve el problema de programación lineal para el plan agregado.
    Devuelve un DataFrame con las variables de decisión por mes y el costo total.
    """
    params = PARAMS_DEFAULT.copy()
    if params_tuple:
        params.update(dict(params_tuple))
    # demanda por mes en horas-hombre
    dem_h = demanda_horas_hombre(factor_demanda)
    # alias locales
    Ct = params["Ct"]
    Ht = params["Ht"]
    PIt = params["PIt"]
    CRt = params["CRt"]
    COt = params["COt"]
    Wm = params["CW_mas"]
    Wd = params["CW_menos"]
    M = params["M"]
    LRi = params["LR_inicial"]
    # modelo de programación lineal
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
    mdl += lpSum(Ct * P[t] + Ht * I[t] + PIt * S[t] + CRt * LR[t] + COt * LO[t] + Wm * Wmas[t] + Wd * Wmenos[t] for t in MESES)
    for idx, t in enumerate(MESES):
        d = dem_h[t]
        tp = MESES[idx - 1] if idx > 0 else None
        if idx == 0:
            mdl += NI[t] == 0 + P[t] - d
        else:
            mdl += NI[t] == NI[tp] + P[t] - d
        mdl += NI[t] == I[t] - S[t]
        mdl += LU[t] + LO[t] == M * P[t]
        mdl += LU[t] <= LR[t]
        if idx == 0:
            mdl += LR[t] == LRi + Wmas[t] - Wmenos[t]
        else:
            mdl += LR[t] == LR[tp] + Wmas[t] - Wmenos[t]
    mdl.solve(PULP_CBC_CMD(msg=False))
    costo = value(mdl.objective)
    ini_l, fin_l = [], []
    for idx, t in enumerate(MESES):
        ini = 0.0 if idx == 0 else fin_l[-1]
        ini_l.append(ini)
        fin_l.append(ini + (P[t].varValue or 0) - dem_h[t])
    df = pd.DataFrame({
        "Mes": MESES,
        "Mes_F": MESES_F,
        "Mes_ES": MESES_ES,
        "Demanda_HH":      [round(dem_h[t], 2) for t in MESES],
        "Produccion_HH":   [round(P[t].varValue or 0, 2) for t in MESES],
        "Backlog_HH":      [round(S[t].varValue or 0, 2) for t in MESES],
        "Horas_Regulares": [round(LR[t].varValue or 0, 2) for t in MESES],
        "Horas_Extras":    [round(LO[t].varValue or 0, 2) for t in MESES],
        "Inv_Ini_HH":      [round(v, 2) for v in ini_l],
        "Inv_Fin_HH":      [round(v, 2) for v in fin_l],
        "Contratacion":    [round(Wmas[t].varValue or 0, 2) for t in MESES],
        "Despidos":        [round(Wmenos[t].varValue or 0, 2) for t in MESES],
    })
    return df, costo

@st.cache_data(show_spinner=False)
def run_desagregacion(prod_hh_items, factor_demanda=1.0):
    """Desagrega el plan agregado en unidades por producto para cada mes.
    Devuelve un dict de DataFrames por producto.
    """
    prod_hh = dict(prod_hh_items)
    mdl = LpProblem("Desagregacion", LpMinimize)
    X = {(p, t): LpVariable(f"X_{p}_{t}", lowBound=0) for p in PRODUCTOS for t in MESES}
    I = {(p, t): LpVariable(f"I_{p}_{t}", lowBound=0) for p in PRODUCTOS for t in MESES}
    S = {(p, t): LpVariable(f"S_{p}_{t}", lowBound=0) for p in PRODUCTOS for t in MESES}
    mdl += lpSum(100_000 * I[p, t] + 150_000 * S[p, t] for p in PRODUCTOS for t in MESES)
    for idx, t in enumerate(MESES):
        tp = MESES[idx - 1] if idx > 0 else None
        mdl += (lpSum(HORAS_PRODUCTO[p] * X[p, t] for p in PRODUCTOS) <= prod_hh[t], f"Cap_{t}")
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
                "Inv_Ini": ini,
                "Inv_Fin": iv,
                "Backlog": sv,
            })
        resultados[p] = pd.DataFrame(filas)
    return resultados

@st.cache_data(show_spinner=False)
def run_simulacion_cached(plan_items, cap_items, falla, factor_t, semilla=42):
    """Simula la producción para un plan mensual dado.  Se utiliza SimPy
    y se registran los tiempos de cada lote y de uso de recursos.
    """
    plan_unidades = dict(plan_items)
    cap_recursos = dict(cap_items)
    random.seed(semilla)
    np.random.seed(semilla)
    lotes_data, uso_rec, sensores = [], [], []

    def sensor_horno(env, recursos):
        while True:
            ocp = recursos["horno"].count
            temp = round(np.random.normal(160 + ocp * 20, 5), 2)
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
            tp = random.uniform(tmin, tmax) * escala * factor_t
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
    # Generación de lotes según plan (poisson/simple)
    for prod, unid in plan_unidades.items():
        if unid <= 0:
            continue
        tam = TAMANO_LOTE_BASE[prod]
        n = math.ceil(unid / tam)
        tasa = dur_mes / max(n, 1)
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
    df_sens = pd.DataFrame(sensores) if sensores else pd.DataFrame()
    return df_lotes, df_uso, df_sens

def calc_utilizacion(df_uso: pd.DataFrame) -> pd.DataFrame:
    """Calcula métricas de utilización de cada recurso a partir del log de uso.
    Devuelve un DataFrame con porcentaje de utilización, cola promedio y si es
    cuello de botella (utilización >= 80% o cola media > 0.5).
    """
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

def calc_kpis(df_lotes: pd.DataFrame, plan: dict) -> pd.DataFrame:
    """Calcula indicadores clave de desempeño (KPIs) a partir de los resultados
    de la simulación y el plan.  Incluye throughput, cycle time, lead time,
    WIP y cumplimiento del plan.
    """
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

###############################################################################
# INTERFAZ STREAMLIT
###############################################################################

st.set_page_config(
    page_title="Gemelo Digital · Dora del Hoyo — Pastel",
    page_icon="🥐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Estilos CSS personalizados.  Usamos tonos pastel para el encabezado y
# elementos interactivos.  Los identificadores de clase corresponden a
# componentes de Streamlit.
st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@400;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600&display=swap');
html,body,[class*="css"]{{font-family:'Plus Jakarta Sans',sans-serif;background:{PALETTE['cream']};}}
.hero{{background:linear-gradient(135deg,{PALETTE['sky']} 0%,{PALETTE['rose']} 60%,{PALETTE['butter']} 100%);
  padding:2rem 2.5rem 1.6rem;border-radius:20px;margin-bottom:1.5rem;
  box-shadow:0 10px 32px rgba(0,0,0,0.05);position:relative;overflow:hidden;}}
.hero::before{{content:"🥐";font-size:8rem;position:absolute;right:1rem;top:-1rem;
  opacity:0.08;transform:rotate(-10deg);}}
.hero h1{{font-family:'Fraunces',serif;color:#444;font-size:2.1rem;margin:0;letter-spacing:-0.5px;}}
.hero p{{color:#555;margin:0.35rem 0 0;font-size:0.95rem;font-weight:300;}}
.hero .badge{{display:inline-block;background:rgba(255,255,255,0.3);color:#333;
  padding:0.25rem 0.75rem;border-radius:20px;font-size:0.78rem;margin-top:0.5rem;
  margin-right:0.4rem;border:1px solid rgba(255,255,255,0.4);}}
.kpi-card{{background:white;border-radius:14px;padding:1rem 1.1rem;
  box-shadow:0 3px 10px rgba(0,0,0,0.05);border:1px solid rgba(0,0,0,0.05);
  text-align:center;transition:transform 0.2s;}}
.kpi-card:hover{{transform:translateY(-3px);box-shadow:0 6px 18px rgba(0,0,0,0.08);}}
.kpi-card .icon{{font-size:1.6rem;margin-bottom:0.25rem;}}
.kpi-card .val{{font-family:'Fraunces',serif;font-size:1.7rem;color:#333;line-height:1;margin:0.1rem 0;}}
.kpi-card .lbl{{font-size:0.7rem;color:#666;text-transform:uppercase;letter-spacing:1px;font-weight:600;}}
.kpi-card .sub{{font-size:0.75rem;color:#999;margin-top:0.2rem;}}
.sec-title{{font-family:'Fraunces',serif;font-size:1.25rem;color:#333;
  border-left:4px solid {PALETTE['caramel']};padding-left:0.75rem;margin:1.4rem 0 0.7rem;}}
.info-box{{background:linear-gradient(135deg,rgba(255,255,255,0.5),rgba(255,255,255,0.8));
  border:1px solid rgba(0,0,0,0.05);border-radius:12px;
  padding:0.7rem 1rem;font-size:0.85rem;color:#444;margin:0.4rem 0 0.8rem;}}
.pill-ok{{background:{PALETTE['mint']};color:#2E7D32;padding:0.35rem 1rem;
  border-radius:20px;font-size:0.8rem;font-weight:600;display:inline-block;}}
.pill-warn{{background:{PALETTE['rose']};color:#B71C1C;padding:0.35rem 1rem;
  border-radius:20px;font-size:0.8rem;font-weight:600;display:inline-block;}}
[data-testid="stSidebar"]{{background:{PALETTE['sky']} !important;}}
[data-testid="stSidebar"] label,[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,[data-testid="stSidebar"] div{{color:#333 !important;}}
[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3{{color:#222 !important;font-family:'Fraunces',serif !important;}}
[data-testid="stSidebar"] hr{{border-color:{PALETTE['caramel']}60 !important;}}
.stTabs [data-baseweb="tab"]{{font-family:'Plus Jakarta Sans',sans-serif;font-weight:500;color:#555;}}
.stTabs [aria-selected="true"]{{color:#222 !important;}}
</style>
""",
    unsafe_allow_html=True,
)

# BARRA LATERAL — PARÁMETROS
with st.sidebar:
    st.markdown("## 🥐 Dora del Hoyo")
    st.markdown("*Gemelo Digital v2.1*")
    st.markdown("---")
    # Parámetros generales
    st.markdown("### ⚙️ Parámetros generales")
    meses_pronostico = st.slider("Meses a pronosticar", 1, 6, 3)
    lote_max = st.number_input(
        "Tamaño máximo de lote (unidades)",
        min_value=5,
        value=max(TAMANO_LOTE_BASE.values()),
        step=1,
    )
    litros_unit = st.number_input(
        "Litros por unidad de producto",
        min_value=0.1,
        max_value=2.0,
        value=0.5,
        step=0.1,
    )
    market_share = st.slider(
        "Participación de mercado (%)", 0.01, 0.20, 0.05, 0.01
    )
    st.markdown("### 📅 Mes a simular")
    mes_idx = st.selectbox(
        "Mes", range(12), index=1, format_func=lambda i: MESES_F[i], label_visibility="collapsed"
    )
    st.markdown("### 📊 Demanda")
    factor_demanda_base = st.slider(
        "Factor de demanda", 0.5, 2.0, 1.0, 0.05
    )
    st.markdown("### 🏭 Producción")
    cap_horno = st.slider("Capacidad del horno (estaciones)", 1, 6, 3)
    falla_horno = st.checkbox("⚠️ Simular fallas en horno")
    doble_turno = st.checkbox("🕐 Doble turno (−20% tiempo)")
    semilla = st.number_input("Semilla aleatoria", value=42, step=1)
    st.markdown("### 💰 Costos (COP)")
    with st.expander("⚙️ Configuración del modelo LP"):
        ct = st.number_input("Costo producción/und (Ct)", value=PARAMS_DEFAULT["Ct"], step=100)
        crt = st.number_input("Costo hora regular (CRt)", value=PARAMS_DEFAULT["CRt"], step=100)
        cot = st.number_input("Costo hora extra (COt)", value=PARAMS_DEFAULT["COt"], step=100)
        ht = st.number_input("Costo mantener inv. (Ht)", value=PARAMS_DEFAULT["Ht"], step=1000)
        pit = st.number_input("Penalización backlog (PIt)", value=PARAMS_DEFAULT["PIt"], step=1000)
        cwp = st.number_input("Costo contratar (CW+)", value=PARAMS_DEFAULT["CW_mas"], step=100)
        cwm = st.number_input("Costo despedir (CW−)", value=PARAMS_DEFAULT["CW_menos"], step=100)
        trab = st.number_input("Trabajadores iniciales", value=10, step=1)
    st.markdown("---")
    st.markdown(
        f"<div style='font-size:0.75rem;color:#555;'>📍 Panadería Dora del Hoyo<br>🔢 SimPy · PuLP · Streamlit</div>",
        unsafe_allow_html=True,
    )

# ESCALA DE DEMANDA: se combina el factor base con la participación de mercado
factor_demanda = factor_demanda_base * (1 + market_share)

# Construcción del diccionario de parámetros personalizados para el modelo LP
params_custom = {
    **PARAMS_DEFAULT,
    "Ct": ct,
    "CRt": crt,
    "COt": cot,
    "Ht": ht,
    "PIt": pit,
    "CW_mas": cwp,
    "CW_menos": cwm,
    "LR_inicial": 44 * 4 * int(trab),
}

# Ejecución del modelo agregado de producción
with st.spinner("⚙️ Optimizando plan agregado..."):
    df_agr, costo = run_agregacion(factor_demanda, tuple(sorted(params_custom.items())))

# Desagregación a unidades por producto
prod_hh = dict(zip(df_agr["Mes"], df_agr["Produccion_HH"]))
with st.spinner("🔢 Desagregando por producto..."):
    desag = run_desagregacion(tuple(prod_hh.items()), factor_demanda)

# Selección del mes actual para simulación y preparación del plan
mes_nm = MESES[mes_idx]
plan_mes = {
    p: int(desag[p].loc[desag[p]["Mes"] == mes_nm, "Produccion"].values[0])
    for p in PRODUCTOS
}
cap_rec = {**CAPACIDAD_BASE, "horno": int(cap_horno)}
factor_t = 0.80 if doble_turno else 1.0

# Simulación de la planta
with st.spinner("🏭 Simulando planta de producción..."):
    df_lotes, df_uso, df_sensores = run_simulacion_cached(
        tuple(plan_mes.items()), tuple(cap_rec.items()), falla_horno, factor_t, int(semilla)
    )

# Cálculo de KPIs y utilización
df_kpis = calc_kpis(df_lotes, plan_mes)
df_util = calc_utilizacion(df_uso)

# METRICAS RESUMEN
cum_avg = df_kpis["Cumplimiento %"].mean() if not df_kpis.empty else 0
util_max = df_util["Utilizacion_%"].max() if not df_util.empty else 0
lotes_n = len(df_lotes) if not df_lotes.empty else 0
temp_avg = df_sensores["temperatura"].mean() if not df_sensores.empty else 0
excesos = int((df_sensores["temperatura"] > 200).sum()) if not df_sensores.empty else 0

# ENCABEZADO (hero) con información resumida
st.markdown(
    f"""
    <div class="hero">
      <h1>Gemelo Digital — Dora del Hoyo</h1>
      <p>Optimización de producción · Simulación discreta · Análisis what‑if</p>
      <span class="badge">📅 {MESES_F[mes_idx]}</span>
      <span class="badge">📈 Demanda ×{factor_demanda:.2f}</span>
      <span class="badge">🔥 Horno: {cap_horno} est.</span>
      {"<span class='badge'>⚠️ Falla activa</span>" if falla_horno else ""}
      {"<span class='badge'>🕐 Doble turno</span>" if doble_turno else ""}
    </div>
    """,
    unsafe_allow_html=True,
)

# Tarjetas KPI principales
k1, k2, k3, k4, k5 = st.columns(5)

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

kpi_card(k1, "💰", f"${costo/1e6:.1f}M", "Costo Óptimo", "COP · Plan anual")
kpi_card(k2, "📦", f"{lotes_n:,}", "Lotes Simulados", MESES_F[mes_idx])
kpi_card(k3, "✅", f"{cum_avg:.1f}%", "Cumplimiento", "Producción vs Plan")
kpi_card(
    k4,
    "⚙️",
    f"{util_max:.0f}%",
    "Utilización Máx.",
    "⚠️ Cuello" if util_max >= 80 else "✓ OK",
)
kpi_card(
    k5,
    "🌡️",
    f"{temp_avg:.0f}°C",
    "Temperatura horno",
    f"⚠️ {excesos} excesos" if excesos else "✓ Sin excesos",
)

# Configuración general para las gráficas de Plotly
PLOT_CFG = dict(
    template="plotly_white",
    font=dict(family="Plus Jakarta Sans"),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(255,255,255,0.9)",
)

# Definición de pestañas principales
tabs = st.tabs([
    "📊 Demanda & Pronóstico",
    "📋 Plan Agregado",
    "📦 Desagregación",
    "🏭 Simulación",
    "🌡️ Sensores",
    "🔬 Escenarios",
])

###############################################################################
# PESTAÑA 1 — DEMANDA Y PRONÓSTICO
###############################################################################
with tabs[0]:
    st.markdown(
        '<div class="sec-title">📈 Demanda histórica y proyección por producto</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="info-box">Se utiliza un suavizado exponencial simple (α=0.3) para estimar la tendencia futura. El factor de demanda y la participación de mercado ajustan la escala.</div>',
        unsafe_allow_html=True,
    )
    # Gráfico de líneas con demanda histórica y pronóstico para cada producto
    fig_pro = go.Figure()
    for p in PRODUCTOS:
        serie = [v * factor_demanda for v in DEM_HISTORICA[p]]
        suav, futuro = pronostico_simple(serie, meses_pronostico)
        # serie histórica
        fig_pro.add_trace(
            go.Scatter(
                x=MESES_ES,
                y=serie,
                mode="lines",
                name=PROD_LABELS[p],
                line=dict(color=PROD_COLORS_DARK[p], width=2.0),
                legendgroup=p,
                showlegend=True,
            )
        )
        # pronóstico (línea punteada)
        meses_fut = [f"P+{j+1}" for j in range(meses_pronostico)]
        x_fut = [MESES_ES[-1]] + meses_fut
        y_fut = [suav[-1]] + futuro
        fig_pro.add_trace(
            go.Scatter(
                x=x_fut,
                y=y_fut,
                mode="lines+markers",
                line=dict(color=PROD_COLORS_DARK[p], width=1.7, dash="dot"),
                marker=dict(
                    size=8,
                    symbol="circle",
                    color=PROD_COLORS[p],
                    line=dict(color=PROD_COLORS_DARK[p], width=1.5),
                ),
                legendgroup=p,
                showlegend=False,
            )
        )
    fig_pro.add_vline(
        x=len(MESES_ES) - 1,
        line_dash="dash",
        line_color=PALETTE["caramel"],
        annotation_text="Pronóstico",
        annotation_font_color=PALETTE["caramel"],
        annotation_position="top right",
    )
    fig_pro.update_layout(
        **PLOT_CFG,
        height=420,
        title="Demanda Histórica y Proyección",
        xaxis_title="Mes",
        yaxis_title="Unidades",
        legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
        xaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.05)"),
        yaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.05)"),
    )
    st.plotly_chart(fig_pro, use_container_width=True)

    # Gráfico adicional: participación por producto en cada mes (barra apilada)
    st.markdown(
        '<div class="sec-title">🍰 Participación por producto</div>',
        unsafe_allow_html=True,
    )
    z_particip = []
    for p in PRODUCTOS:
        z_particip.append([DEM_HISTORICA[p][i] * factor_demanda for i in range(12)])
    fig_stack = go.Figure()
    for idx, p in enumerate(PRODUCTOS):
        fig_stack.add_trace(
            go.Bar(
                x=MESES_ES,
                y=z_particip[idx],
                name=PROD_LABELS[p],
                marker=dict(color=PROD_COLORS[p]),
                hovertemplate="%{x}: %{y:.0f} und<extra></extra>",
            )
        )
    fig_stack.update_layout(
        **PLOT_CFG,
        barmode="stack",
        height=300,
        xaxis_title="Mes",
        yaxis_title="Unidades",
        legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor="rgba(0,0,0,0.05)"),
    )
    st.plotly_chart(fig_stack, use_container_width=True)

###############################################################################
# PESTAÑA 2 — PLAN AGREGADO
###############################################################################
with tabs[1]:
    st.markdown(
        '<div class="sec-title">📋 Planeación Agregada — Programación Lineal</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="info-box"><b>{int(trab)} trabajadores</b> iniciales · {int(44*4*trab):,} H-H regulares/mes · CRt: ${crt:,} · COt: ${cot:,} · Ht: ${ht:,} COP</div>',
        unsafe_allow_html=True,
    )
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("💰 Costo Total", f"${costo:,.0f} COP")
    m2.metric("⏰ Horas Extra", f"{df_agr['Horas_Extras'].sum():,.0f} H-H")
    m3.metric("📉 Backlog Total", f"{df_agr['Backlog_HH'].sum():,.0f} H-H")
    m4.metric(
        "👥 Contrat. Netas",
        f"{df_agr['Contratacion'].sum() - df_agr['Despidos'].sum():+.0f} pers.",
    )
    st.markdown(
        '<div class="sec-title">🛠️ Producción vs Demanda (H-H)</div>',
        unsafe_allow_html=True,
    )
    # Gráfico principal de plan agregado: inventario inicial, producción y demanda
    fig_agr = go.Figure()
    fig_agr.add_trace(
        go.Bar(
            x=df_agr["Mes_ES"],
            y=df_agr["Inv_Ini_HH"],
            name="Inventario inicial",
            marker_color=PALETTE["lavender"],
            marker_line_color="white",
            marker_line_width=1,
        )
    )
    fig_agr.add_trace(
        go.Bar(
            x=df_agr["Mes_ES"],
            y=df_agr["Produccion_HH"],
            name="Producción",
            marker_color=PALETTE["peach"],
            marker_line_color="white",
            marker_line_width=1,
        )
    )
    fig_agr.add_trace(
        go.Scatter(
            x=df_agr["Mes_ES"],
            y=df_agr["Demanda_HH"],
            mode="lines+markers",
            name="Demanda",
            line=dict(color=PALETTE["caramel"], dash="dash", width=2.5),
            marker=dict(size=7, color=PALETTE["caramel"]),
        )
    )
    fig_agr.add_trace(
        go.Scatter(
            x=df_agr["Mes_ES"],
            y=df_agr["Horas_Regulares"],
            mode="lines",
            name="Capacidad Regular",
            line=dict(color=PALETTE["mint"], dash="dot", width=2),
        )
    )
    fig_agr.update_layout(
        **PLOT_CFG,
        barmode="stack",
        height=370,
        title=f"Costo Óptimo LP: COP ${costo:,.0f}",
        xaxis_title="Mes",
        yaxis_title="Horas-Hombre",
        legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor="rgba(0,0,0,0.05)"),
    )
    st.plotly_chart(fig_agr, use_container_width=True)

    # Gráficos secundarios: fuerza laboral y horas extra/backlog
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            '<div class="sec-title">👷 Fuerza laboral</div>',
            unsafe_allow_html=True,
        )
        fig_fl = go.Figure()
        fig_fl.add_trace(
            go.Bar(
                x=df_agr["Mes_ES"],
                y=df_agr["Contratacion"],
                name="Contrataciones",
                marker_color=PALETTE["sage"],
                marker_line_color="white",
                marker_line_width=1,
            )
        )
        fig_fl.add_trace(
            go.Bar(
                x=df_agr["Mes_ES"],
                y=df_agr["Despidos"],
                name="Despidos",
                marker_color=PALETTE["rose"],
                marker_line_color="white",
                marker_line_width=1,
            )
        )
        fig_fl.update_layout(
            **PLOT_CFG,
            barmode="group",
            height=300,
            legend=dict(orientation="h", y=-0.3, x=0.5, xanchor="center"),
            xaxis=dict(showgrid=False),
            yaxis=dict(gridcolor="rgba(0,0,0,0.05)"),
        )
        st.plotly_chart(fig_fl, use_container_width=True)
    with col2:
        st.markdown(
            '<div class="sec-title">⏱️ Horas extra & Backlog</div>',
            unsafe_allow_html=True,
        )
        fig_ex = go.Figure()
        fig_ex.add_trace(
            go.Bar(
                x=df_agr["Mes_ES"],
                y=df_agr["Horas_Extras"],
                name="Horas extra",
                marker_color=PALETTE["butter"],
                marker_line_color="white",
                marker_line_width=1,
            )
        )
        fig_ex.add_trace(
            go.Bar(
                x=df_agr["Mes_ES"],
                y=df_agr["Backlog_HH"],
                name="Backlog",
                marker_color=PALETTE["rose"],
                marker_line_color="white",
                marker_line_width=1,
            )
        )
        fig_ex.update_layout(
            **PLOT_CFG,
            barmode="group",
            height=300,
            legend=dict(orientation="h", y=-0.3, x=0.5, xanchor="center"),
            xaxis=dict(showgrid=False),
            yaxis=dict(gridcolor="rgba(0,0,0,0.05)"),
        )
        st.plotly_chart(fig_ex, use_container_width=True)
    with st.expander("📄 Ver tabla completa del plan"):
        df_show = df_agr.drop(columns=["Mes", "Mes_ES"]).rename(columns={"Mes_F": "Mes"})
        st.dataframe(
            df_show.style.format(
                {c: "{:, .1f}" for c in df_show.columns if c != "Mes"}
            ).background_gradient(
                subset=["Produccion_HH", "Horas_Extras"], cmap="YlOrBr"
            ),
            use_container_width=True,
        )

###############################################################################
# PESTAÑA 3 — DESAGREGACIÓN
###############################################################################
with tabs[2]:
    st.markdown(
        '<div class="sec-title">📦 Desagregación del plan en unidades por producto</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="info-box">El plan agregado en horas-hombre se transforma en unidades por producto mediante optimización lineal. Puede resaltarse un mes específico.</div>',
        unsafe_allow_html=True,
    )
    mes_resaltar = st.selectbox(
        "Mes a resaltar ★", range(12), index=mes_idx, format_func=lambda i: MESES_F[i], key="mes_desag"
    )
    mes_nm_desag = MESES[mes_resaltar]
    # Crear subgráficos por producto
    fig_des = make_subplots(
        rows=3,
        cols=2,
        subplot_titles=[PROD_LABELS[p] for p in PRODUCTOS],
        vertical_spacing=0.12,
        horizontal_spacing=0.08,
    )
    for idx, p in enumerate(PRODUCTOS):
        r, c = idx // 2 + 1, idx % 2 + 1
        df_p = desag[p]
        # Producción por mes
        fig_des.add_trace(
            go.Bar(
                x=df_p["Mes_ES"],
                y=df_p["Produccion"],
                marker_color=PROD_COLORS[p],
                opacity=0.9,
                showlegend=False,
                marker_line_color="white",
                marker_line_width=1,
                hovertemplate="%{x}: %{y:.0f} und<extra></extra>",
            ),
            row=r,
            col=c,
        )
        # Demanda real
        fig_des.add_trace(
            go.Scatter(
                x=df_p["Mes_ES"],
                y=df_p["Demanda"],
                mode="lines+markers",
                line=dict(color=PROD_COLORS_DARK[p], dash="dash", width=1.5),
                marker=dict(size=5),
                showlegend=False,
            ),
            row=r,
            col=c,
        )
        # Estrella de resaltado
        mes_row = df_p[df_p["Mes"] == mes_nm_desag]
        if not mes_row.empty:
            fig_des.add_trace(
                go.Scatter(
                    x=[MESES_ES[mes_resaltar]],
                    y=[mes_row["Produccion"].values[0]],
                    mode="markers",
                    marker=dict(size=14, color=PALETTE["caramel"], symbol="star"),
                    showlegend=False,
                ),
                row=r,
                col=c,
            )
    fig_des.update_layout(
        **PLOT_CFG,
        height=650,
        barmode="group",
        title="Producción planificada vs Demanda por producto (unidades/mes)",
        margin=dict(t=60),
    )
    # Ajuste de grillas
    for i in range(1, 4):
        for j in range(1, 3):
            fig_des.update_xaxes(showgrid=False, row=i, col=j)
            fig_des.update_yaxes(gridcolor="rgba(0,0,0,0.05)", row=i, col=j)
    st.plotly_chart(fig_des, use_container_width=True)
    # Cobertura anual
    st.markdown(
        '<div class="sec-title">🎯 Cobertura de demanda anual</div>',
        unsafe_allow_html=True,
    )
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
        fig_cob = go.Figure()
        fig_cob.add_trace(
            go.Bar(
                y=prods_c,
                x=cob_vals,
                orientation="h",
                marker=dict(color=list(PROD_COLORS.values()), line=dict(color="white", width=2)),
                text=[f"{v:.1f}%" for v in cob_vals],
                textposition="inside",
                textfont=dict(color="#333", size=12),
                hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
            )
        )
        fig_cob.add_vline(
            x=100,
            line_dash="dash",
            line_color=PALETTE["caramel"],
            annotation_text="Meta 100%",
            annotation_font_color=PALETTE["caramel"],
        )
        fig_cob.update_layout(
            **PLOT_CFG,
            height=260,
            xaxis_title="Cobertura (%)",
            xaxis=dict(range=[0, 115]),
            yaxis=dict(showgrid=False),
            margin=dict(t=20, b=20),
            showlegend=False,
        )
        st.plotly_chart(fig_cob, use_container_width=True)
    with col_cob2:
        df_cob = pd.DataFrame(
            {
                "Producto": prods_c,
                "Producido": und_prod,
                "Demanda": und_dem,
                "Cobertura %": cob_vals,
            }
        )
        st.dataframe(
            df_cob.style.format(
                {"Producido": "{:,.0f}", "Demanda": "{:,.0f}", "Cobertura %": "{:.1f}%"}
            ).background_gradient(subset=["Cobertura %"], cmap="YlGn"),
            use_container_width=True,
            height=260,
        )
    # Inventario final
    st.markdown(
        '<div class="sec-title">📦 Inventario final proyectado</div>',
        unsafe_allow_html=True,
    )
    fig_inv = go.Figure()
    for p in PRODUCTOS:
        fig_inv.add_trace(
            go.Scatter(
                x=desag[p]["Mes_ES"],
                y=desag[p]["Inv_Fin"],
                name=PROD_LABELS[p],
                mode="lines+markers",
                line=dict(color=PROD_COLORS_DARK[p], width=2),
                marker=dict(
                    size=6,
                    color=PROD_COLORS[p],
                    line=dict(color=PROD_COLORS_DARK[p], width=1.2),
                ),
                fill="tozeroy",
                fillcolor=f"rgba(int('{PROD_COLORS[p][1:3]}',16), int('{PROD_COLORS[p][3:5]}',16), int('{PROD_COLORS[p][5:7]}',16), 0.15)",
            )
        )
    fig_inv.update_layout(
        **PLOT_CFG,
        height=280,
        xaxis_title="Mes",
        yaxis_title="Unidades en inventario",
        legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor="rgba(0,0,0,0.05)"),
    )
    st.plotly_chart(fig_inv, use_container_width=True)

###############################################################################
# PESTAÑA 4 — SIMULACIÓN
###############################################################################
with tabs[3]:
    st.markdown(
        f'<div class="sec-title">🏭 Simulación de Planta — {MESES_F[mes_idx]}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="info-box">Simulación de eventos discretos con SimPy. Las rutas incluyen Mezclado → Dosificado/Moldeado → Horneado → Enfriamiento → Empaque. Los tiempos son estocásticos y se ajustan según el tamaño de lote y turnos.</div>',
        unsafe_allow_html=True,
    )
    # Mostrar plan del mes en tarjetas
    st.markdown(
        '<div class="sec-title">🗓️ Plan del mes (unidades a producir)</div>',
        unsafe_allow_html=True,
    )
    cols_p = st.columns(len(PRODUCTOS))
    EMOJIS = {
        "Brownies": "🍫",
        "Mantecadas": "🧁",
        "Mantecadas_Amapola": "🌸",
        "Torta_Naranja": "🍊",
        "Pan_Maiz": "🌽",
    }
    for i, (p, u) in enumerate(plan_mes.items()):
        with cols_p[i]:
            hh_req = round(u * HORAS_PRODUCTO[p], 1)
            st.markdown(
                f"""
                <div class="kpi-card" style="background:{PROD_COLORS[p]}33;border-color:{PROD_COLORS_DARK[p]}40">
                  <div class="icon">{EMOJIS[p]}</div>
                  <div class="val" style="font-size:1.5rem">{u:,}</div>
                  <div class="lbl">{PROD_LABELS[p]}</div>
                  <div class="sub">{hh_req} H-H</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.markdown("<br>", unsafe_allow_html=True)
    # Cumplimiento del plan por producto
    if not df_kpis.empty:
        st.markdown(
            '<div class="sec-title">✅ Cumplimiento del plan por producto</div>',
            unsafe_allow_html=True,
        )
        fig_cum = go.Figure()
        for i, row in df_kpis.iterrows():
            p_key = [p for p in PRODUCTOS if PROD_LABELS[p] == row["Producto"]]
            p_key = p_key[0] if p_key else PRODUCTOS[i % len(PRODUCTOS)]
            fig_cum.add_trace(
                go.Bar(
                    x=[row["Cumplimiento %"]],
                    y=[row["Producto"]],
                    orientation="h",
                    marker=dict(
                        color=PROD_COLORS[p_key],
                        line=dict(color=PROD_COLORS_DARK[p_key], width=1.5),
                    ),
                    text=f"{row['Cumplimiento %']:.1f}%",
                    textposition="inside",
                    textfont=dict(color="#333", size=12),
                    showlegend=False,
                    hovertemplate=f"<b>{row['Producto']}</b><br>Prod: {row['Und Producidas']:,.0f}<br>Plan: {row['Plan']:,.0f}<extra></extra>",
                )
            )
        fig_cum.add_vline(
            x=100,
            line_dash="dash",
            line_color=PALETTE["caramel"],
            annotation_text="Meta 100%",
            annotation_font_color=PALETTE["caramel"],
        )
        fig_cum.update_layout(
            **PLOT_CFG,
            height=250,
            xaxis=dict(range=[0, 115]),
            yaxis=dict(showgrid=False),
            xaxis_title="Cumplimiento (%)",
            margin=dict(t=20, b=20),
            title="Cumplimiento del Plan por Producto",
        )
        st.plotly_chart(fig_cum, use_container_width=True)
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.markdown(
                '<div class="sec-title">⚡ Throughput (und/h)</div>',
                unsafe_allow_html=True,
            )
            prods_kpi = [
                PROD_LABELS[p] for p in PRODUCTOS if PROD_LABELS[p] in df_kpis["Producto"].values
            ]
            colores_kpi = [
                PROD_COLORS[p] for p in PRODUCTOS if PROD_LABELS[p] in df_kpis["Producto"].values
            ]
            fig_tp = go.Figure(
                go.Bar(
                    x=prods_kpi,
                    y=df_kpis["Throughput (und/h)"].values,
                    marker_color=colores_kpi,
                    marker_line_color="white",
                    marker_line_width=2,
                    text=[f"{v:.1f}" for v in df_kpis["Throughput (und/h)"].values],
                    textposition="outside",
                )
            )
            fig_tp.update_layout(
                **PLOT_CFG,
                height=260,
                yaxis_title="und/h",
                showlegend=False,
                xaxis=dict(showgrid=False),
                yaxis=dict(gridcolor="rgba(0,0,0,0.05)"),
                margin=dict(t=40),
            )
            st.plotly_chart(fig_tp, use_container_width=True)
        with col_t2:
            st.markdown(
                '<div class="sec-title">⏱️ Lead Time (min/lote)</div>',
                unsafe_allow_html=True,
            )
            fig_lt = go.Figure(
                go.Bar(
                    x=prods_kpi,
                    y=df_kpis["Lead Time (min/lote)"].values,
                    marker_color=[
                        PROD_COLORS_DARK[p]
                        for p in PRODUCTOS
                        if PROD_LABELS[p] in df_kpis["Producto"].values
                    ],
                    marker_line_color="white",
                    marker_line_width=2,
                    text=[f"{v:.0f}" for v in df_kpis["Lead Time (min/lote)"].values],
                    textposition="outside",
                )
            )
            fig_lt.update_layout(
                **PLOT_CFG,
                height=260,
                yaxis_title="min/lote",
                showlegend=False,
                xaxis=dict(showgrid=False),
                yaxis=dict(gridcolor="rgba(0,0,0,0.05)"),
                margin=dict(t=40),
            )
            st.plotly_chart(fig_lt, use_container_width=True)
    # Utilización de recursos y cuellos de botella
    if not df_util.empty:
        st.markdown(
            '<div class="sec-title">⚙️ Utilización de recursos y cuellos de botella</div>',
            unsafe_allow_html=True,
        )
        cuellos = df_util[df_util["Cuello Botella"]]
        if not cuellos.empty:
            for _, row in cuellos.iterrows():
                st.markdown(
                    f'<div class="pill-warn">⚠️ Cuello: <b>{row["Recurso"]}</b> — {row["Utilizacion_%"]:.1f}% · Cola prom: {row["Cola Prom"]:.2f}</div><br>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                '<div class="pill-ok">✅ Sin cuellos de botella detectados</div><br>',
                unsafe_allow_html=True,
            )
        # Representación de utilización y colas
        REC_LABELS = {
            "mezcla": "🥣 Mezcla",
            "dosificado": "🔧 Dosificado",
            "horno": "🔥 Horno",
            "enfriamiento": "❄️ Enfriamiento",
            "empaque": "📦 Empaque",
            "amasado": "👐 Amasado",
        }
        rec_lb = [REC_LABELS.get(r, r) for r in df_util["Recurso"]]
        col_util = [
            PALETTE["rose"] if u >= 80 else PALETTE["butter"] if u >= 60 else PALETTE["mint"]
            for u in df_util["Utilizacion_%"]
        ]
        fig_util_g = make_subplots(
            rows=1,
            cols=2,
            subplot_titles=["Utilización (%)", "Cola Promedio"],
        )
        fig_util_g.add_trace(
            go.Bar(
                x=rec_lb,
                y=df_util["Utilizacion_%"],
                marker_color=col_util,
                marker_line_color="white",
                marker_line_width=2,
                text=[f"{v:.0f}%" for v in df_util["Utilizacion_%"]],
                textposition="outside",
                showlegend=False,
            ),
            row=1,
            col=1,
        )
        fig_util_g.add_hline(
            y=80,
            line_dash="dash",
            line_color=PALETTE["rose"],
            annotation_text="80%",
            annotation_position="top left",
            row=1,
            col=1,
        )
        fig_util_g.add_trace(
            go.Bar(
                x=rec_lb,
                y=df_util["Cola Prom"],
                marker_color=PALETTE["lavender"],
                marker_line_color="white",
                marker_line_width=2,
                text=[f"{v:.2f}" for v in df_util["Cola Prom"]],
                textposition="outside",
                showlegend=False,
            ),
            row=1,
            col=2,
        )
        fig_util_g.update_layout(
            **PLOT_CFG,
            height=310,
        )
        fig_util_g.update_xaxes(showgrid=False)
        fig_util_g.update_yaxes(gridcolor="rgba(0,0,0,0.05)")
        st.plotly_chart(fig_util_g, use_container_width=True)
    # Diagrama de Gantt y distribución de tiempos
    if not df_lotes.empty:
        st.markdown(
            '<div class="sec-title">📅 Diagrama de Gantt — Flujo de lotes de producción</div>',
            unsafe_allow_html=True,
        )
        n_gantt = min(60, len(df_lotes))
        sub_l = df_lotes.head(n_gantt).reset_index(drop=True)
        fig_gantt = go.Figure()
        for _, row in sub_l.iterrows():
            fig_gantt.add_trace(
                go.Bar(
                    x=[row["tiempo_sistema"]],
                    y=[row["lote_id"]],
                    base=[row["t_creacion"]],
                    orientation="h",
                    marker_color=PROD_COLORS.get(row["producto"], "#cccccc"),
                    opacity=0.85,
                    showlegend=False,
                    marker_line_color="white",
                    marker_line_width=0.5,
                    hovertemplate=(
                        f"<b>{PROD_LABELS.get(row['producto'], row['producto'])}</b><br>Inicio: {row['t_creacion']:.0f} min<br>Duración: {row['tiempo_sistema']:.1f} min<extra></extra>"
                    ),
                )
            )
        # Leyenda manual de productos
        for p, c in PROD_COLORS.items():
            fig_gantt.add_trace(
                go.Bar(x=[None], y=[None], marker_color=c, name=PROD_LABELS[p])
            )
        fig_gantt.update_layout(
            **PLOT_CFG,
            barmode="overlay",
            height=max(380, n_gantt * 8),
            title=f"Gantt — Primeros {n_gantt} lotes",
            xaxis_title="Tiempo simulado (min)",
            legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"),
            yaxis=dict(showticklabels=False),
        )
        st.plotly_chart(fig_gantt, use_container_width=True)
        st.markdown(
            '<div class="sec-title">🎻 Distribución de tiempos en sistema por producto</div>',
            unsafe_allow_html=True,
        )
        fig_violin = go.Figure()
        for p in PRODUCTOS:
            sub_v = df_lotes[df_lotes["producto"] == p]["tiempo_sistema"]
            if len(sub_v) < 3:
                continue
            fig_violin.add_trace(
                go.Violin(
                    y=sub_v,
                    name=PROD_LABELS[p],
                    box_visible=True,
                    meanline_visible=True,
                    fillcolor=PROD_COLORS[p],
                    line_color=PROD_COLORS_DARK[p],
                    opacity=0.75,
                )
            )
        fig_violin.update_layout(
            **PLOT_CFG,
            height=310,
            yaxis_title="Tiempo en sistema (min)",
            showlegend=False,
            violinmode="overlay",
        )
        st.plotly_chart(fig_violin, use_container_width=True)
        with st.expander("📊 Ver tabla completa de KPIs"):
            if not df_kpis.empty:
                st.dataframe(
                    df_kpis.style.format(
                        {
                            "Und Producidas": "{:,.0f}",
                            "Plan": "{:,.0f}",
                            "Throughput (und/h)": "{:,.2f}",
                            "Cycle Time (min/und)": "{:,.2f}",
                            "Lead Time (min/lote)": "{:,.2f}",
                            "WIP Prom": "{:,.2f}",
                            "Takt (min/lote)": "{:,.2f}",
                            "Cumplimiento %": "{:,.1f}%",
                        }
                    ).background_gradient(subset=["Cumplimiento %"], cmap="YlGn"),
                    use_container_width=True,
                )

###############################################################################
# PESTAÑA 5 — SENSORES
###############################################################################
with tabs[4]:
    st.markdown(
        '<div class="sec-title">🌡️ Sensores virtuales — Monitor del horno</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="info-box">Se simulan sensores IoT del horno: temperatura, ocupación y alertas de exceso térmico. El límite operativo es 200 °C.</div>',
        unsafe_allow_html=True,
    )
    if not df_sensores.empty:
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("🌡️ Temp. mínima", f"{df_sensores['temperatura'].min():.1f} °C")
        s2.metric("🔥 Temp. máxima", f"{df_sensores['temperatura'].max():.1f} °C")
        s3.metric("📊 Temp. promedio", f"{df_sensores['temperatura'].mean():.1f} °C")
        s4.metric(
            "⚠️ Excesos >200°C",
            excesos,
            delta="Revisar horno" if excesos else "Operación normal",
            delta_color="inverse" if excesos else "off",
        )
        # Curva de temperatura a lo largo del tiempo
        fig_temp = go.Figure()
        fig_temp.add_trace(
            go.Scatter(
                x=df_sensores["tiempo"],
                y=df_sensores["temperatura"],
                mode="lines",
                line=dict(color=PALETTE["rose"], width=1.8),
                name="Temperatura",
            )
        )
        # Línea de ocupación del horno
        fig_temp.add_trace(
            go.Scatter(
                x=df_sensores["tiempo"],
                y=df_sensores["horno_ocup"],
                mode="lines",
                yaxis="y2",
                line=dict(color=PALETTE["mint"], width=1.5, dash="dash"),
                name="Ocupación horno",
            )
        )
        fig_temp.add_hline(
            y=200,
            line_dash="dash",
            line_color=PALETTE["caramel"],
            annotation_text="Límite 200°C",
            annotation_position="top right",
        )
        fig_temp.update_layout(
            **PLOT_CFG,
            height=350,
            xaxis_title="Tiempo (min)",
            yaxis=dict(title="Temperatura (°C)", showgrid=True, gridcolor="rgba(0,0,0,0.05)"),
            yaxis2=dict(
                title="Estaciones ocupadas",
                overlaying="y",
                side="right",
                showgrid=False,
            ),
            legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"),
        )
        st.plotly_chart(fig_temp, use_container_width=True)
        # Histograma de temperaturas
        st.markdown(
            '<div class="sec-title">📊 Distribución de temperaturas</div>',
            unsafe_allow_html=True,
        )
        fig_hist = go.Figure(
            go.Histogram(
                x=df_sensores["temperatura"],
                nbinsx=30,
                marker_color=PALETTE["sky"],
                marker_line_color="white",
                marker_line_width=1,
            )
        )
        fig_hist.update_layout(
            **PLOT_CFG,
            height=260,
            xaxis_title="Temperatura (°C)",
            yaxis_title="Frecuencia",
            showlegend=False,
        )
        st.plotly_chart(fig_hist, use_container_width=True)
    else:
        st.info("No se registraron datos de sensores en esta simulación.")

###############################################################################
# PESTAÑA 6 — ESCENARIOS
###############################################################################
with tabs[5]:
    st.markdown(
        '<div class="sec-title">🔬 Escenarios What‑If</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="info-box">Experimenta con parámetros clave para analizar escenarios alternativos (por ejemplo, aumentar la capacidad del horno o modificar la participación de mercado). Actualiza los controles en la barra lateral y observa cómo cambian los KPIs.</div>',
        unsafe_allow_html=True,
    )
    st.success(
        "Utiliza la barra lateral para modificar los parámetros y observa en tiempo real cómo se alteran las gráficas y métricas."
    )
