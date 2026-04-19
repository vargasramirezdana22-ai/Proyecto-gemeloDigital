import math
import random
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import simpy
import streamlit as st
from pulp import LpMinimize, LpProblem, LpVariable, PULP_CBC_CMD, lpSum, value

# ============================================================
# IDENTIDAD VISUAL - VERSIÓN REPLANTEADA
# ============================================================
PALETTE = {
    "bg": "#0F172A",
    "panel": "#111827",
    "panel_2": "#1F2937",
    "card": "#FFFFFF",
    "txt": "#E5E7EB",
    "muted": "#94A3B8",
    "accent": "#22C55E",
    "accent_2": "#38BDF8",
    "warn": "#F59E0B",
    "danger": "#F43F5E",
    "violet": "#8B5CF6",
}

PRODUCTS = ["Brownies", "Mantecadas", "Mantecadas_Amapola", "Torta_Naranja", "Pan_Maiz"]
MONTHS_EN = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]
MONTHS_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
MONTHS_FULL = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

PRODUCT_NAMES = {
    "Brownies": "Brownies",
    "Mantecadas": "Mantecadas",
    "Mantecadas_Amapola": "Mantecadas con Amapola",
    "Torta_Naranja": "Torta de Naranja",
    "Pan_Maiz": "Pan de Maíz",
}

PRODUCT_COLORS = {
    "Brownies": "#22C55E",
    "Mantecadas": "#38BDF8",
    "Mantecadas_Amapola": "#8B5CF6",
    "Torta_Naranja": "#F97316",
    "Pan_Maiz": "#EAB308",
}

PRODUCT_EMOJI = {
    "Brownies": "🍫",
    "Mantecadas": "🧁",
    "Mantecadas_Amapola": "🌸",
    "Torta_Naranja": "🍊",
    "Pan_Maiz": "🌽",
}

HIST_DEMAND = {
    "Brownies": [315, 804, 734, 541, 494, 59, 315, 803, 734, 541, 494, 59],
    "Mantecadas": [125, 780, 432, 910, 275, 68, 512, 834, 690, 455, 389, 120],
    "Mantecadas_Amapola": [320, 710, 520, 251, 631, 150, 330, 220, 710, 610, 489, 180],
    "Torta_Naranja": [100, 250, 200, 101, 190, 50, 100, 220, 200, 170, 180, 187],
    "Pan_Maiz": [330, 140, 143, 73, 83, 48, 70, 89, 118, 83, 67, 87],
}

HOURS_PER_UNIT = {
    "Brownies": 0.866,
    "Mantecadas": 0.175,
    "Mantecadas_Amapola": 0.175,
    "Torta_Naranja": 0.175,
    "Pan_Maiz": 0.312,
}

PROCESS_ROUTES = {
    "Brownies": [("mezcla", 12, 18), ("dosificado", 8, 14), ("horno", 30, 40), ("enfriamiento", 25, 35), ("empaque", 8, 12)],
    "Mantecadas": [("mezcla", 12, 18), ("dosificado", 16, 24), ("horno", 20, 30), ("enfriamiento", 35, 55), ("empaque", 4, 6)],
    "Mantecadas_Amapola": [("mezcla", 12, 18), ("mezcla", 8, 12), ("dosificado", 16, 24), ("horno", 20, 30), ("enfriamiento", 36, 54), ("empaque", 4, 6)],
    "Torta_Naranja": [("mezcla", 16, 24), ("dosificado", 8, 12), ("horno", 32, 48), ("enfriamiento", 48, 72), ("dosificado", 8, 12), ("empaque", 8, 12)],
    "Pan_Maiz": [("mezcla", 12, 18), ("amasado", 16, 24), ("dosificado", 12, 18), ("horno", 28, 42), ("enfriamiento", 36, 54), ("empaque", 4, 6)],
}

BATCH_SIZE = {
    "Brownies": 12,
    "Mantecadas": 10,
    "Mantecadas_Amapola": 10,
    "Torta_Naranja": 12,
    "Pan_Maiz": 15,
}

