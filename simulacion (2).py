"""
simulacion.py
=============
Simulación de eventos discretos del flujo de producción para la panadería Dora del Hoyo.

Modela el recorrido de lotes de producción a través de las estaciones de trabajo:
  Mezclado → Dosificado/Moldeado → Horneado → Enfriamiento → Empaque

Incluye:
  - Recursos compartidos con colas (SimPy)
  - Tiempos estocásticos por etapa y producto
  - Sensores virtuales del horno (temperatura, ocupación)
  - Soporte para fallas en horno y reducción de tiempos (doble turno)

Dependencias: simpy, pandas, numpy
"""

import math
import random
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import simpy

from demanda import PRODUCTOS, PROD_COLORS

# ─────────────────────────────────────────────────────────────────────────────
# DATOS MAESTROS DE PRODUCCIÓN
# ─────────────────────────────────────────────────────────────────────────────

# Rutas de producción: (nombre_etapa, recurso, t_min_min, t_max_min)
RUTAS = {
    "Brownies": [
        ("Mezclado",    "mezcla",       12, 18),
        ("Moldeado",    "dosificado",    8, 14),
        ("Horneado",    "horno",        30, 40),
        ("Enfriamiento","enfriamiento", 25, 35),
        ("Corte_Empaque","empaque",      8, 12),
    ],
    "Mantecadas": [
        ("Mezclado",    "mezcla",       12, 18),
        ("Dosificado",  "dosificado",   16, 24),
        ("Horneado",    "horno",        20, 30),
        ("Enfriamiento","enfriamiento", 35, 55),
        ("Empaque",     "empaque",       4,  6),
    ],
    "Mantecadas_Amapola": [
        ("Mezclado",    "mezcla",       12, 18),
        ("Inc_Semillas","mezcla",        8, 12),
        ("Dosificado",  "dosificado",   16, 24),
        ("Horneado",    "horno",        20, 30),
        ("Enfriamiento","enfriamiento", 36, 54),
        ("Empaque",     "empaque",       4,  6),
    ],
    "Torta_Naranja": [
        ("Mezclado",    "mezcla",       16, 24),
        ("Dosificado",  "dosificado",    8, 12),
        ("Horneado",    "horno",        32, 48),
        ("Enfriamiento","enfriamiento", 48, 72),
        ("Desmolde",    "dosificado",    8, 12),
        ("Empaque",     "empaque",       8, 12),
    ],
    "Pan_Maiz": [
        ("Mezclado",    "mezcla",       12, 18),
        ("Amasado",     "amasado",      16, 24),
        ("Moldeado",    "dosificado",   12, 18),
        ("Horneado",    "horno",        28, 42),
        ("Enfriamiento","enfriamiento", 36, 54),
        ("Empaque",     "empaque",       4,  6),
    ],
}

TAMANO_LOTE_BASE = {
    "Brownies":           12,
    "Mantecadas":         10,
    "Mantecadas_Amapola": 10,
    "Torta_Naranja":      12,
    "Pan_Maiz":           15,
}

CAPACIDAD_BASE = {
    "mezcla":      2,
    "dosificado":  2,
    "horno":       3,
    "enfriamiento":4,
    "empaque":     2,
    "amasado":     1,
}


# ─────────────────────────────────────────────────────────────────────────────
# SIMULACIÓN
# ─────────────────────────────────────────────────────────────────────────────

