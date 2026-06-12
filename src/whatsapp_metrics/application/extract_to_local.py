from __future__ import annotations
import logging
from datetime import date
from src.whatsapp_metrics.domain.ports import SourceRepository, TargetRepository

logger = logging.getLogger(__name__)

class ExtractToLocal:
    def __init__(
            self,
            source: SourceRepository,
            target: TargetRepository,
            batch_size: int = 5000,
    ) -> None:
        self._source = source
        self._target = target
        self._batch_size = batch_size

    def execute(self, fecha_desde: date, fecha_hasta: date) -> dict:
        logger.info("Extrayendo a local: %s a %s", fecha_desde, fecha_hasta)

        total_estimado = self._source.contar_interacciones(fecha_desde,fecha_hasta)    
        logger.info("Filas estimadas: %s", total_estimado)

        resultado = self._target.guardar_raw(
            self._source.iter_interacciones_por_fecha(
                fecha_desde = fecha_desde,
                fecha_hasta = fecha_hasta,
                batch_size = self._batch_size,
            ),
            fecha_desde = fecha_desde,
            fecha_hasta = fecha_hasta,
        )

        resumen = {
            "fecha_desde": str(fecha_desde),
            "fecha_hasta": str(fecha_hasta),
            "estimado_origen": total_estimado,
            **resultado,
        }
        logger.info("Extración terminada: %s", resumen)
        return resumen