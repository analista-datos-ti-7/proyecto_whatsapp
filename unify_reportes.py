from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd

OUTPUT_DIR = Path("./output/reportes")


@dataclass
class TipoReporte:
    """Configuración de cada tipo de archivo a unificar."""
    nombre: str
    patron: re.Pattern          # regex con dos grupos de fecha (desde, hasta)
    sep_fecha: str              # separador dentro de la fecha ("-" o "_")
    glob: str                   # patrón para buscar archivos de entrada
    base_salida: str            # nombre base de los archivos unificados
    cols_dedup_orden: tuple[str, ...] = ()   # para elegir qué fila conservar al deduplicar
    cols_orden_final: tuple[str, ...] = ()    # para ordenar la salida final


TIPOS: list[TipoReporte] = [
    TipoReporte(
        nombre="reporte",
        patron=re.compile(r"reporte_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.parquet$"),
        sep_fecha="-",
        glob="reporte_*.parquet",
        base_salida="reporte_unificado",
        cols_dedup_orden=("total_mensajes", "fecha_calculo"),
        cols_orden_final=("primera_interaccion_cliente",),
    ),
    TipoReporte(
        nombre="casos",
        # casos_YYYY_MM_DD_YYYY_MM_DD.parquet  (fecha inicio _ fecha fin)
        patron=re.compile(r"casos_(\d{4}_\d{2}_\d{2})_(\d{4}_\d{2}_\d{2})\.parquet$"),
        sep_fecha="_",
        glob="casos_*.parquet",
        base_salida="casos_unificado",
        cols_dedup_orden=(),                  # casos no trae total_mensajes/fecha_calculo
        cols_orden_final=("fecha",),
    ),
]


def _a_fecha(texto: str, sep: str) -> date:
    """Convierte 'YYYY-MM-DD' o 'YYYY_MM_DD' a date."""
    return date.fromisoformat(texto.replace(sep, "-"))


def _ventana(path: Path, tipo: TipoReporte) -> tuple[date, date] | None:
    """Extrae (desde, hasta) del nombre del archivo según el tipo."""
    m = tipo.patron.search(path.name)
    if not m:
        return None
    return _a_fecha(m.group(1), tipo.sep_fecha), _a_fecha(m.group(2), tipo.sep_fecha)


def candidatos(tipo: TipoReporte) -> list[Path]:
    return sorted(
        p for p in OUTPUT_DIR.glob(tipo.glob)
        if not p.name.startswith(tipo.base_salida)
    )


def _seleccionar(
    tipo: TipoReporte,
    desde: date | None,
    hasta: date | None,
    todos: bool,
    archivos: list[str],
) -> list[Path]:
    if archivos:
        # Solo los archivos cuyo nombre corresponda a ESTE tipo.
        rutas = [Path(a) for a in archivos if tipo.patron.search(Path(a).name)]
        faltan = [str(r) for r in rutas if not r.exists()]
        if faltan:
            print("ERROR, no existen:", ", ".join(faltan))
            sys.exit(1)
        return rutas
    if todos:
        return candidatos(tipo)
    elegidos = []
    for p in candidatos(tipo):
        v = _ventana(p, tipo)
        if v and v[0] >= desde and v[1] <= hasta:
            elegidos.append(p)
    return elegidos


def unificar(tipo: TipoReporte, paths: list[Path], dedup: bool = True) -> tuple[Path, Path]:
    dfs = []
    for p in paths:
        df = pd.read_parquet(p)
        dfs.append(df)
        print(f"  incluyo: {p.name} ({len(df)} filas)")

    unido = pd.concat(dfs, ignore_index=True)
    antes = len(unido)

    if dedup and "nro_caso" in unido.columns:
        por = [c for c in tipo.cols_dedup_orden if c in unido.columns]
        if por:
            unido = unido.sort_values(por, ascending=[False] * len(por))
        unido = unido.drop_duplicates(subset="nro_caso", keep="first")
        duplicados = antes - len(unido)
        if duplicados:
            print(f"  deduplicados por nro_caso: {duplicados}")

    orden = [c for c in tipo.cols_orden_final if c in unido.columns]
    if orden:
        unido = unido.sort_values(orden)

    path_parquet = OUTPUT_DIR / f"{tipo.base_salida}.parquet"
    path_csv = OUTPUT_DIR / f"{tipo.base_salida}.csv"
    unido.to_parquet(path_parquet, index=False)
    unido.to_csv(path_csv, index=False, encoding="utf-8-sig")
    print(f"  OK {len(unido)} filas -> {path_parquet}")
    print(f"  OK {len(unido)} filas -> {path_csv}")
    return path_parquet, path_csv


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Unifica reportes y/o casos en una sola tabla (parquet + CSV)."
    )
    ap.add_argument("--desde", type=str, help="YYYY-MM-DD (inicio del rango)")
    ap.add_argument("--hasta", type=str, help="YYYY-MM-DD (fin del rango)")
    ap.add_argument("--todos", action="store_true", help="Unificar todos los archivos de output/")
    ap.add_argument("--archivos", nargs="+", help="Rutas puntuales a unificar")
    ap.add_argument("--sin-dedup", action="store_true", help="No deduplicar por nro_caso")
    ap.add_argument(
        "--tipo",
        choices=["reporte", "casos", "ambos"],
        default="ambos",
        help="Qué unificar (por defecto: ambos)",
    )
    args = ap.parse_args()

    if args.archivos or args.todos:
        desde = hasta = None
    elif args.desde and args.hasta:
        desde = datetime.strptime(args.desde, "%Y-%m-%d").date()
        hasta = datetime.strptime(args.hasta, "%Y-%m-%d").date()
        if desde > hasta:
            print("ERROR: --desde no puede ser posterior a --hasta")
            sys.exit(1)
    else:
        print("Indica --desde y --hasta, o --todos, o --archivos. Ver --help.")
        sys.exit(1)

    tipos = TIPOS if args.tipo == "ambos" else [t for t in TIPOS if t.nombre == args.tipo]

    algo = False
    for tipo in tipos:
        paths = _seleccionar(tipo, desde, hasta, args.todos, args.archivos or [])
        if not paths:
            print(f"[{tipo.nombre}] sin archivos que cumplan el criterio en {OUTPUT_DIR}")
            continue
        print(f"[{tipo.nombre}] {len(paths)} archivo(s):")
        if len(paths) == 1:
            print("  aviso: solo hay uno; la salida será una copia unificada de ese archivo.")
        unificar(tipo, paths, dedup=not args.sin_dedup)
        algo = True

    if not algo:
        print("No se generó ninguna salida.")
        sys.exit(1)


if __name__ == "__main__":
    main()