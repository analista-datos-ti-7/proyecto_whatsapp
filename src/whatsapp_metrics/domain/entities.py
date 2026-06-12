from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Direccionamiento(str, Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


@dataclass(frozen=True, slots=True)
class Interaccion:
    nro_caso: int
    fecha_creacion: datetime
    direccionamiento: Direccionamiento
    usuario: str | None
    canal: str | None
    campania: str | None
    contenido: str | None

    @property
    def es_inbound(self) -> bool:
        return self.direccionamiento == Direccionamiento.INBOUND

    @property
    def es_outbound(self) -> bool:
        return self.direccionamiento == Direccionamiento.OUTBOUND


@dataclass(frozen=True, slots=True)
class MetricasCaso:
    nro_caso: int
    primera_interaccion_cliente: datetime
    primera_interaccion_bot: datetime | None
    primera_interaccion_humano: datetime | None
    ultima_interaccion: datetime
    ftr_bot_min: float | None
    tfr_human_min: float | None
    tiempo_promedio_de_interaccion_min: float
    canal_primera_interaccion: str | None
    campania: str | None
    total_mensajes: int
    mensajes_cliente: int
    mensajes_bot: int
    mensajes_humano: int
    mensajes_multimedia: int
    atendido_por_humano: bool
    cumple_min_mensajes: bool
    es_venta: bool
    fecha_calculo: datetime
    tiempo_promedio_entre_mensajes_min: float | None = None
    icc_score: int | None = None
    agente: str | None = None
    tuvo_bot: bool = True


@dataclass(slots=True)
class ResultadoCaso:
    nro_caso: int
    metricas: MetricasCaso | None
    categorias: list[str] = field(default_factory=list)
    duplicados_eliminados: int = 0
    fecha_caso: datetime | None = None