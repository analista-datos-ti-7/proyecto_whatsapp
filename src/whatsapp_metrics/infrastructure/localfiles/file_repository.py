from __future__ import annotations
import csv
import logging
from datetime import date
from pathlib import Path
from typing import Iterable
import json
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from src.whatsapp_metrics.domain.entities import Direccionamiento, Interaccion, MetricasCaso


logger = logging.getLogger(__name__)


RAW_SCHEMA = pa.schema([
    ("nro_caso", pa.int64()),
    ("fecha_creacion", pa.timestamp("ms")),
    ("direccionamiento", pa.string()),
    ("usuario", pa.string()),
    ("canal", pa.string()),
    ("campania", pa.string()),
    ("contenido", pa.string()),
])


RAW_CSV_COLUMNS = [
    "nro_caso", "fecha_creacion", "direccionamiento",
    "usuario", "canal", "campania", "contenido",
]


METRICAS_CSV_COLUMNS = [
    "nro_caso",
    "primera_interaccion_cliente",
    "primera_interaccion_bot",
    "primera_interaccion_humano",
    "ultima_interaccion",
    "ftr_bot_min",
    "tfr_human_min",
    "tiempo_promedio_de_interaccion_min",
    "canal_primera_interaccion",
    "campania",
    "total_mensajes",
    "mensajes_cliente",
    "mensajes_bot",
    "mensajes_humano",
    "mensajes_multimedia",
    "atendido_por_humano",
    "cumple_min_mensajes",
    "es_venta",
    "fecha_calculo",
    "tiempo_promedio_entre_mensajes_min",  
    "icc_score",                           
    "agente",                             
    "tuvo_bot", 
]