def run_simulacion(
    plan_unidades: dict,
    cap_recursos: dict = None,
    falla: bool = False,
    factor_t: float = 1.0,
    tamano_lote: dict = None,
    semilla: int = 42,
):
    """
    Ejecuta la simulación de eventos discretos (SimPy).

    Args:
        plan_unidades (dict): {producto: unidades_a_producir}.
        cap_recursos (dict): Capacidad de cada estación (default CAPACIDAD_BASE).
        falla (bool): Si True, simula fallas aleatorias en el horno.
        factor_t (float): Factor de tiempo (< 1 = más rápido, ej. 0.8 doble turno).
        tamano_lote (dict): Tamaño de lote por producto (default TAMANO_LOTE_BASE).
        semilla (int): Semilla aleatoria para reproducibilidad.

    Returns:
        tuple:
            - df_lotes (pd.DataFrame): Registro de lotes completados.
            - df_uso (pd.DataFrame): Uso de recursos por instante.
            - df_sensores (pd.DataFrame): Lecturas del sensor de horno.
    """
    random.seed(semilla)
    np.random.seed(semilla)

    if cap_recursos is None:
        cap_recursos = CAPACIDAD_BASE.copy()
    if tamano_lote is None:
        tamano_lote = TAMANO_LOTE_BASE.copy()

    lotes_data, uso_rec, sensores = [], [], []

    # ── Sensor virtual del horno ──────────────────────────────────────────────
    def sensor_horno(env, recursos):
        while True:
            ocp  = recursos["horno"].count
            temp = round(np.random.normal(160 + ocp * 20, 5), 2)
            sensores.append({
                "tiempo":      round(env.now, 1),
                "temperatura": temp,
                "horno_ocup":  ocp,
                "horno_cola":  len(recursos["horno"].queue),
            })
            yield env.timeout(10)

    # ── Registro de uso de recursos ───────────────────────────────────────────
    def reg_uso(env, recursos, prod="", lid=""):
        ts = round(env.now, 3)
        for nm, r in recursos.items():
            uso_rec.append({
                "tiempo":    ts,
                "recurso":   nm,
                "ocupados":  r.count,
                "cola":      len(r.queue),
                "capacidad": r.capacity,
                "producto":  prod,
            })

    # ── Proceso de un lote ────────────────────────────────────────────────────
    def proceso_lote(env, lid, prod, tam, recursos):
        t0     = env.now
        esperas = {}

        for etapa, rec_nm, tmin, tmax in RUTAS[prod]:
            escala = math.sqrt(tam / TAMANO_LOTE_BASE[prod])
            tp     = random.uniform(tmin, tmax) * escala * factor_t

            # Falla aleatoria en horno
            if falla and rec_nm == "horno":
                tp += random.uniform(10, 30)

            reg_uso(env, recursos, prod, lid)
            t_entrada = env.now

            with recursos[rec_nm].request() as req:
                yield req
                esperas[etapa] = round(env.now - t_entrada, 3)
                reg_uso(env, recursos, prod, lid)
                yield env.timeout(tp)

            reg_uso(env, recursos, prod, lid)

        lotes_data.append({
            "lote_id":       lid,
            "producto":      prod,
            "tamano":        tam,
            "t_creacion":    round(t0, 3),
            "t_fin":         round(env.now, 3),
            "tiempo_sistema":round(env.now - t0, 3),
            "total_espera":  round(sum(esperas.values()), 3),
        })

    # ── Ambiente SimPy ────────────────────────────────────────────────────────
    env      = simpy.Environment()
    recursos = {nm: simpy.Resource(env, capacity=cap) for nm, cap in cap_recursos.items()}
    env.process(sensor_horno(env, recursos))

    # Generar lista de lotes ordenados por tiempo de llegada
    dur_mes = 44 * 4 * 60  # minutos disponibles en el mes
    lotes   = []
    ctr     = [0]

    for prod, unid in plan_unidades.items():
        if unid <= 0:
            continue
        tam  = tamano_lote[prod]
        n    = math.ceil(unid / tam)
        tasa = dur_mes / max(n, 1)
        ta   = random.expovariate(1 / max(tasa, 1))
        rem  = unid

        for _ in range(n):
            lotes.append((round(ta, 2), prod, min(tam, int(rem))))
            rem -= tam
            ta  += random.expovariate(1 / max(tasa, 1))

    lotes.sort(key=lambda x: x[0])

    # Proceso lanzador de lotes
    def lanzador():
        for ta, prod, tam in lotes:
            yield env.timeout(max(ta - env.now, 0))
            lid = f"{prod[:3].upper()}_{ctr[0]:04d}"
            ctr[0] += 1
            env.process(proceso_lote(env, lid, prod, tam, recursos))

    env.process(lanzador())
    env.run(until=dur_mes * 1.8)

    df_lotes   = pd.DataFrame(lotes_data) if lotes_data else pd.DataFrame()
    df_uso     = pd.DataFrame(uso_rec)    if uso_rec    else pd.DataFrame()
    df_sensores= pd.DataFrame(sensores)   if sensores   else pd.DataFrame()

    return df_lotes, df_uso, df_sensores


