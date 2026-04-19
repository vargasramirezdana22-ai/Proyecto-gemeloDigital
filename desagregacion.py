"""
desagregacion.py
================
Desagregación del plan agregado en unidades por producto para la panadería Dora del Hoyo.

Toma las horas-hombre de producción del plan agregado y las convierte en
unidades producidas por producto y mes, usando optimización lineal (PuLP).

Dependencias: pandas, pulp
"""

import pandas as pd
from pulp import (
    LpProblem, LpMinimize, LpVariable, lpSum, PULP_CBC_CMD
)
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from demanda import (
    PRODUCTOS, MESES, DEM_HISTORICA, HORAS_PRODUCTO, PROD_COLORS
)

# ─────────────────────────────────────────────────────────────────────────────
# INVENTARIO INICIAL POR PRODUCTO
# ─────────────────────────────────────────────────────────────────────────────

INV_INICIAL = {p: 0 for p in PRODUCTOS}


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def run_desagregacion(prod_hh: dict, factor_demanda: float = 1.0):
    """
    Desagrega el plan agregado en unidades por producto y mes.

    Args:
        prod_hh (dict): Producción mensual en H-H disponibles {mes: horas}.
                        Generalmente viene de run_agregacion()["Produccion_HH"].
        factor_demanda (float): Factor multiplicador de demanda (default 1.0).

    Returns:
        dict: {producto: pd.DataFrame} con columnas:
              Mes, Demanda, Produccion, Inv_Ini, Inv_Fin, Backlog
    """
    meses = MESES

    mdl = LpProblem("Desagregacion_Dora_del_Hoyo", LpMinimize)

    # Variables
    X = {(p, t): LpVariable(f"X_{p}_{t}", lowBound=0) for p in PRODUCTOS for t in meses}
    I = {(p, t): LpVariable(f"I_{p}_{t}", lowBound=0) for p in PRODUCTOS for t in meses}
    S = {(p, t): LpVariable(f"S_{p}_{t}", lowBound=0) for p in PRODUCTOS for t in meses}

    # Objetivo: minimizar inventario y backlog
    mdl += lpSum(
        100_000 * I[p, t] + 150_000 * S[p, t]
        for p in PRODUCTOS for t in meses
    ), "Costo_Desagregacion"

    # Restricciones
    for idx, t in enumerate(meses):
        tp = meses[idx - 1] if idx > 0 else None

        # Capacidad mensual disponible (H-H)
        mdl += (
            lpSum(HORAS_PRODUCTO[p] * X[p, t] for p in PRODUCTOS) <= prod_hh[t],
            f"Capacidad_{t}",
        )

        for p in PRODUCTOS:
            d = int(DEM_HISTORICA[p][idx] * factor_demanda)

            if idx == 0:
                mdl += (
                    I[p, t] - S[p, t] == INV_INICIAL[p] + X[p, t] - d,
                    f"Balance_{p}_{t}",
                )
            else:
                mdl += (
                    I[p, t] - S[p, t] == I[p, tp] - S[p, tp] + X[p, t] - d,
                    f"Balance_{p}_{t}",
                )

    mdl.solve(PULP_CBC_CMD(msg=False))

    # ── Construir resultados por producto ─────────────────────────────────────
    resultados = {}
    for p in PRODUCTOS:
        filas = []
        for idx, t in enumerate(meses):
            xv = round(X[p, t].varValue or 0, 2)
            iv = round(I[p, t].varValue or 0, 2)
            sv = round(S[p, t].varValue or 0, 2)
            ini = (
                INV_INICIAL[p] if idx == 0
                else round(I[p, meses[idx - 1]].varValue or 0, 2)
            )
            filas.append({
                "Mes":       t,
                "Demanda":   int(DEM_HISTORICA[p][idx] * factor_demanda),
                "Produccion": xv,
                "Inv_Ini":   ini,
                "Inv_Fin":   iv,
                "Backlog":   sv,
            })
        resultados[p] = pd.DataFrame(filas)

    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# VISUALIZACIONES
# ─────────────────────────────────────────────────────────────────────────────

def fig_desagregacion(desag_dict: dict, mes_sel: str = "January"):
    """
    Subplots: producción vs demanda por producto, con el mes seleccionado marcado.

    Args:
        desag_dict (dict): Resultado de run_desagregacion().
        mes_sel (str): Mes a resaltar con una estrella.

    Returns:
        go.Figure
    """
    fig = make_subplots(
        rows=3, cols=2,
        subplot_titles=[p.replace("_", " ") for p in PRODUCTOS],
        vertical_spacing=0.1,
        horizontal_spacing=0.08,
    )

    for idx, p in enumerate(PRODUCTOS):
        r, c = idx // 2 + 1, idx % 2 + 1
        df = desag_dict[p]

        fig.add_trace(go.Bar(
            x=df["Mes"], y=df["Produccion"],
            name=p.replace("_", " "),
            marker_color=PROD_COLORS[p], opacity=0.85,
            showlegend=False,
            hovertemplate="%{x}<br>Prod: %{y:.0f} und<extra></extra>",
        ), row=r, col=c)

        fig.add_trace(go.Scatter(
            x=df["Mes"], y=df["Demanda"],
            mode="lines+markers", name="Demanda",
            line=dict(color="#81C784", dash="dash", width=1.5),
            marker=dict(size=5), showlegend=False,
        ), row=r, col=c)

        mes_row = df[df["Mes"] == mes_sel]
        if not mes_row.empty:
            fig.add_trace(go.Scatter(
                x=[mes_sel], y=[mes_row["Produccion"].values[0]],
                mode="markers",
                marker=dict(size=12, color="#E8A838", symbol="star"),
                showlegend=False,
            ), row=r, col=c)

    fig.update_layout(
        height=700,
        barmode="group",
        title="Desagregación por Producto (unidades/mes)",
        template="plotly_white",
    )
    return fig


def fig_cobertura(desag_dict: dict):
    """Gráfica de cobertura: cumplimiento producción vs demanda por producto."""
    productos, cobertura = [], []
    for p in PRODUCTOS:
        df = desag_dict[p]
        cob = round(df["Produccion"].sum() / max(df["Demanda"].sum(), 1) * 100, 2)
        productos.append(p.replace("_", " "))
        cobertura.append(cob)

    fig = go.Figure(go.Bar(
        x=productos, y=cobertura,
        marker_color=[PROD_COLORS[p] for p in PRODUCTOS],
        text=[f"{v:.1f}%" for v in cobertura],
        textposition="outside",
    ))
    fig.add_hline(y=100, line_dash="dash", line_color="green",
                  annotation_text="100% cobertura")
    fig.update_layout(
        title="Cobertura de Demanda por Producto (%)",
        yaxis_title="%",
        template="plotly_white",
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Importar agregación para obtener producción en H-H
    from agregacion import run_agregacion
    from demanda import demanda_horas_hombre

    dem_h = demanda_horas_hombre()
    df_agr, costo = run_agregacion(dem_h)
    prod_hh = dict(zip(df_agr["Mes"], df_agr["Produccion_HH"]))

    desag = run_desagregacion(prod_hh)

    for p, df in desag.items():
        total_prod = df["Produccion"].sum()
        total_dem  = df["Demanda"].sum()
        print(f"{p:<22}: Prod={total_prod:,.0f}  Dem={total_dem:,.0f}  "
              f"Cob={total_prod/max(total_dem,1)*100:.1f}%")
