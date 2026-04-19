"""
demanda.py
==========
Datos históricos de demanda y funciones de análisis para la panadería Dora del Hoyo.

Productos: Brownies, Mantecadas, Mantecadas_Amapola, Torta_Naranja, Pan_Maiz
Horizonte: 12 meses (enero a diciembre)
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# ─────────────────────────────────────────────────────────────────────────────
# DATOS MAESTROS
# ─────────────────────────────────────────────────────────────────────────────

PRODUCTOS = [
    "Brownies",
    "Mantecadas",
    "Mantecadas_Amapola",
    "Torta_Naranja",
    "Pan_Maiz",
]

MESES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

DEM_HISTORICA = {
    "Brownies":           [315, 804, 734, 541, 494,  59, 315, 803, 734, 541, 494,  59],
    "Mantecadas":         [125, 780, 432, 910, 275,  68, 512, 834, 690, 455, 389, 120],
    "Mantecadas_Amapola": [320, 710, 520, 251, 631, 150, 330, 220, 710, 610, 489, 180],
    "Torta_Naranja":      [100, 250, 200, 101, 190,  50, 100, 220, 200, 170, 180, 187],
    "Pan_Maiz":           [330, 140, 143,  73,  83,  48,  70,  89, 118,  83,  67,  87],
}

# Horas-hombre requeridas por unidad producida
HORAS_PRODUCTO = {
    "Brownies":           0.866,
    "Mantecadas":         0.175,
    "Mantecadas_Amapola": 0.175,
    "Torta_Naranja":      0.175,
    "Pan_Maiz":           0.312,
}

# Paleta de colores por producto
PROD_COLORS = {
    "Brownies":           "#E8A838",
    "Mantecadas":         "#4FC3F7",
    "Mantecadas_Amapola": "#81C784",
    "Torta_Naranja":      "#CE93D8",
    "Pan_Maiz":           "#FF8A65",
}

# ─────────────────────────────────────────────────────────────────────────────
# FUNCIONES DE ANÁLISIS
# ─────────────────────────────────────────────────────────────────────────────

def get_dataframe_demanda():
    """Retorna la demanda histórica como DataFrame (filas=meses, cols=productos)."""
    return pd.DataFrame(DEM_HISTORICA, index=MESES)


def demanda_total_anual():
    """Retorna un dict con la demanda total anual por producto."""
    return {p: sum(DEM_HISTORICA[p]) for p in PRODUCTOS}


def mes_pico(producto=None):
    """
    Retorna el mes de mayor demanda.
    Si se indica un producto, lo calcula para ese producto;
    si no, lo calcula sobre la demanda agregada de todos los productos.
    """
    if producto:
        vals = DEM_HISTORICA[producto]
        return MESES[vals.index(max(vals))]
    else:
        totales = [sum(DEM_HISTORICA[p][i] for p in PRODUCTOS) for i in range(12)]
        return MESES[totales.index(max(totales))]


def demanda_horas_hombre(factor_mensual=None):
    """
    Convierte la demanda en unidades a horas-hombre por mes.

    Args:
        factor_mensual (dict, optional): Factores multiplicadores por mes.
                                         Si es None, se usa 1.0 para todos.

    Returns:
        dict: {mes: horas_hombre_requeridas}
    """
    if factor_mensual is None:
        factor_mensual = {m: 1.0 for m in MESES}

    return {
        mes: round(
            sum(DEM_HISTORICA[p][i] * HORAS_PRODUCTO[p] for p in PRODUCTOS)
            * factor_mensual.get(mes, 1.0),
            4
        )
        for i, mes in enumerate(MESES)
    }


def resumen_estadistico():
    """Retorna un DataFrame con estadísticas descriptivas de la demanda por producto."""
    df = get_dataframe_demanda()
    stats = df.describe().T
    stats["cv_%"] = (stats["std"] / stats["mean"] * 100).round(2)
    return stats.round(2)


# ─────────────────────────────────────────────────────────────────────────────
# VISUALIZACIONES
# ─────────────────────────────────────────────────────────────────────────────

def fig_barras_agrupadas():
    """Gráfica de barras agrupadas: demanda por producto y mes."""
    fig = go.Figure()
    for p in PRODUCTOS:
        fig.add_trace(go.Bar(
            x=MESES,
            y=DEM_HISTORICA[p],
            name=p.replace("_", " "),
            marker_color=PROD_COLORS[p],
            opacity=0.85,
            hovertemplate=f"<b>{p}</b><br>%{{x}}<br>%{{y:.0f}} und<extra></extra>",
        ))
    fig.update_layout(
        barmode="group",
        title="Demanda Histórica por Producto",
        xaxis_title="Mes",
        yaxis_title="Unidades",
        template="plotly_white",
        legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
    )
    return fig


def fig_heatmap():
    """Mapa de calor de estacionalidad de la demanda."""
    z = [[DEM_HISTORICA[p][i] for i in range(12)] for p in PRODUCTOS]
    fig = go.Figure(go.Heatmap(
        z=z,
        x=MESES,
        y=[p.replace("_", " ") for p in PRODUCTOS],
        colorscale="YlOrBr",
        hovertemplate="%{y}<br>%{x}<br>%{z:.0f} und<extra></extra>",
    ))
    fig.update_layout(
        title="Mapa de Calor — Estacionalidad de la Demanda",
        template="plotly_white",
    )
    return fig


def fig_lineas_tendencia():
    """Gráfica de líneas para ver tendencias mensuales por producto."""
    fig = go.Figure()
    for p in PRODUCTOS:
        fig.add_trace(go.Scatter(
            x=MESES,
            y=DEM_HISTORICA[p],
            mode="lines+markers",
            name=p.replace("_", " "),
            line=dict(color=PROD_COLORS[p], width=2),
            marker=dict(size=6),
        ))
    fig.update_layout(
        title="Tendencia Mensual de Demanda por Producto",
        xaxis_title="Mes",
        yaxis_title="Unidades",
        template="plotly_white",
        legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# MAIN — ejecución directa para prueba rápida
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Demanda total anual por producto ===")
    for p, v in demanda_total_anual().items():
        print(f"  {p:<22}: {v:,} und")

    print(f"\nMes pico (agregado): {mes_pico()}")

    print("\n=== Demanda en Horas-Hombre (primer mes) ===")
    hh = demanda_horas_hombre()
    for m, h in list(hh.items())[:3]:
        print(f"  {m}: {h} H-H")

    print("\n=== Resumen Estadístico ===")
    print(resumen_estadistico())