BASE_SETTINGS = {
    "Ct": 4310,
    "Ht": 100000,
    "PIt": 100000,
    "CRt": 11364,
    "COt": 14205,
    "CW_plus": 14204,
    "CW_minus": 15061,
    "M": 1,
    "LR_initial": 44 * 4 * 10,
}

INITIAL_STOCK = {p: 0 for p in PRODUCTS}


def rgba(hex_color: str, alpha: float = 0.18) -> str:
    color = hex_color.lstrip("#")
    r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def human_hour_demand(multiplier: float = 1.0) -> dict:
    return {
        month: round(sum(HIST_DEMAND[p][i] * HOURS_PER_UNIT[p] for p in PRODUCTS) * multiplier, 2)
        for i, month in enumerate(MONTHS_EN)
    }


def smooth_forecast(series, steps=4, alpha=0.35):
    level = series[0]
    smoothed = []
    for value_ in series:
        level = alpha * value_ + (1 - alpha) * level
        smoothed.append(level)
    trend = (smoothed[-1] - smoothed[-4]) / 3 if len(smoothed) >= 4 else 0
    projection = []
    current = smoothed[-1]
    for _ in range(steps):
        current += trend * alpha
        projection.append(round(current, 1))
    return smoothed, projection


@st.cache_data(show_spinner=False)
def aggregate_plan(demand_factor=1.0, settings_tuple=None):
    cfg = BASE_SETTINGS.copy()
    if settings_tuple:
        cfg.update(dict(settings_tuple))

    demand_hh = human_hour_demand(demand_factor)
    model = LpProblem("planificacion_agregada", LpMinimize)

    prod = LpVariable.dicts("Prod", MONTHS_EN, lowBound=0)
    inv = LpVariable.dicts("Inv", MONTHS_EN, lowBound=0)
    backlog = LpVariable.dicts("Bkl", MONTHS_EN, lowBound=0)
    regular = LpVariable.dicts("Reg", MONTHS_EN, lowBound=0)
    overtime = LpVariable.dicts("Over", MONTHS_EN, lowBound=0)
    undertime = LpVariable.dicts("Under", MONTHS_EN, lowBound=0)
    net = LpVariable.dicts("Net", MONTHS_EN)
    hire = LpVariable.dicts("Hire", MONTHS_EN, lowBound=0)
    fire = LpVariable.dicts("Fire", MONTHS_EN, lowBound=0)

    model += lpSum(
        cfg["Ct"] * prod[m] + cfg["Ht"] * inv[m] + cfg["PIt"] * backlog[m] +
        cfg["CRt"] * regular[m] + cfg["COt"] * overtime[m] +
        cfg["CW_plus"] * hire[m] + cfg["CW_minus"] * fire[m]
        for m in MONTHS_EN
    )

    for i, month in enumerate(MONTHS_EN):
        prev = MONTHS_EN[i - 1] if i > 0 else None
        d = demand_hh[month]
        if i == 0:
            model += net[month] == prod[month] - d
            model += regular[month] == cfg["LR_initial"] + hire[month] - fire[month]
        else:
            model += net[month] == net[prev] + prod[month] - d
            model += regular[month] == regular[prev] + hire[month] - fire[month]
        model += net[month] == inv[month] - backlog[month]
        model += undertime[month] + overtime[month] == cfg["M"] * prod[month]
        model += undertime[month] <= regular[month]

    model.solve(PULP_CBC_CMD(msg=False))

    opening, closing = [], []
    for i, m in enumerate(MONTHS_EN):
        ini = 0 if i == 0 else closing[-1]
        fin = ini + (prod[m].varValue or 0) - demand_hh[m]
        opening.append(round(ini, 2))
        closing.append(round(fin, 2))

    out = pd.DataFrame({
        "Mes": MONTHS_EN,
        "Mes_ES": MONTHS_ES,
        "Mes_Full": MONTHS_FULL,
        "Demanda_HH": [round(demand_hh[m], 2) for m in MONTHS_EN],
        "Produccion_HH": [round(prod[m].varValue or 0, 2) for m in MONTHS_EN],
        "Inventario_HH": [round(inv[m].varValue or 0, 2) for m in MONTHS_EN],
        "Backlog_HH": [round(backlog[m].varValue or 0, 2) for m in MONTHS_EN],
        "Horas_Regulares": [round(regular[m].varValue or 0, 2) for m in MONTHS_EN],
        "Horas_Extra": [round(overtime[m].varValue or 0, 2) for m in MONTHS_EN],
        "Apertura_HH": opening,
        "Cierre_HH": closing,
        "Contrata": [round(hire[m].varValue or 0, 2) for m in MONTHS_EN],
        "Despide": [round(fire[m].varValue or 0, 2) for m in MONTHS_EN],
    })
    return out, value(model.objective)


