"""
agregacion.py
=============
Modelo de Planeación Agregada para la panadería Dora del Hoyo.

Optimiza el plan mensual en horas-hombre minimizando costos de:
  - Producción, inventario, backlog, horas extra, contratación y despidos.

Dependencias: pandas, pulp
"""

import pandas as pd
from pulp import (
    LpProblem, LpMinimize, LpVariable, lpSum, value, PULP_CBC_CMD
)
import plotly.graph_objects as go

from demanda import MESES, demanda_horas_hombre

# ─────────────────────────────────────────────────────────────────────────────
# PARÁMETROS POR DEFECTO (costos en COP)
# ─────────────────────────────────────────────────────────────────────────────

PARAMS_DEFAULT = {
    "Ct":    4_310,      # Costo por unidad producida
    "Ht":  100_000,      # Costo de mantener inventario (H-H)
    "PIt": 100_000,      # Penalización por backlog (H-H)
    "CRt":  11_364,      # Costo hora regular
    "COt":  14_205,      # Costo hora extra
    "CW_mas":  14_204,   # Costo de contratar un trabajador
    "CW_menos": 15_061,  # Costo de despedir un trabajador
    "M":         1,      # Horas-hombre por unidad
    "LR_inicial": 44 * 4 * 10,  # Horas regulares iniciales (10 empleados)
    "inv_seg":   0.0,    # Fracción de inventario de seguridad
}


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def run_agregacion(dem_horas: dict, params: dict = None):
    """
    Ejecuta el modelo de planeación agregada.

    Args:
        dem_horas (dict): Demanda mensual en horas-hombre {mes: horas}.
        params (dict, optional): Parámetros del modelo. Usa PARAMS_DEFAULT si es None.

    Returns:
        tuple:
            - df (pd.DataFrame): Resultados mensuales del plan.
            - costo (float): Costo total óptimo en COP.
    """
    if params is None:
        params = PARAMS_DEFAULT.copy()

    Ct   = params["Ct"];    Ht  = params["Ht"];  PIt = params["PIt"]
    CRt  = params["CRt"];   COt = params["COt"]
    Wm   = params["CW_mas"]; Wd = params["CW_menos"]
    M    = params["M"];     LRi = params["LR_inicial"]
    meses = MESES

    # ── Modelo ────────────────────────────────────────────────────────────────
    mdl = LpProblem("Agregacion_Dora_del_Hoyo", LpMinimize)

    P      = LpVariable.dicts("P",    meses, lowBound=0)  # Producción
    I      = LpVariable.dicts("I",    meses, lowBound=0)  # Inventario positivo
    S      = LpVariable.dicts("S",    meses, lowBound=0)  # Backlog
    LR     = LpVariable.dicts("LR",   meses, lowBound=0)  # Horas regulares
    LO     = LpVariable.dicts("LO",   meses, lowBound=0)  # Horas extra
    LU     = LpVariable.dicts("LU",   meses, lowBound=0)  # Horas usadas regulares
    NI     = LpVariable.dicts("NI",   meses)              # Inventario neto
    Wmas   = LpVariable.dicts("Wm",   meses, lowBound=0)  # Contrataciones
    Wmenos = LpVariable.dicts("Wd",   meses, lowBound=0)  # Despidos

    # Función objetivo
    mdl += lpSum(
        Ct * P[t] + Ht * I[t] + PIt * S[t] +
        CRt * LR[t] + COt * LO[t] +
        Wm * Wmas[t] + Wd * Wmenos[t]
        for t in meses
    ), "Costo_Total"

    # Restricciones
    for idx, t in enumerate(meses):
        d  = dem_horas[t]
        tp = meses[idx - 1] if idx > 0 else None

        # Balance de inventario neto
        if idx == 0:
            mdl += NI[t] == 0 + P[t] - d,       f"NI_inicial_{t}"
        else:
            mdl += NI[t] == NI[tp] + P[t] - d,  f"NI_{t}"

        mdl += NI[t] == I[t] - S[t],             f"NI_def_{t}"

        # Horas
        mdl += LU[t] + LO[t] == M * P[t],        f"Horas_balance_{t}"
        mdl += LU[t] <= LR[t],                    f"LU_max_{t}"

        # Evolución de fuerza laboral
        if idx == 0:
            mdl += LR[t] == LRi + Wmas[t] - Wmenos[t], f"LR_inicial_{t}"
        else:
            mdl += LR[t] == LR[tp] + Wmas[t] - Wmenos[t], f"LR_{t}"

    mdl.solve(PULP_CBC_CMD(msg=False))
    costo = value(mdl.objective)

    # ── Calcular inventarios inicial/final por periodo ────────────────────────
    ini_l, fin_l = [], []
    for idx, t in enumerate(meses):
        ini = 0.0 if idx == 0 else fin_l[-1]
        ini_l.append(ini)
        fin_l.append(ini + (P[t].varValue or 0) - dem_horas[t])

    # ── DataFrame de resultados ───────────────────────────────────────────────
    df = pd.DataFrame({
        "Mes":                  meses,
        "Demanda_HH":           [round(dem_horas[t], 2)             for t in meses],
        "Produccion_HH":        [round(P[t].varValue or 0, 2)       for t in meses],
        "Backlog_HH":           [round(S[t].varValue or 0, 2)       for t in meses],
        "Horas_Regulares":      [round(LR[t].varValue or 0, 2)      for t in meses],
        "Horas_Extras":         [round(LO[t].varValue or 0, 2)      for t in meses],
        "Inventario_Inicial_HH":[round(v, 2)                        for v in ini_l],
        "Inventario_Final_HH":  [round(v, 2)                        for v in fin_l],
        "Contratacion":         [round(Wmas[t].varValue or 0, 2)    for t in meses],
        "Despidos":             [round(Wmenos[t].varValue or 0, 2)  for t in meses],
    })

    return df, costo


