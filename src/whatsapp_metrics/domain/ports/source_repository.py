from __future__ import annotations
from datetime import date
from typing import Iterable, Iterator, Protocol
from src.whatsapp_metrics.domain.entities import Interaccion, MetricasCaso

class SourceRepository(Protocol):
    
    def iter_interacciones_por_fecha(
            self,
            fecha_desde: date,
            fecha_hasta: date,
            batch_size: int
    ) -> Iterator[list[Interaccion]]:
        ...

    def contar_interacciones(self, fecha_desde: date, fecha_hasta: date) -> int:
        ...

    def probar_conexion(self) -> bool:
        ...