@st.cache_data(show_spinner=False)
def product_breakdown(monthly_hh_items, factor=1.0, cost_prod=1.0, cost_inv=1.0):
    capacity = dict(monthly_hh_items)
    model = LpProblem("desglose_productos", LpMinimize)

    x = {(p, m): LpVariable(f"X_{p}_{m}", lowBound=0) for p in PRODUCTS for m in MONTHS_EN}
    inv = {(p, m): LpVariable(f"I_{p}_{m}", lowBound=0) for p in PRODUCTS for m in MONTHS_EN}
    bkl = {(p, m): LpVariable(f"S_{p}_{m}", lowBound=0) for p in PRODUCTS for m in MONTHS_EN}

    model += lpSum(cost_inv * 100000 * inv[p, m] + cost_prod * 150000 * bkl[p, m] for p in PRODUCTS for m in MONTHS_EN)

    for i, month in enumerate(MONTHS_EN):
        prev = MONTHS_EN[i - 1] if i > 0 else None
        model += lpSum(HOURS_PER_UNIT[p] * x[p, month] for p in PRODUCTS) <= capacity[month]
        for p in PRODUCTS:
            demand = int(HIST_DEMAND[p][i] * factor)
            if i == 0:
                model += inv[p, month] - bkl[p, month] == INITIAL_STOCK[p] + x[p, month] - demand
            else:
                model += inv[p, month] - bkl[p, month] == inv[p, prev] - bkl[p, prev] + x[p, month] - demand

    model.solve(PULP_CBC_CMD(msg=False))

    result = {}
    for p in PRODUCTS:
        rows = []
        for i, month in enumerate(MONTHS_EN):
            prev_stock = INITIAL_STOCK[p] if i == 0 else round(inv[p, MONTHS_EN[i - 1]].varValue or 0, 2)
            rows.append({
                "Mes": month,
                "Mes_ES": MONTHS_ES[i],
                "Demanda": int(HIST_DEMAND[p][i] * factor),
                "Produccion": round(x[p, month].varValue or 0, 2),
                "Inventario_Inicial": prev_stock,
                "Inventario_Final": round(inv[p, month].varValue or 0, 2),
                "Backlog": round(bkl[p, month].varValue or 0, 2),
            })
        result[p] = pd.DataFrame(rows)
    return result


