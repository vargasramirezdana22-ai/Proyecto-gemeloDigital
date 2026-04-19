"""
gemeloDigital.py
================
Módulo central del Gemelo Digital — Panadería Dora del Hoyo.

Orquesta el pipeline completo:
  1. Demanda en horas-hombre
  2. Planeación agregada (PuLP)
  3. Desagregación por producto
  4. Simulación de eventos discretos (SimPy)
  5. KPIs y utilización de recursos

Expone la función principal `run_pipeline()` que retorna todos los resultados
listos para ser consumidos por el dashboard o cualquier análisis externo.

Dependencias: pandas, numpy, pulp, simpy
"""

from demanda import (
    PRODUCTOS, MESES, DEM_HISTORICA, HORAS_PRODUCTO,
    PROD_COLORS, demanda_horas_hombre,
)
from agregacion import run_agregacion, PARAMS_DEFAULT
from desagregacion import run_desagregacion, INV_INICIAL
from simulacion import (
    run_simulacion, calc_utilizacion, calc_kpis,
    RUTAS, TAMANO_LOTE_BASE, CAPACIDAD_BASE,
)

# ─────────────────────────────────────────────────────────────────────────────
# RE-EXPORTAR CONSTANTES PARA ACCESO CENTRALIZADO
# ─────────────────────────────────────────────────────────────────────────────

