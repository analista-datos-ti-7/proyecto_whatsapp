from __future__ import annotations

import logging
from datetime import date

from src.whatsapp_metrics.domain.metrics_calculator import analizar_caso
from src.whatsapp_metrics.domain.ports import TargetRepository

logger = logging.getLogger(__name__)

NOMBRES_AUDITORIA: dict[str, str] = {
    "duplicados":           "casos_duplicados",
    "llamada":              "casos_llamadas",
    "con_llamada":          "casos_con_llamada",
    "solo_inbound":         "casos_solo_inbound",
    "solo_outbound":        "casos_solo_outbound",
    "mensaje_repetido":     "casos_mensaje_repetido",
    "fechas_incoherentes":  "casos_fechas_incoherentes",
    "colaborador":          "casos_colaborador",
    "sin_atencion_humana":  "casos_sin_atencion_humana",
    "sin_bot":              "casos_sin_bot",          
    "extraordinario":       "casos_extraordinarios",
    "sin_palabras_venta":   "casos_sin_palabras_venta",
    "vacio":                "casos_vacios",
}


class ComputeMetricsFromLocal:
    def __init__(self, target: TargetRepository) -> None:
        self._target = target

    def execute(self, fecha_desde: date, fecha_hasta: date) -> dict:
        logger.info("Calculando métricas: %s a %s ", fecha_desde, fecha_hasta)

        metricas = []
        auditoria: dict[str, list[dict]] = {n: [] for n in NOMBRES_AUDITORIA.values()}
        registros_duplicados = 0
        casos_descartados = 0

        for grupo_caso in self._target.iter_casos_raw(fecha_desde, fecha_hasta):
            r = analizar_caso(grupo_caso)
            if r is None:
                continue

            campania_caso = grupo_caso[0].campania if grupo_caso else None
            canal_caso = grupo_caso[0].canal if grupo_caso else None

            for cat in r.categorias:
                seccion = NOMBRES_AUDITORIA.get(cat)
                if seccion:
                    auditoria[seccion].append({
                        "nro_caso": r.nro_caso,
                        "fecha": (r.fecha_caso.strftime("%Y-%m-%d %H:%M")
                                  if r.fecha_caso else ""),
                        "campania": campania_caso,      # NUEVO
                        "canal": canal_caso,            # NUEVO
                    })
            registros_duplicados += r.duplicados_eliminados

            if r.metricas is None:
                casos_descartados += 1
            else:
                metricas.append(r.metricas)

        # guardar métricas
        resultado_guardado = self._target.guardar_metricas(
            metricas, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta,
        )

        # guardar auditoría
        rutas_auditoria: dict = {}
        if hasattr(self._target, "guardar_auditoria"):
            rutas_auditoria = self._target.guardar_auditoria(
                auditoria, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta,
            )

        resumen = {
            "fecha_desde": str(fecha_desde),
            "fecha_hasta": str(fecha_hasta),
            "metricas_calculadas": len(metricas),
            "casos_descartados": casos_descartados,
            "registros_duplicados_eliminados": registros_duplicados,
            **{seccion: len(casos) for seccion, casos in auditoria.items()},
            **resultado_guardado,
            **rutas_auditoria,
        }
        logger.info("Cálculo terminado: %s ", resumen)
        return resumen