@st.cache_data(show_spinner=False)
def run_factory_simulation(plan_items, resource_items, oven_failure, speed_factor, seed=42,
                           mix_range=(12, 18), bake_range=(30, 40), cool_range=(25, 55), pack_range=(4, 12)):
    monthly_plan = dict(plan_items)
    resources_map = dict(resource_items)
    random.seed(seed)
    np.random.seed(seed)

    batches, logs, sensor_log = [], [], []
    overrides = {
        "mezcla": mix_range,
        "horno": bake_range,
        "enfriamiento": cool_range,
        "empaque": pack_range,
    }

    def monitor(env, resources):
        while True:
            occupied = resources["horno"].count
            temp = round(np.random.normal(162 + occupied * 11, 5), 2)
            sensor_log.append({
                "tiempo": round(env.now, 2),
                "temperatura": temp,
                "ocupacion_horno": occupied,
                "cola_horno": len(resources["horno"].queue),
            })
            yield env.timeout(10)

    def register_state(env, resources, product=""):
        for name, res in resources.items():
            logs.append({
                "tiempo": round(env.now, 3),
                "recurso": name,
                "ocupados": res.count,
                "cola": len(res.queue),
                "capacidad": res.capacity,
                "producto": product,
            })

    def process_batch(env, batch_id, product, units, resources):
        start = env.now
        total_wait = 0
        for resource_name, low_t, high_t in PROCESS_ROUTES[product]:
            low_, high_ = overrides.get(resource_name, (low_t, high_t))
            duration = random.uniform(low_, high_) * math.sqrt(units / BATCH_SIZE[product]) * speed_factor
            if oven_failure and resource_name == "horno":
                duration += random.uniform(10, 30)

            register_state(env, resources, product)
            queue_in = env.now
            with resources[resource_name].request() as req:
                yield req
                total_wait += env.now - queue_in
                register_state(env, resources, product)
                yield env.timeout(duration)
            register_state(env, resources, product)

        batches.append({
            "lote": batch_id,
            "producto": product,
            "unidades": units,
            "inicio": round(start, 2),
            "fin": round(env.now, 2),
            "tiempo_total": round(env.now - start, 2),
            "espera_total": round(total_wait, 2),
        })

    env = simpy.Environment()
    sim_resources = {k: simpy.Resource(env, capacity=v) for k, v in resources_map.items()}
    env.process(monitor(env, sim_resources))

    month_duration = 44 * 4 * 60
    arrivals = []
    seq = 0
    for product, total_units in monthly_plan.items():
        if total_units <= 0:
            continue
        batch = BATCH_SIZE[product]
        count_batches = math.ceil(total_units / batch)
        gap = month_duration / max(count_batches, 1)
        next_t = random.expovariate(1 / max(gap, 1))
        pending = total_units
        for _ in range(count_batches):
            arrivals.append((round(next_t, 2), product, min(batch, int(pending))))
            pending -= batch
            next_t += random.expovariate(1 / max(gap, 1))

    arrivals.sort(key=lambda x: x[0])

    def launcher():
        nonlocal seq
        for at, product, units in arrivals:
            yield env.timeout(max(at - env.now, 0))
            batch_id = f"{product[:3].upper()}-{seq:03d}"
            seq += 1
            env.process(process_batch(env, batch_id, product, units, sim_resources))

    env.process(launcher())
    env.run(until=month_duration * 1.8)

    return pd.DataFrame(batches), pd.DataFrame(logs), pd.DataFrame(sensor_log)


def summarize_utilization(log_df: pd.DataFrame) -> pd.DataFrame:
    if log_df.empty:
        return pd.DataFrame()
    rows = []
    for resource, grp in log_df.groupby("recurso"):
        grp = grp.sort_values("tiempo").reset_index(drop=True)
        cap = grp["capacidad"].iloc[0]
        t = grp["tiempo"].values
        used = grp["ocupados"].values
        if len(t) > 1 and (t[-1] - t[0]) > 0:
            fn = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
            util = round(fn(used, t) / (cap * (t[-1] - t[0])) * 100, 2)
        else:
            util = 0.0
        rows.append({
            "Recurso": resource,
            "Utilizacion": util,
            "Cola_Promedio": round(grp["cola"].mean(), 3),
            "Cola_Max": int(grp["cola"].max()),
            "Capacidad": int(cap),
            "Critico": util >= 80 or grp["cola"].mean() > 0.5,
        })
    return pd.DataFrame(rows).sort_values("Utilizacion", ascending=False).reset_index(drop=True)