# ─────────────────────────────────────────────────────────────────────────────
# KPIs Y UTILIZACIÓN
# ─────────────────────────────────────────────────────────────────────────────

def calc_utilizacion(df_uso: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula utilización, cola promedio y máxima por recurso.

    Args:
        df_uso (pd.DataFrame): Registro de uso de run_simulacion().

    Returns:
        pd.DataFrame con columnas: Recurso, Utilización_%, Cola Prom, Cola Máx,
                                   Capacidad, Cuello Botella.
    """
    if df_uso.empty:
        return pd.DataFrame()

    filas = []
    for rec, grp in df_uso.groupby("recurso"):
        grp = grp.sort_values("tiempo").reset_index(drop=True)
        cap = grp["capacidad"].iloc[0]
        t   = grp["tiempo"].values
        ocp = grp["ocupados"].values

        if len(t) > 1 and (t[-1] - t[0]) > 0:
            fn_trapz = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
            area = fn_trapz(ocp, t)
            util = round(area / (cap * (t[-1] - t[0])) * 100, 2)
        else:
            util = 0.0

        filas.append({
            "Recurso":        rec,
            "Utilización_%":  util,
            "Cola Prom":      round(grp["cola"].mean(), 3),
            "Cola Máx":       int(grp["cola"].max()),
            "Capacidad":      int(cap),
            "Cuello Botella": util >= 80 or grp["cola"].mean() > 0.5,
        })

    return (
        pd.DataFrame(filas)
        .sort_values("Utilización_%", ascending=False)
        .reset_index(drop=True)
    )


def calc_kpis(df_lotes: pd.DataFrame, plan: dict) -> pd.DataFrame:
    """
    Calcula KPIs operativos por producto.

    Args:
        df_lotes (pd.DataFrame): Registro de lotes de run_simulacion().
        plan (dict): Plan de producción {producto: unidades}.

    Returns:
        pd.DataFrame con throughput, cycle time, lead time, WIP y cumplimiento.
    """
    if df_lotes.empty:
        return pd.DataFrame()

    from demanda import DEM_HISTORICA, MESES
    dur = (df_lotes["t_fin"].max() - df_lotes["t_creacion"].min()) / 60
    filas = []

    for p in PRODUCTOS:
        sub = df_lotes[df_lotes["producto"] == p]
        if sub.empty:
            continue

        und      = sub["tamano"].sum()
        plan_und = plan.get(p, 0)
        tp       = round(und / max(dur, 0.01), 3)
        ct       = round((sub["tiempo_sistema"] / sub["tamano"]).mean(), 3)
        lt       = round(sub["tiempo_sistema"].mean(), 3)
        dem_avg  = sum(DEM_HISTORICA[p]) / 12
        takt     = round((44 * 4 * 60) / max(dem_avg / TAMANO_LOTE_BASE[p], 1), 2)
        wip      = round(tp * (lt / 60), 2)

        filas.append({
            "Producto":              p,
            "Und Producidas":        und,
            "Plan":                  plan_und,
            "Throughput (und/h)":    tp,
            "Cycle Time (min/und)":  ct,
            "Lead Time (min/lote)":  lt,
            "WIP Prom":              wip,
            "Takt Time (min/lote)":  takt,
            "Cumplimiento %":        round(min(und / max(plan_und, 1) * 100, 100), 2),
        })

    return pd.DataFrame(filas)


# ─────────────────────────────────────────────────────────────────────────────
# VISUALIZACIONES
# ─────────────────────────────────────────────────────────────────────────────

def fig_gantt(df_lotes: pd.DataFrame, n: int = 80) -> go.Figure:
    """Diagrama de Gantt de los primeros n lotes."""
    if df_lotes.empty:
        return go.Figure()

    sub = df_lotes.head(n).copy().reset_index(drop=True)
    fig = go.Figure()

    for _, row in sub.iterrows():
        col = PROD_COLORS.get(row["producto"], "#aaa")
        fig.add_trace(go.Bar(
            x=[row["tiempo_sistema"]],
            y=[row["lote_id"]],
            base=[row["t_creacion"]],
            orientation="h",
            marker_color=col, opacity=0.8,
            hovertemplate=(
                f"<b>{row['producto']}</b><br>"
                f"Inicio: {row['t_creacion']:.0f} min<br>"
                f"Duración: {row['tiempo_sistema']:.1f} min<extra></extra>"
            ),
            showlegend=False,
        ))

    for p, c in PROD_COLORS.items():
        fig.add_trace(go.Bar(x=[None], y=[None], marker_color=c,
                             name=p.replace("_", " "), showlegend=True))

    fig.update_layout(
        barmode="overlay",
        title="Diagrama de Gantt — Lotes de Producción",
        xaxis_title="Tiempo simulado (min)",
        yaxis_title="Lote ID",
        template="plotly_white",
        height=max(350, len(sub) * 7),
        legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center"),
    )
    return fig


def fig_utilizacion(df_uso: pd.DataFrame) -> go.Figure:
    """Gráficas de utilización y cola por recurso."""
    df_ut = calc_utilizacion(df_uso)
    if df_ut.empty:
        return go.Figure()

    colores = [
        "#c0392b" if u >= 80 else "#E8A838" if u >= 60 else "#4FC3F7"
        for u in df_ut["Utilización_%"]
    ]

    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=["Utilización (%)", "Cola Promedio"])
    fig.add_trace(go.Bar(
        x=df_ut["Recurso"], y=df_ut["Utilización_%"],
        marker_color=colores,
        text=df_ut["Utilización_%"].apply(lambda v: f"{v:.1f}%"),
        textposition="outside", showlegend=False,
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        x=df_ut["Recurso"], y=df_ut["Cola Prom"],
        marker_color="#CE93D8",
        text=df_ut["Cola Prom"].apply(lambda v: f"{v:.2f}"),
        textposition="outside", showlegend=False,
    ), row=1, col=2)
    fig.add_hline(y=80, line_dash="dash", line_color="#c0392b",
                  annotation_text="⚠ 80%", row=1, col=1)
    fig.update_layout(
        title="Utilización de Recursos — Detección Cuellos de Botella",
        template="plotly_white",
    )
    return fig


def fig_sensores(df_s: pd.DataFrame) -> go.Figure:
    """Gráficas de temperatura y ocupación del horno."""
    if df_s.empty:
        return go.Figure()

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        subplot_titles=["Temperatura Horno (°C)", "Ocupación Horno"])

    fig.add_trace(go.Scatter(
        x=df_s["tiempo"], y=df_s["temperatura"],
        mode="lines", name="Temperatura",
        line=dict(color="#FF8A65", width=1.5),
    ), row=1, col=1)
    fig.add_hline(y=200, line_dash="dash", line_color="#c0392b",
                  annotation_text="Límite 200°C", row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df_s["tiempo"], y=df_s["horno_ocup"],
        mode="lines", name="Ocupación",
        fill="tozeroy", fillcolor="rgba(79,195,247,0.12)",
        line=dict(color="#4FC3F7", width=1.5),
    ), row=2, col=1)

    fig.update_layout(
        title="Sensores Virtuales — Monitor del Horno",
        template="plotly_white",
        height=460,
    )
    fig.update_xaxes(title_text="Tiempo simulado (min)", row=2, col=1)
    fig.update_yaxes(title_text="°C", row=1, col=1)
    fig.update_yaxes(title_text="Estaciones", row=2, col=1)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    plan_prueba = {
        "Brownies":           315,
        "Mantecadas":         125,
        "Mantecadas_Amapola": 320,
        "Torta_Naranja":      100,
        "Pan_Maiz":           330,
    }

    print("Ejecutando simulación de prueba (enero)...")
    df_l, df_u, df_s = run_simulacion(plan_prueba)

    print(f"Lotes completados : {len(df_l)}")
    print(f"Temp. máx. horno  : {df_s['temperatura'].max():.1f} °C")

    df_ut = calc_utilizacion(df_u)
    print("\nUtilización por recurso:")
    print(df_ut[["Recurso", "Utilización_%", "Cola Prom", "Cuello Botella"]].to_string(index=False))

    df_kpi = calc_kpis(df_l, plan_prueba)
    print("\nKPIs por producto:")
    print(df_kpi[["Producto", "Und Producidas", "Throughput (und/h)", "Cumplimiento %"]].to_string(index=False))
