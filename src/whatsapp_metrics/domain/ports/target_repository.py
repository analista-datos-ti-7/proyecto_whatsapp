from __future__ import annotations
from datetime import date
from typing import Iterable, Iterator, Protocol
from src.whatsapp_metrics.domain.entities import Interaccion, MetricasCaso

class TargetRepository(Protocol):

    def guardar_raw(
            self,
            interacciones: Iterable[Interaccion],
            fecha_desde: date,
            fecha_hasta: date,
    ) -> dict:
        ...

    def guardar_metricas(
            self,
            metricas: Iterable[MetricasCaso],
            fecha_desde: date,
            fecha_hasta: date,
    ) -> dict:
        ...

    def iter_casos_raw(
            self,
            fecha_desde: date,
            fecha_hasta: date,
    ) -> Iterable[list[Interaccion]]:
        ...