def summarize_kpis(batch_df: pd.DataFrame, plan: dict) -> pd.DataFrame:
    if batch_df.empty:
        return pd.DataFrame()
    rows = []
    horizon_hours = max((batch_df["fin"].max() - batch_df["inicio"].min()) / 60, 0.01)
    for p in PRODUCTS:
        subset = batch_df[batch_df["producto"] == p]
        if subset.empty:
            continue
        produced = subset["unidades"].sum()
        target = plan.get(p, 0)
        throughput = round(produced / horizon_hours, 2)
        lead_time = round(subset["tiempo_total"].mean(), 2)
        cycle = round((subset["tiempo_total"] / subset["unidades"]).mean(), 3)
        wip = round(throughput * (lead_time / 60), 2)
        rows.append({
            "Producto": PRODUCT_NAMES[p],
            "Plan": target,
            "Producido": produced,
            "Cumplimiento": round(min(produced / max(target, 1) * 100, 100), 2),
            "Throughput": throughput,
            "Lead_Time": lead_time,
            "Cycle_Time": cycle,
            "WIP": wip,
        })
    return pd.DataFrame(rows)


st.set_page_config(page_title="Centro Analítico Panadería", page_icon="📊", layout="wide")

st.markdown(
    f"""
    <style>
    .stApp {{background: linear-gradient(180deg, {PALETTE['bg']} 0%, #111827 100%);}}
    .main-title {{font-size: 2.4rem; font-weight: 800; color: white; margin-bottom: 0.2rem;}}
    .subtitle {{color: {PALETTE['muted']}; font-size: 1rem; margin-bottom: 1rem;}}
    .panel {{background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); padding: 1rem; border-radius: 18px;}}
    .metricbox {{background: white; border-radius: 18px; padding: 1rem; text-align: left; min-height: 118px;}}
    .metricvalue {{font-size: 1.8rem; font-weight: 800; color: #111827;}}
    .metriclabel {{font-size: 0.82rem; color: #64748B; text-transform: uppercase; letter-spacing: 1px;}}
    .badge {{display: inline-block; padding: 0.35rem 0.8rem; border-radius: 999px; margin-right: 0.4rem; background: rgba(255,255,255,0.08); color: white; font-size: 0.8rem;}}
    [data-testid='stSidebar'] {{background: #0B1220;}}
    [data-testid='stSidebar'] * {{color: #E5E7EB !important;}}
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("⚙️ Controles")
    selected_month = st.selectbox("Mes de simulación", range(12), format_func=lambda i: MONTHS_FULL[i], index=1)
    demand_factor = st.slider("Multiplicador de demanda", 0.5, 2.0, 1.0, 0.05)
    forecast_steps = st.slider("Horizonte de proyección", 1, 6, 4)

    st.subheader("Capacidad del sistema")
    oven_capacity = st.slider("Hornos activos", 1, 6, 3)
    has_breakdown = st.checkbox("Introducir falla de horno")
    fast_mode = st.checkbox("Modo acelerado de producción")
    seed_value = st.number_input("Semilla", value=42, step=1)

    st.subheader("Plantilla")
    workers = st.number_input("Trabajadores por turno", value=10, min_value=1, step=1)
    shifts_per_day = st.number_input("Turnos por día", value=3, min_value=1, max_value=3, step=1)
    hours_shift = st.number_input("Horas por turno", value=8, min_value=4, max_value=12, step=1)
    days_month = st.number_input("Días operativos", value=30, min_value=20, max_value=31, step=1)
    efficiency = st.slider("Eficiencia (%)", 50, 110, 95)
    absenteeism = st.slider("Ausentismo (%)", 0, 30, 5)

    st.subheader("Costos")
    ct = st.number_input("Ct", value=4310, step=100)
    ht = st.number_input("Ht", value=100000, step=1000)
    pit = st.number_input("PIt", value=100000, step=1000)
    crt = st.number_input("CRt", value=11364, step=100)
    cot = st.number_input("COt", value=14205, step=100)
    cplus = st.number_input("CW+", value=14204, step=100)
    cminus = st.number_input("CW-", value=15061, step=100)

    st.subheader("Recursos")
    mix_cap = st.number_input("Mezcla", value=2, min_value=1, step=1)
    dosing_cap = st.number_input("Dosificado", value=2, min_value=1, step=1)
    cool_cap = st.number_input("Enfriamiento", value=4, min_value=1, step=1)
    pack_cap = st.number_input("Empaque", value=2, min_value=1, step=1)
    knead_cap = st.number_input("Amasado", value=1, min_value=1, step=1)

    st.subheader("Tiempos")
    mix_max = st.slider("Mezcla max", 8, 30, 18)
    bake_max = st.slider("Horneado max", 20, 60, 40)
    cool_max = st.slider("Enfriamiento max", 15, 80, 55)
    pack_max = st.slider("Empaque max", 2, 20, 12)

available_hh = round(workers * shifts_per_day * hours_shift * days_month * (efficiency / 100) * ((100 - absenteeism) / 100))

settings = {
    **BASE_SETTINGS,
    "Ct": ct,
    "Ht": ht,
    "PIt": pit,
    "CRt": crt,
    "COt": cot,
    "CW_plus": cplus,
    "CW_minus": cminus,
    "LR_initial": workers * shifts_per_day * hours_shift * days_month,
}

agg_df, total_cost = aggregate_plan(demand_factor, tuple(sorted(settings.items())))
plan_hh = dict(zip(agg_df["Mes"], agg_df["Produccion_HH"]))
product_plan = product_breakdown(tuple(plan_hh.items()), demand_factor, 1.0, 1.0)
month_key = MONTHS_EN[selected_month]
month_plan = {p: int(product_plan[p].loc[product_plan[p]["Mes"] == month_key, "Produccion"].values[0]) for p in PRODUCTS}

resource_cfg = {
    "mezcla": mix_cap,
    "dosificado": dosing_cap,
    "horno": int(oven_capacity),
    "enfriamiento": cool_cap,
    "empaque": pack_cap,
    "amasado": knead_cap,
}

speed = 0.82 if fast_mode else 1.0
mix_range = (max(8, mix_max - 6), mix_max)
bake_range = (max(20, bake_max - 10), bake_max)
cool_range = (max(15, cool_max - 15), cool_max)
pack_range = (max(2, pack_max - 4), pack_max)

batches_df, log_df, sensor_df = run_factory_simulation(
    tuple(month_plan.items()), tuple(resource_cfg.items()), has_breakdown, speed, int(seed_value),
    mix_range, bake_range, cool_range, pack_range,
)

kpi_df = summarize_kpis(batches_df, month_plan)
util_df = summarize_utilization(log_df)

avg_fill = kpi_df["Cumplimiento"].mean() if not kpi_df.empty else 0
max_util = util_df["Utilizacion"].max() if not util_df.empty else 0
avg_temp = sensor_df["temperatura"].mean() if not sensor_df.empty else 0
critical_temp = int((sensor_df["temperatura"] > 200).sum()) if not sensor_df.empty else 0

st.markdown('<div class="main-title">Centro Analítico de Producción</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Versión rediseñada con estructura ejecutiva, panel oscuro y navegación por bloques.</div>', unsafe_allow_html=True)
st.markdown(
    f"<span class='badge'>Mes: {MONTHS_FULL[selected_month]}</span>"
    f"<span class='badge'>Demanda x{demand_factor}</span>"
    f"<span class='badge'>Capacidad efectiva: {available_hh:,} H-H</span>"
    f"<span class='badge'>Hornos: {oven_capacity}</span>",
    unsafe_allow_html=True,
)

m1, m2, m3, m4 = st.columns(4)
for col, label, value_, extra in [
    (m1, "Costo anual", f"${total_cost:,.0f}", "Plan agregado"),
    (m2, "Cumplimiento", f"{avg_fill:.1f}%", "Simulación mensual"),
    (m3, "Utilización máxima", f"{max_util:.0f}%", "Recurso crítico"),
    (m4, "Temperatura media", f"{avg_temp:.0f}°C", f"Eventos >200°C: {critical_temp}"),
]:
    col.markdown(f"<div class='metricbox'><div class='metriclabel'>{label}</div><div class='metricvalue'>{value_}</div><div style='color:#64748B'>{extra}</div></div>", unsafe_allow_html=True)

view = st.radio(
    "Navegación",
    ["Resumen ejecutivo", "Planeación agregada", "Portafolio de productos", "Operación simulada", "Sensores y riesgos", "Escenarios"],
    horizontal=True,
)

if view == "Resumen ejecutivo":
    left, right = st.columns([1.25, 1])
    with left:
        demand_long = []
        for p in PRODUCTS:
            _, future = smooth_forecast([x * demand_factor for x in HIST_DEMAND[p]], forecast_steps)
            for i, value_ in enumerate(HIST_DEMAND[p]):
                demand_long.append({"Periodo": MONTHS_ES[i], "Valor": value_ * demand_factor, "Producto": PRODUCT_NAMES[p], "Tipo": "Histórico"})
            for j, value_ in enumerate(future):
                demand_long.append({"Periodo": f"F{j+1}", "Valor": value_, "Producto": PRODUCT_NAMES[p], "Tipo": "Proyección"})
        df_demand_long = pd.DataFrame(demand_long)
        fig = px.line(df_demand_long, x="Periodo", y="Valor", color="Producto", line_dash="Tipo", markers=True,
                      color_discrete_map={PRODUCT_NAMES[k]: PRODUCT_COLORS[k] for k in PRODUCTS})
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,0.02)", height=430)
        st.plotly_chart(fig, use_container_width=True)
    with right:
        hh = human_hour_demand(demand_factor)
        fig2 = go.Figure(go.Bar(x=MONTHS_ES, y=list(hh.values()), marker_color=PALETTE["accent_2"]))
        fig2.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,0.02)", height=430, title="Carga laboral mensual")
        st.plotly_chart(fig2, use_container_width=True)

elif view == "Planeación agregada":
    c1, c2 = st.columns([1.5, 1])
    with c1:
        fig = go.Figure()
        fig.add_bar(x=agg_df["Mes_ES"], y=agg_df["Produccion_HH"], name="Producción H-H", marker_color=PALETTE["accent"])
        fig.add_scatter(x=agg_df["Mes_ES"], y=agg_df["Demanda_HH"], mode="lines+markers", name="Demanda H-H", line=dict(color=PALETTE["accent_2"], width=3))
        fig.add_scatter(x=agg_df["Mes_ES"], y=[available_hh] * 12, mode="lines", name="Capacidad efectiva", line=dict(color=PALETTE["warn"], dash="dash"))
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,0.02)", height=420)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.dataframe(
            agg_df[["Mes_Full", "Produccion_HH", "Demanda_HH", "Horas_Extra", "Backlog_HH"]].rename(columns={"Mes_Full": "Mes"}),
            use_container_width=True,
            height=420,
        )

elif view == "Portafolio de productos":
    tabs = st.tabs([PRODUCT_NAMES[p] for p in PRODUCTS])
    for i, p in enumerate(PRODUCTS):
        with tabs[i]:
            product_df = product_plan[p]
            a, b = st.columns([1.35, 1])
            with a:
                fig = go.Figure()
                fig.add_bar(x=product_df["Mes_ES"], y=product_df["Produccion"], marker_color=PRODUCT_COLORS[p], name="Producción")
                fig.add_scatter(x=product_df["Mes_ES"], y=product_df["Demanda"], mode="lines+markers", line=dict(color="#FFFFFF", dash="dot"), name="Demanda")
                fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,0.02)", title=f"{PRODUCT_NAMES[p]}")
                st.plotly_chart(fig, use_container_width=True)
            with b:
                st.metric("Plan del mes seleccionado", f"{month_plan[p]:,} und")
                st.metric("Demanda anual", f"{product_df['Demanda'].sum():,} und")
                st.metric("Inventario final anual", f"{product_df['Inventario_Final'].iloc[-1]:,.0f} und")
                st.dataframe(product_df, use_container_width=True, height=300)

elif view == "Operación simulada":
    a, b = st.columns([1.1, 1])
    with a:
        if not kpi_df.empty:
            fig = px.bar(kpi_df, x="Producto", y="Cumplimiento", color="Producto",
                         color_discrete_sequence=list(PRODUCT_COLORS.values()), text_auto=".1f")
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,0.02)", height=360)
            st.plotly_chart(fig, use_container_width=True)
        st.dataframe(kpi_df, use_container_width=True, height=250)
    with b:
        if not util_df.empty:
            fig2 = px.bar(util_df, x="Recurso", y="Utilizacion", color="Critico", text_auto=".1f",
                          color_discrete_map={True: PALETTE["danger"], False: PALETTE["accent"]})
            fig2.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,0.02)", height=360)
            st.plotly_chart(fig2, use_container_width=True)
        st.dataframe(util_df, use_container_width=True, height=250)

elif view == "Sensores y riesgos":
    if sensor_df.empty:
        st.info("No hay datos de sensores para mostrar.")
    else:
        x1, x2 = st.columns(2)
        with x1:
            fig = go.Figure()
            fig.add_scatter(x=sensor_df["tiempo"], y=sensor_df["temperatura"], mode="lines", line=dict(color=PALETTE["warn"], width=2.5), fill="tozeroy")
            fig.add_hline(y=200, line_dash="dash", line_color=PALETTE["danger"])
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,0.02)", height=360, title="Temperatura de horno")
            st.plotly_chart(fig, use_container_width=True)
        with x2:
            fig2 = px.histogram(sensor_df, x="temperatura", nbins=30)
            fig2.update_traces(marker_color=PALETTE["accent_2"])
            fig2.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,0.02)", height=360, title="Distribución térmica")
            st.plotly_chart(fig2, use_container_width=True)
        st.dataframe(sensor_df.tail(40), use_container_width=True)

else:
    scenario_defs = {
        "Base": {"factor": 1.0, "fail": False, "speed": 1.0, "oven_delta": 0},
        "Alta demanda": {"factor": 1.2, "fail": False, "speed": 1.0, "oven_delta": 0},
        "Falla térmica": {"factor": 1.0, "fail": True, "speed": 1.0, "oven_delta": 0},
        "Turno ágil": {"factor": 1.0, "fail": False, "speed": 0.82, "oven_delta": 0},
        "Capacidad expandida": {"factor": 1.0, "fail": False, "speed": 1.0, "oven_delta": 1},
    }
    chosen = st.multiselect("Escenarios", list(scenario_defs.keys()), default=["Base", "Alta demanda", "Turno ágil"])
    if st.button("Ejecutar comparación"):
        rows = []
        for name in chosen:
            sc = scenario_defs[name]
            alt_plan = {p: max(int(v * sc["factor"]), 0) for p, v in month_plan.items()}
            alt_resources = {**resource_cfg, "horno": max(resource_cfg["horno"] + sc["oven_delta"], 1)}
            sim_b, sim_l, _ = run_factory_simulation(
                tuple(alt_plan.items()), tuple(alt_resources.items()), sc["fail"], sc["speed"], int(seed_value),
                mix_range, bake_range, cool_range, pack_range,
            )
            sk = summarize_kpis(sim_b, alt_plan)
            su = summarize_utilization(sim_l)
            rows.append({
                "Escenario": name,
                "Cumplimiento": round(sk["Cumplimiento"].mean(), 2) if not sk.empty else 0,
                "Throughput": round(sk["Throughput"].mean(), 2) if not sk.empty else 0,
                "Lead Time": round(sk["Lead_Time"].mean(), 2) if not sk.empty else 0,
                "Utilización Max": round(su["Utilizacion"].max(), 2) if not su.empty else 0,
                "Lotes": len(sim_b),
            })
        comp = pd.DataFrame(rows)
        st.dataframe(comp, use_container_width=True)
        if not comp.empty:
            fig = px.scatter(comp, x="Throughput", y="Lead Time", size="Cumplimiento", color="Escenario", hover_name="Escenario")
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,0.02)", height=420)
            st.plotly_chart(fig, use_container_width=True)

st.caption("Código reestructurado con nueva identidad visual, navegación distinta y organización funcional más ejecutiva.")
