from __future__ import annotations

import logging
import sys
from datetime import date, timedelta
from pathlib import Path
import click
from config.container import Container
from config.settings import Settings

def _setup_logging(log_dir: Path, level:str) -> None:
    log_dir.mkdir(parents = True, exist_ok = True)
    fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    log_file = log_dir / f"etl_{date.today().isoformat()}.log"
    logging.basicConfig(
        level = getattr(logging, level.upper(), logging.INFO),
        format = fmt,
        handlers =[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

@click.command()
@click.option("--fecha", type = click.DateTime(formats = ["%Y-%m-%d"]), default = None, help = "Fecha única (YYYY-MM-DD) Default: ayer")
@click.option("--desde", type = click.DateTime(formats = ["%Y-%m-%d"]), default = None)
@click.option("--hasta", type = click.DateTime(formats = ["%Y-%m-%d"]), default = None)
@click.option("--solo-extract", is_flag = True, help = "Solo descargar a local")
@click.option("--solo-metricas", is_flag = True, help = "Solo recalcular desde raw local")
@click.option("--probar-conexion", is_flag = True, help = "Prueba 1 SELECT en SQL Server y termina")

def main(
    fecha: object | None,
    desde: object | None,
    hasta: object | None,
    solo_extract: bool,
    solo_metricas: bool,
    probar_conexion: bool,
) -> None:
    settings = Settings()
    _setup_logging(settings.etl.log_dir, settings.etl.log_level)
    log = logging.getLogger("etl_runner")
    container = Container(settings)

    # Se prueba la conexión y sale
    if probar_conexion:
        log.info("Probando conexión a SQL", settings.sqlserver.host)
        if container.source.probar_conexion():
            click.echo("Conexión OK")
            sys.exit(0)
        else:
            click.echo("No se pudo conectar")
            sys.exit(1)

    # Resolver el rango de fechas
    if fecha is not None:
        fecha_desde = fecha_hasta = fecha.date()
    elif desde is not None and hasta is not None:
        fecha_desde = desde.date()
        fecha_hasta = hasta.date()
    elif desde is None and hasta is None:
        fecha_desde = fecha_hasta = date.today() - timedelta(days=1) 
    else:
        click.echo("Error en las fechas, usa --desde y --hasta")
        sys.exit(2)
    
    if fecha_desde > fecha_hasta:
        click.echo("La fecha --desde no puede ser posterior a --hasta")
        sys.exit(2)

    if solo_extract and solo_metricas:
        click.echo("Error en extracción y métricas al ser excluyentes")
        sys.exit(2)

    log.info("Iniciando ETL %s a %s | solo_extract = %s | solo_metricas = %s", fecha_desde, fecha_hasta, solo_extract, solo_metricas)

    # Fase de extracción
    if not solo_metricas:
        from src.whatsapp_metrics.application.extract_to_local import ExtractToLocal
        uc_extract = ExtractToLocal(
            source = container.source,
            target = container.target,
            batch_size = settings.etl.batch_size,
        )
        resumen = uc_extract.execute(fecha_desde, fecha_hasta)
        log.info("Resumen extracción: %s", resumen)
    
    #Fase de métricas
    if not solo_extract:
        from src.whatsapp_metrics.application.compute_metrics_from_local import (ComputeMetricsFromLocal,)
        uc_metricas = ComputeMetricsFromLocal(target = container.target)
        resumen = uc_metricas.execute(fecha_desde, fecha_hasta)
        log.info("Resumen métricas: %s", resumen)

    log.info("ETL terminado correctamente")

if __name__ == "__main__":
    main()