class LocalFileRepository:

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._dir_raw = self._output_dir / "raw"
        self._dir_metricas = self._output_dir / "metricas"
        self._dir_auditoria = self._output_dir / "auditoria"
        for d in (self._dir_raw, self._dir_metricas, self._dir_auditoria):
            d.mkdir(parents=True, exist_ok=True)

    def _paths_raw(self, d_desde: date, d_hasta: date) -> tuple[Path, Path]:
        base = f"raw_{d_desde.isoformat()}_{d_hasta.isoformat()}"
        return (
            self._dir_raw / f"{base}.parquet",
            self._dir_raw / f"{base}.csv",
        )

    def _paths_metricas(self, d_desde: date, d_hasta: date) -> tuple[Path, Path]:
        base = f"metricas_{d_desde.isoformat()}_{d_hasta.isoformat()}"
        return (
            self._dir_metricas / f"{base}.parquet",
            self._dir_metricas / f"{base}.csv",
        )

    def guardar_raw(
        self,
        interacciones: Iterable[Interaccion],
        fecha_desde: date,
        fecha_hasta: date,
    ) -> dict:
        path_parquet, path_csv = self._paths_raw(fecha_desde, fecha_hasta)

        for p in (path_parquet, path_csv):
            if p.exists():
                p.unlink()

        total = 0
        batch_idx = 0

        with pq.ParquetWriter(path_parquet, RAW_SCHEMA) as writer, \
             path_csv.open("w", encoding="utf-8-sig", newline="") as f_csv:

            csv_writer = csv.writer(f_csv)
            csv_writer.writerow(RAW_CSV_COLUMNS)

            for batch in interacciones:
                if not batch:
                    continue
                batch_idx += 1

                arrays = self._batch_to_arrays(batch)
                table = pa.table(arrays, schema=RAW_SCHEMA)
                writer.write_table(table)
                for i in batch:
                    csv_writer.writerow([
                        i.nro_caso,
                        i.fecha_creacion.isoformat(sep=" "),
                        i.direccionamiento.value,
                        i.usuario or "",
                        i.canal or "",
                        i.campania or "",
                        (i.contenido or "").replace("\n", " ").replace("\r", " "),
                    ])

                total += len(batch)
                logger.info("Raw batch %s escrito: %s filas (acumulado %s)",
                            batch_idx, len(batch), total)

        logger.info("RAW guardado: %s filas -> %s y %s", total, path_parquet, path_csv)
        return {
            "total_filas": total,
            "parquet": str(path_parquet),
            "csv": str(path_csv),
        }

    @staticmethod
    def _batch_to_arrays(batch: list[Interaccion]) -> dict:
        return {
            "nro_caso": [i.nro_caso for i in batch],
            "fecha_creacion": [i.fecha_creacion for i in batch],
            "direccionamiento": [i.direccionamiento.value for i in batch],
            "usuario": [i.usuario for i in batch],
            "canal": [i.canal for i in batch],
            "campania": [i.campania for i in batch],
            "contenido": [i.contenido for i in batch],
        }

    def guardar_metricas(
        self,
        metricas: Iterable[MetricasCaso],
        fecha_desde: date,
        fecha_hasta: date,
    ) -> dict:
        path_parquet, path_csv = self._paths_metricas(fecha_desde, fecha_hasta)
        lista = list(metricas)

        if not lista:
            logger.warning("No hay métricas para guardar.")
            return {"total_filas": 0, "parquet": str(path_parquet), "csv": str(path_csv)}

        df = pd.DataFrame([self._metrica_to_dict(m) for m in lista])
        df = df[METRICAS_CSV_COLUMNS]

        df.to_parquet(path_parquet, index=False)
        df.to_csv(path_csv, index=False, encoding="utf-8-sig")

        logger.info("Metricas guardadas: %s filas -> %s y %s",
                    len(df), path_parquet, path_csv)
        return {
            "total_filas": len(df),
            "parquet": str(path_parquet),
            "csv": str(path_csv),
        }

    @staticmethod
    def _metrica_to_dict(m: MetricasCaso) -> dict:
        return {
            "nro_caso": m.nro_caso,
            "primera_interaccion_cliente": m.primera_interaccion_cliente,
            "primera_interaccion_bot": m.primera_interaccion_bot,
            "primera_interaccion_humano": m.primera_interaccion_humano,
            "ultima_interaccion": m.ultima_interaccion,
            "ftr_bot_min": m.ftr_bot_min,
            "tfr_human_min": m.tfr_human_min,
            "tiempo_promedio_de_interaccion_min": m.tiempo_promedio_de_interaccion_min,
            "canal_primera_interaccion": m.canal_primera_interaccion,
            "campania": m.campania,
            "total_mensajes": m.total_mensajes,
            "mensajes_cliente": m.mensajes_cliente,
            "mensajes_bot": m.mensajes_bot,
            "mensajes_humano": m.mensajes_humano,
            "mensajes_multimedia": m.mensajes_multimedia,
            "atendido_por_humano": m.atendido_por_humano,
            "cumple_min_mensajes": m.cumple_min_mensajes,
            "es_venta": m.es_venta,
            "fecha_calculo": m.fecha_calculo,
            "tiempo_promedio_entre_mensajes_min": m.tiempo_promedio_entre_mensajes_min,  
            "icc_score": m.icc_score,                                                    
            "agente": m.agente,                                                         
            "tuvo_bot": m.tuvo_bot,   
        }

    @staticmethod
    def _caso_a_fila(c, cat: str) -> dict:
        if isinstance(c, dict):
            return {"nro_caso": c.get("nro_caso"),
                    "fecha": c.get("fecha", ""),
                    "categoria": cat}
        return {"nro_caso": c, "fecha": "", "categoria": cat}

    def guardar_auditoria(self, auditoria: dict, fecha_desde: date,
                          fecha_hasta: date) -> dict:
        base = f"auditoria_{fecha_desde.isoformat()}_{fecha_hasta.isoformat()}"
        path_json = self._dir_auditoria / f"{base}.json"
        path_csv = self._dir_auditoria / f"{base}.csv"
        with open(path_json, "w", encoding="utf-8") as f:
            json.dump(auditoria, f, ensure_ascii=False, indent=2)
        filas = [self._caso_a_fila(c, cat)
                 for cat, casos in auditoria.items() for c in casos]
        pd.DataFrame(filas, columns=["nro_caso", "fecha", "categoria"]).to_csv(
            path_csv, index=False, encoding="utf-8-sig")
        logger.info("Auditoria guardada: %s", path_json)

        rutas = {"auditoria_json": str(path_json), "auditoria_csv": str(path_csv)}
        try:
            from auditoria_excel import actualizar_auditoria_general

            path_general = actualizar_auditoria_general(
                auditoria, fecha_desde, fecha_hasta, output_dir=self._dir_auditoria
            )
            if path_general:
                rutas["auditoria_general"] = str(path_general)
                logger.info("Auditoria general actualizada: %s", path_general)
            else:
                logger.warning(
                    "auditoria_general.xlsx está abierto en Excel; el JSON quedó "
                    "actualizado. Regenera con: python auditoria_excel.py --general")
        except ImportError:
            logger.warning("openpyxl no instalado; auditoría solo en JSON/CSV")
        except Exception as e:
            logger.warning(
                "No se pudo generar el Excel general (%s). El JSON maestro quedó "
                "actualizado; regenera con: python auditoria_excel.py --general", e)
        return rutas

    def iter_casos_raw(
        self,
        fecha_desde: date,
        fecha_hasta: date,
    ) -> Iterable[list[Interaccion]]:
        path_parquet, _ = self._paths_raw(fecha_desde, fecha_hasta)
        if not path_parquet.exists():
            raise FileNotFoundError(
                f"No existe el RAW para el rango {fecha_desde}..{fecha_hasta}: "
                f"{path_parquet}. Corre primero el extract."
            )

        parquet_file = pq.ParquetFile(path_parquet)
        casos_pendientes: dict[int, list[Interaccion]] = {}

        for batch_idx in range(parquet_file.num_row_groups):
            tabla = parquet_file.read_row_group(batch_idx)
            df = tabla.to_pandas()
            df = df.sort_values(["nro_caso", "fecha_creacion"])

            for _, fila in df.iterrows():
                inter = self._row_to_interaccion(fila)
                if inter is None:
                    continue
                casos_pendientes.setdefault(inter.nro_caso, []).append(inter)

        for nro_caso in sorted(casos_pendientes.keys()):
            grupo = sorted(
                casos_pendientes[nro_caso],
                key=lambda i: i.fecha_creacion,
            )
            yield grupo

    @staticmethod
    def _row_to_interaccion(fila) -> Interaccion | None:
        try:
            direc = str(fila["direccionamiento"]).strip().upper()
            if direc not in ("INBOUND", "OUTBOUND"):
                return None
            return Interaccion(
                nro_caso=int(fila["nro_caso"]),
                fecha_creacion=pd.to_datetime(fila["fecha_creacion"]).to_pydatetime(),
                direccionamiento=Direccionamiento(direc),
                usuario=(fila["usuario"] if pd.notna(fila["usuario"]) else None),
                canal=(fila["canal"] if pd.notna(fila["canal"]) else None),
                campania=(fila["campania"] if pd.notna(fila["campania"]) else None),
                contenido=(fila["contenido"] if pd.notna(fila["contenido"]) else None),
            )
        except Exception as e:
            logger.warning("Fila inválida en parquet: %s", e)
            return None