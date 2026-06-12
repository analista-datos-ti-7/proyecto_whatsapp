from __future__ import annotations
import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

OUTPUT_DIR = Path("./output")
DIR_METRICAS = OUTPUT_DIR / "metricas"
DIR_REPORTES = OUTPUT_DIR / "reportes"
DIR_AUDITORIA = OUTPUT_DIR / "auditoria"


SECCIONES_NO_ATENDIDA: tuple[str, ...] = (
    "casos_sin_atencion_humana",
    "casos_solo_inbound",
    "casos_mensaje_repetido",
)


def _rango_horario_2h(dt) -> str | None:
    if pd.isna(dt):
        return None
    bloque = (dt.hour // 2) * 2
    fin = (bloque + 2) % 24
    return f"{bloque:02d}:00 - {fin:02d}:00"


def _hora_fraccion(dt) -> float | None:
    if pd.isna(dt):
        return None
    seg = dt.hour * 3600 + dt.minute * 60 + dt.second
    return seg / 86400.0


def _hora_minuto(dt) -> int | None:
    if pd.isna(dt):
        return None
    return dt.hour * 60 + dt.minute


def _rango_hora_atencion(dt) -> str | None:
    if pd.isna(dt):
        return None
    total = dt.hour * 60 + dt.minute + dt.second / 60.0
    redondeado = (int(round(total / 15.0)) * 15) % (24 * 60)  
    h, m = divmod(redondeado, 60)
    return f"{h:02d}:{m:02d}"


def _tfr_rango(v) -> str | None:
    if v is None or pd.isna(v):
        return None
    if v <= 1:
        return "0 a 1"
    if v <= 5:
        return "1 a 5"
    if v <= 10:
        return "5 a 10"
    return "> 10"


_ORDEN_RANGO = {"0 a 1": 1, "1 a 5": 2, "5 a 10": 3, "> 10": 4}


def _clasif_tiempo_entre(v) -> str | None:
    if v is None or pd.isna(v):
        return None
    if v <= 2:
        return "Conversación verbal (0-2 min)"
    if v <= 5:
        return "Fluida (3-5 min)"
    if v <= 10:
        return "Riesgo comercial (6-10 min)"
    return "Conversación fría (>10 min)"


_ORDEN_CLASIF = {
    "Conversación verbal (0-2 min)": 1,
    "Fluida (3-5 min)": 2,
    "Riesgo comercial (6-10 min)": 3,
    "Conversación fría (>10 min)": 4,
}


def _construir_casos(df_metricas: pd.DataFrame, fecha_desde: date,
                     fecha_hasta: date) -> tuple[Path, Path] | None:
    cols = ["nro_caso", "fecha", "campania", "canal", "atendido",
            "categoria_no_atendida"]

    atend = pd.DataFrame({
        "nro_caso": df_metricas["nro_caso"],
        "fecha": pd.to_datetime(df_metricas["primera_interaccion_cliente"]),
        "campania": df_metricas["campania"],
        "canal": df_metricas["canal_primera_interaccion"],
        "atendido": True,
        "categoria_no_atendida": None,
    })

    filas_no: list[dict] = []
    ruta_json = (DIR_AUDITORIA /
                 f"auditoria_{fecha_desde.isoformat()}_{fecha_hasta.isoformat()}.json")
    if ruta_json.exists():
        aud = json.loads(ruta_json.read_text(encoding="utf-8"))
        vistos: set = set()
        for seccion in SECCIONES_NO_ATENDIDA:
            for c in aud.get(seccion, []):
                if isinstance(c, dict):
                    nro = c.get("nro_caso")
                    fch = c.get("fecha", "")
                    camp = c.get("campania")
                    can = c.get("canal")
                else:
                    nro, fch, camp, can = c, "", None, None
                if nro in vistos:          
                    continue
                vistos.add(nro)
                filas_no.append({
                    "nro_caso": nro,
                    "fecha": pd.to_datetime(fch, errors="coerce") if fch else pd.NaT,
                    "campania": camp,
                    "canal": can,
                    "atendido": False,
                    "categoria_no_atendida": seccion,
                })

    no_atend = (pd.DataFrame(filas_no, columns=cols) if filas_no
                else pd.DataFrame(columns=cols))

    casos = pd.concat([atend[cols], no_atend[cols]], ignore_index=True)
    casos["fecha"] = pd.to_datetime(casos["fecha"], errors="coerce")
    casos["Rango Horario (2h)"] = casos["fecha"].apply(_rango_horario_2h)
    casos["campania"] = casos["campania"].fillna("(sin campaña)")
    casos["canal"] = casos["canal"].fillna("(sin canal)")

    base = f"casos_{fecha_desde.isoformat()}_{fecha_hasta.isoformat()}"
    DIR_REPORTES.mkdir(parents=True, exist_ok=True)
    p_parquet = DIR_REPORTES / f"{base}.parquet"
    p_csv = DIR_REPORTES / f"{base}.csv"
    casos.to_parquet(p_parquet, index=False)
    casos.to_csv(p_csv, index=False, encoding="utf-8-sig")
    return p_parquet, p_csv


def build_report(fecha_desde: date, fecha_hasta: date) -> Path:
    base = f"metricas_{fecha_desde.isoformat()}_{fecha_hasta.isoformat()}"
    path_metricas = DIR_METRICAS / f"{base}.parquet"
    if not path_metricas.exists():
        raise FileNotFoundError(
            f"No existe {path_metricas}. Corre primero el --solo-extract y --solo-metricas."
        )

    df = pd.read_parquet(path_metricas)
    pi = pd.to_datetime(df["primera_interaccion_cliente"])

    df["primera_interaccion - format"] = pi.dt.strftime("%d/%m/%Y")
    df["Rango Horario (2h)"] = pi.apply(_rango_horario_2h)
    df["primera_interaccion_hora"] = pi.apply(_hora_fraccion)
    df["rangos_hora_atencion"] = pi.apply(_rango_hora_atencion)
    df["HoraMinuto"] = pi.apply(_hora_minuto)
    df["tfr_human_rango"] = df["tfr_human_min"].apply(_tfr_rango)
    df["Orden_rango"] = df["tfr_human_rango"].map(_ORDEN_RANGO)
    df["canal"] = df["canal_primera_interaccion"]

    df["clasificacion_tiempo_entre"] = (
        df["tiempo_promedio_entre_mensajes_min"].apply(_clasif_tiempo_entre))
    df["Orden_clasif_tiempo"] = df["clasificacion_tiempo_entre"].map(_ORDEN_CLASIF)
    if "agente" in df.columns:
        df["agente"] = df["agente"].fillna("(sin agente)")

    out_base = f"reporte_{fecha_desde.isoformat()}_{fecha_hasta.isoformat()}"
    DIR_REPORTES.mkdir(parents=True, exist_ok=True)
    path_parquet = DIR_REPORTES / f"{out_base}.parquet"
    path_csv = DIR_REPORTES / f"{out_base}.csv"
    df.to_parquet(path_parquet, index=False)
    df.to_csv(path_csv, index=False, encoding="utf-8-sig")

    _construir_casos(df, fecha_desde, fecha_hasta)
    return path_parquet


def main() -> None:
    ap = argparse.ArgumentParser(description="Construye la tabla 'reporte' para Power BI.")
    ap.add_argument("--fecha", type=str, help="YYYY-MM-DD (un solo día)")
    ap.add_argument("--desde", type=str, help="YYYY-MM-DD")
    ap.add_argument("--hasta", type=str, help="YYYY-MM-DD")
    args = ap.parse_args()

    if args.fecha:
        d = datetime.strptime(args.fecha, "%Y-%m-%d").date()
        fd = fh = d
    elif args.desde and args.hasta:
        fd = datetime.strptime(args.desde, "%Y-%m-%d").date()
        fh = datetime.strptime(args.hasta, "%Y-%m-%d").date()
    else:
        fd = fh = date.today() - timedelta(days=1)

    out = build_report(fd, fh)
    print(f"OK -> {out}")
    print(f"OK -> {out.with_suffix('.csv')}")


if __name__ == "__main__":
    main()