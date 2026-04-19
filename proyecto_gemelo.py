"""
proyecto_gemelo.py
==================
Punto de entrada del Gemelo Digital — Panadería Dora del Hoyo.

Ejecuta el pipeline completo y genera un reporte de resultados en consola.
También puede usarse como script de arranque del dashboard Dash.

Uso:
    # Sólo pipeline en consola
    python proyecto_gemelo.py

    # Arrancar el dashboard web
    python dashboard_gemelo.py
"""

import pandas as pd
from gemeloDigital import run_pipeline, run_escenario, ESCENARIOS_DEF, MESES

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN DE EJECUCIÓN
# ─────────────────────────────────────────────────────────────────────────────

CONFIG = {
    "mes_idx":        1,      # Febrero
    "factor_demanda": 1.0,    # Demanda normal
    "cap_horno":      3,      # 3 estaciones de horno
    "falla_horno":    False,  # Sin fallas
    "doble_turno":    False,  # Turno normal
    "semilla":        42,
}


# ─────────────────────────────────────────────────────────────────────────────
# REPORTE EN CONSOLA
# ─────────────────────────────────────────────────────────────────────────────

def _sep(char="─", n=64):
    print(char * n)


def imprimir_reporte(res: dict):
    """Imprime un reporte completo en consola."""
    _sep("═")
    print("  GEMELO DIGITAL — DORA DEL HOYO")
    print(f"  Mes: {res['mes_nombre']}  |  Costo agregado: COP ${res['costo_agregado']:,.0f}")
    _sep("═")

    # ── Plan agregado ─────────────────────────────────────────────────────────
    _sep()
    print("PLAN AGREGADO (horas-hombre)")
    _sep()
    cols_agr = ["Mes", "Demanda_HH", "Produccion_HH", "Horas_Extras",
                "Contratacion", "Despidos", "Backlog_HH"]
    print(res["df_agregacion"][cols_agr].to_string(index=False))

    # ── Plan del mes ──────────────────────────────────────────────────────────
    _sep()
    print(f"PLAN DEL MES: {res['mes_nombre']} (unidades por producto)")
    _sep()
    for p, u in res["plan_mes"].items():
        print(f"  {p:<22}: {u:>6,} und")

    # ── KPIs ──────────────────────────────────────────────────────────────────
    _sep()
    print("KPIs POR PRODUCTO")
    _sep()
    cols_kpi = ["Producto", "Und Producidas", "Plan",
                "Throughput (und/h)", "Lead Time (min/lote)", "Cumplimiento %"]
    if not res["df_kpis"].empty:
        print(res["df_kpis"][cols_kpi].to_string(index=False))

    # ── Utilización ───────────────────────────────────────────────────────────
    _sep()
    print("UTILIZACIÓN DE RECURSOS")
    _sep()
    if not res["df_utilizacion"].empty:
        print(res["df_utilizacion"][
            ["Recurso", "Utilización_%", "Cola Prom", "Cola Máx", "Cuello Botella"]
        ].to_string(index=False))

    # ── Sensores ──────────────────────────────────────────────────────────────
    _sep()
    print("SENSORES VIRTUALES — HORNO")
    _sep()
    if not res["df_sensores"].empty:
        s = res["df_sensores"]["temperatura"]
        print(f"  Temp. mínima  : {s.min():.1f} °C")
        print(f"  Temp. máxima  : {s.max():.1f} °C")
        print(f"  Temp. promedio: {s.mean():.1f} °C")
        excesos = (res["df_sensores"]["temperatura"] > 200).sum()
        if excesos:
            print(f"  ⚠ Lecturas > 200°C: {excesos}")
        else:
            print("  ✓ Temperatura dentro de rango")

    _sep("═")


def comparar_escenarios(plan_mes: dict, escenarios: list = None):
    """
    Ejecuta y compara múltiples escenarios what-if.

    Args:
        plan_mes (dict): Plan base del mes.
        escenarios (list): Lista de nombres de escenarios. None = todos.
    """
    if escenarios is None:
        escenarios = list(ESCENARIOS_DEF.keys())

    _sep("═")
    print("ANÁLISIS DE ESCENARIOS WHAT-IF")
    _sep("═")

    filas = []
    for nm in escenarios:
        print(f"  Corriendo escenario: {nm}...")
        r = run_escenario(nm, plan_mes)
        fila = {"Escenario": nm}
        if not r["kpis"].empty:
            for col in ["Throughput (und/h)", "Lead Time (min/lote)",
                         "WIP Prom", "Cumplimiento %"]:
                if col in r["kpis"].columns:
                    fila[col] = round(r["kpis"][col].mean(), 2)
        if not r["util"].empty and "Utilización_%" in r["util"].columns:
            fila["Util Máx %"] = round(r["util"]["Utilización_%"].max(), 2)
        filas.append(fila)

    df_comp = pd.DataFrame(filas)
    _sep()
    print(df_comp.to_string(index=False))
    _sep("═")
    return df_comp


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\nIniciando pipeline del Gemelo Digital...")

    # Pipeline principal
    res = run_pipeline(**CONFIG)
    imprimir_reporte(res)

    # Comparación de escenarios (sólo base y demanda alta por defecto)
    escenarios_demo = ["base", "demanda_20", "falla_horno", "doble_turno"]
    df_comp = comparar_escenarios(res["plan_mes"], escenarios_demo)

    print("\n✓ Pipeline completado exitosamente.")
    print("  Para el dashboard visual, ejecuta: python dashboard_gemelo.py\n")
