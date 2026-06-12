from __future__ import annotations
import logging
from datetime import date, datetime
from typing import Iterator
import pyodbc
from tenacity import ( 
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from config.settings import SqlServerSettings
from src.whatsapp_metrics.domain.entities import Direccionamiento, Interaccion

logger = logging.getLogger(__name__)

COLUMNAS = [
    "id",
    "nro_caso",
    "fecha_creacion",
    "direccionamiento",
    "usuario",
    "canal",
    "campania",
    "contenido",
]
COLUMNAS_SQL = ", ".join(COLUMNAS)


class SagiccRepository:

    def __init__(self, settings: SqlServerSettings) -> None:
        self._settings = settings

    def probar_conexion(self) -> bool:
        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1")
                row = cur.fetchone()
                return row is not None and row[0] == 1
        except Exception as e:
            logger.error("Fallo prueba de conexión: %s", e)
            return False

    def contar_interacciones(self, fecha_desde: date, fecha_hasta: date) -> int:
        sql = f"""
        SELECT COUNT_BIG(*) AS total
        FROM Sagicc.dbo.reporte_llamada_entra_sal WITH (NOLOCK)
        WHERE fecha_creacion >= ?
          AND fecha_creacion < DATEADD(DAY, 1, ?)
        """
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, fecha_desde, fecha_hasta)
            row = cur.fetchone()
            total = int(row[0]) if row else 0
            logger.info(
                "Conteo previo: %s filas entre %s y %s",
                total, fecha_desde, fecha_hasta,
            )
            return total

    def iter_interacciones_por_fecha(
        self,
        fecha_desde: date,
        fecha_hasta: date,
        batch_size: int,
    ) -> Iterator[list[Interaccion]]:
        ultimo_id: int = 0
        nro_batch = 0

        while True:
            rows = self._fetch_batch(
                fecha_desde=fecha_desde,
                fecha_hasta=fecha_hasta,
                ultimo_id=ultimo_id,
                batch_size=batch_size,
            )
            if not rows:
                logger.info("Fin de extracción. Batches: %s", nro_batch)
                break

            nro_batch += 1
            logger.info("Batch %s: %s filas (id > %s)", nro_batch, len(rows), ultimo_id)

            ultimo_id = rows[-1][0]  

            interacciones = [
                inter for row in rows
                if (inter := self._row_to_interaccion(row)) is not None
            ]
            yield interacciones

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type((pyodbc.OperationalError, pyodbc.InterfaceError)),
        reraise=True,
    )
    def _fetch_batch(
        self,
        fecha_desde: date,
        fecha_hasta: date,
        ultimo_id: int,
        batch_size: int,
    ) -> list[tuple]:
        sql = f"""
        SELECT TOP (?) {COLUMNAS_SQL}
        FROM Sagicc.dbo.reporte_llamada_entra_sal WITH (NOLOCK)
        WHERE id > ?
          AND fecha_creacion >= ?
          AND fecha_creacion < DATEADD(DAY, 1, ?)
        ORDER BY id ASC
        """
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, batch_size, ultimo_id, fecha_desde, fecha_hasta)
            return cur.fetchall()

    def _connect(self) -> pyodbc.Connection:
        conn = pyodbc.connect(
            self._settings.odbc_connection_string(),
            readonly=True,
            timeout=30,
        )
        cur = conn.cursor()
        cur.execute("SET LOCK_TIMEOUT 5000")  # 5s máx esperando lock
        cur.close()
        return conn

    @staticmethod
    def _row_to_interaccion(row: tuple) -> Interaccion | None:
        try:
            (_id, nro_caso, fecha_creacion, direccionamiento,
             usuario, canal, campania, contenido) = row

            if nro_caso is None or fecha_creacion is None:
                return None

            direc_str = (direccionamiento or "").strip().upper()
            if direc_str not in ("INBOUND", "OUTBOUND"):
                return None

            return Interaccion(
                nro_caso=int(nro_caso),
                fecha_creacion=(
                    fecha_creacion if isinstance(fecha_creacion, datetime)
                    else datetime.fromisoformat(str(fecha_creacion))
                ),
                direccionamiento=Direccionamiento(direc_str),
                usuario=usuario.strip() if usuario else None,
                canal=canal.strip() if canal else None,
                campania=campania.strip() if campania else None,
                contenido=(str(contenido)[:4000] if contenido is not None else None),
            )
        except Exception as e:
            logger.warning("Fila inválida descartada: %s", e)
            return None