__all__ = [
    "PRODUCTOS", "MESES", "DEM_HISTORICA", "HORAS_PRODUCTO",
    "PROD_COLORS", "INV_INICIAL", "RUTAS",
    "TAMANO_LOTE_BASE", "CAPACIDAD_BASE", "PARAMS_DEFAULT",
    "run_pipeline",
]


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE COMPLETO
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(
    mes_idx: int = 1,
    factor_demanda: float = 1.0,
    cap_horno: int = 3,
    falla_horno: bool = False,
    doble_turno: bool = False,
    params_agr: dict = None,
    semilla: int = 42,
):
    """
    Ejecuta el pipeline completo del gemelo digital.

    Args:
        mes_idx (int): Índice del mes a simular (0=enero … 11=diciembre).
        factor_demanda (float): Multiplicador global de demanda.
        cap_horno (int): Capacidad del horno (estaciones simultáneas).
        falla_horno (bool): Activar fallas aleatorias en el horno.
        doble_turno (bool): Si True, reduce tiempos de proceso un 20%.
        params_agr (dict): Parámetros del modelo agregado (usa PARAMS_DEFAULT si None).
        semilla (int): Semilla aleatoria para la simulación.

    Returns:
        dict con claves:
            'df_agregacion'  → pd.DataFrame  (plan mensual H-H)
            'costo_agregado' → float          (COP)
            'desagregacion'  → dict           {producto: pd.DataFrame}
            'plan_mes'       → dict           {producto: unidades}
            'df_lotes'       → pd.DataFrame  (lotes simulados)
            'df_uso'         → pd.DataFrame  (uso de recursos)
            'df_sensores'    → pd.DataFrame  (lecturas horno)
            'df_kpis'        → pd.DataFrame  (KPIs por producto)
            'df_utilizacion' → pd.DataFrame  (utilización por recurso)
            'mes_nombre'     → str
    """
    # ── 1. Demanda en H-H ────────────────────────────────────────────────────
    dem_h = demanda_horas_hombre(
        factor_mensual={m: factor_demanda for m in MESES}
    )

    # ── 2. Plan agregado ─────────────────────────────────────────────────────
    df_agr, costo = run_agregacion(dem_h, params=params_agr)
    prod_hh = dict(zip(df_agr["Mes"], df_agr["Produccion_HH"]))

    # ── 3. Desagregación ─────────────────────────────────────────────────────
    desag = run_desagregacion(prod_hh, factor_demanda)

    # ── 4. Plan del mes seleccionado ─────────────────────────────────────────
    mes_nm = MESES[mes_idx]
    plan_mes = {
        p: int(desag[p].loc[desag[p]["Mes"] == mes_nm, "Produccion"].values[0])
        for p in PRODUCTOS
    }

    # ── 5. Simulación ────────────────────────────────────────────────────────
    cap_rec  = {**CAPACIDAD_BASE, "horno": int(cap_horno)}
    factor_t = 0.80 if doble_turno else 1.0

    df_lotes, df_uso, df_sensores = run_simulacion(
        plan_mes, cap_rec, falla_horno, factor_t, semilla=semilla
    )

    # ── 6. KPIs y utilización ────────────────────────────────────────────────
    df_kpis = calc_kpis(df_lotes, plan_mes)
    df_util  = calc_utilizacion(df_uso)

    return {
        "df_agregacion":  df_agr,
        "costo_agregado": costo,
        "desagregacion":  desag,
        "plan_mes":       plan_mes,
        "df_lotes":       df_lotes,
        "df_uso":         df_uso,
        "df_sensores":    df_sensores,
        "df_kpis":        df_kpis,
        "df_utilizacion": df_util,
        "mes_nombre":     mes_nm,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ANÁLISIS DE ESCENARIOS
# ─────────────────────────────────────────────────────────────────────────────

ESCENARIOS_DEF = {
    "base":        {"fd": 1.0, "falla": False, "ft": 1.0,  "dh": 0},
    "demanda_20":  {"fd": 1.2, "falla": False, "ft": 1.0,  "dh": 0},
    "falla_horno": {"fd": 1.0, "falla": True,  "ft": 1.0,  "dh": 0},
    "red_cap":     {"fd": 1.0, "falla": False, "ft": 1.0,  "dh": -1},
    "doble_turno": {"fd": 1.0, "falla": False, "ft": 0.80, "dh": 0},
    "lote_grande": {"fd": 1.0, "falla": False, "ft": 1.0,  "dh": 0, "fl": 1.5},
    "optimizado":  {"fd": 1.0, "falla": False, "ft": 0.85, "dh": 1},
}


def run_escenario(nombre: str, plan_mes: dict, cap_horno_base: int = 3):
    """
    Ejecuta un escenario what-if sobre el plan del mes dado.

    Args:
        nombre (str): Clave del escenario en ESCENARIOS_DEF.
        plan_mes (dict): Plan base {producto: unidades}.
        cap_horno_base (int): Capacidad base del horno.

    Returns:
        dict con 'kpis' y 'util' como pd.DataFrame.
    """
    cfg = ESCENARIOS_DEF.get(nombre, ESCENARIOS_DEF["base"])

    plan_aj = {p: max(int(u * cfg["fd"]), 0) for p, u in plan_mes.items()}
    cap_rec = {
        **CAPACIDAD_BASE,
        "horno": max(cap_horno_base + cfg.get("dh", 0), 1),
    }
    tam_l = {
        p: max(int(t * cfg.get("fl", 1.0)), 1)
        for p, t in TAMANO_LOTE_BASE.items()
    }

    df_l, df_u, _ = run_simulacion(plan_aj, cap_rec, cfg["falla"], cfg["ft"], tam_l)

    return {
        "kpis": calc_kpis(df_l, plan_aj),
        "util": calc_utilizacion(df_u),
    }


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Ejecutando pipeline completo (febrero, demanda normal)...")
    res = run_pipeline(mes_idx=1)

    print(f"\nMes: {res['mes_nombre']}")
    print(f"Costo agregado: COP ${res['costo_agregado']:,.0f}")
    print(f"Lotes simulados: {len(res['df_lotes'])}")

    print("\nPlan del mes:")
    for p, u in res["plan_mes"].items():
        print(f"  {p:<22}: {u:,} und")

    print("\nKPIs principales:")
    cols = ["Producto", "Und Producidas", "Throughput (und/h)", "Cumplimiento %"]
    print(res["df_kpis"][cols].to_string(index=False))

    print("\nCuellos de botella detectados:")
    cb = res["df_utilizacion"][res["df_utilizacion"]["Cuello Botella"]]
    if cb.empty:
        print("  Ninguno")
    else:
        print(cb[["Recurso", "Utilización_%", "Cola Prom"]].to_string(index=False))