# ─────────────────────────────────────────────────────────────────────────────
# VISUALIZACIÓN
# ─────────────────────────────────────────────────────────────────────────────

def fig_plan_agregado(df: pd.DataFrame, costo: float):
    """
    Genera la gráfica del plan agregado con barras apiladas y líneas de referencia.

    Args:
        df (pd.DataFrame): Resultado de run_agregacion().
        costo (float): Costo total óptimo.

    Returns:
        go.Figure
    """
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df["Mes"], y=df["Inventario_Inicial_HH"],
        name="Inv. Inicial (H-H)", marker_color="#5C6BC0", opacity=0.8,
    ))
    fig.add_trace(go.Bar(
        x=df["Mes"], y=df["Produccion_HH"],
        name="Producción (H-H)", marker_color="#E8A838", opacity=0.85,
    ))
    fig.add_trace(go.Scatter(
        x=df["Mes"], y=df["Demanda_HH"],
        mode="lines+markers", name="Demanda (H-H)",
        line=dict(color="#81C784", dash="dash", width=2.5),
        marker=dict(size=7),
    ))
    fig.add_trace(go.Scatter(
        x=df["Mes"], y=df["Horas_Regulares"],
        mode="lines", name="Cap. Regular",
        line=dict(color="#FF8A65", dash="dot", width=2),
    ))

    fig.update_layout(
        barmode="stack",
        title=f"Plan Agregado — Costo Óptimo: COP ${costo:,.0f}",
        xaxis_title="Mes",
        yaxis_title="Horas-Hombre (H-H)",
        template="plotly_white",
        legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
    )
    return fig


def fig_fuerza_laboral(df: pd.DataFrame):
    """Gráfica de evolución de contrataciones y despidos."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["Mes"], y=df["Contratacion"],
        name="Contrataciones", marker_color="#4FC3F7",
    ))
    fig.add_trace(go.Bar(
        x=df["Mes"], y=df["Despidos"],
        name="Despidos", marker_color="#EF5350",
    ))
    fig.update_layout(
        barmode="group",
        title="Movimiento de Fuerza Laboral",
        xaxis_title="Mes",
        yaxis_title="Personas",
        template="plotly_white",
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    dem_h = demanda_horas_hombre()
    df, costo = run_agregacion(dem_h)

    print(f"Estado del solver: Óptimo")
    print(f"Costo total: COP ${costo:,.0f}\n")
    print(df.to_string(index=False))
