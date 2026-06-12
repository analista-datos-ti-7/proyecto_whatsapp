from __future__ import annotations

from datetime import datetime

from src.whatsapp_metrics.domain.entities import (
    Interaccion,
    MetricasCaso,
    ResultadoCaso,
)

DOMINIO_SISTEMA = "@SAGICC.CO"

CONTENIDOS_LLAMADA: tuple[str, ...] = ("llamada saliente", "llamada entrante")

PALABRAS_VENTA: tuple[str, ...] = (
    "precio", "pollo", "muslo", "pechuga", "alas", "carne", "corte"
    "domicilio", "efectivo", "debito", "débito", "credito", "crédito",
    "pedido", "pago", "factura", "entrega", "compra", "venta",
    "valor", "kilo", "combo", "promo", "costo", "cuanto", "cuánto",
    "transferencia", "nequi", "daviplata", "sucursal", "despacho",
    "porfavor", "gracias", "libra"
)

PALABRAS_COLABORADOR: tuple[str, ...] = (
    "parce", "parcero", "mijo", "jefe", "mantenimiento", "almuerzo", "reunion",
    "reunión", "jefe", "compañero", "compañera", "turno", "descanso", "nomina",
    "nómina", "permiso", "incapacidad", "vacaciones", "granja", "mantenimiento"
)

SALUDOS_TRIVIALES: frozenset[str] = frozenset({
    "hola", "holaa", "buenas", "buen dia", "buen día",
    "buenos dias", "buenos días", "buenas tardes", "buenas noches",
    "gracias", "muchas gracias", "ok", "okey", "vale", "listo",
    "si", "sí", "no", "de acuerdo", "hello", "hi", "bueno",
})
FRASES_NO_SUSTANTIVAS: tuple[str, ...] = (
    "encuesta", "calific", "puntu", "del 1 al", "satisfacc", "recomendar",
    "su opinion", "su opinión", "gracias por", "muy amable",
    "excelente servicio", "buen servicio", "feliz dia", "feliz día",
    "bendiciones",
)

MULTIMEDIA_EXTENSIONES: tuple[str, ...] = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp3", ".ogg", ".opus",
    ".aac", ".m4a", ".mp4", ".mov", ".3gp", ".pdf",
)
MULTIMEDIA_MARCADORES: tuple[str, ...] = (
    "audio", "imagen", "video", "sticker", "foto",
    "archivo adjunto", "adjunto", "ptt", "media", "documento",
)

MAX_MENSAJES_EXTRAORDINARIO = 30
GAP_MAX_HORAS = 24


def _normalizar(texto: str | None) -> str:
    return "" if texto is None else texto.strip().lower()


def _contiene(contenido: str | None, terminos: tuple[str, ...]) -> bool:
    c = _normalizar(contenido)
    return bool(c) and any(t in c for t in terminos)


def _es_marcador_llamada(i: Interaccion) -> bool:
    return _normalizar(i.contenido) in CONTENIDOS_LLAMADA


def _usuario_es_sistema(usuario: str | None) -> bool:
    if not usuario:
        return True
    u = usuario.upper()
    return DOMINIO_SISTEMA in u or u.startswith("SAGICC")


def _es_mensaje_trivial(contenido: str | None) -> bool:
    c = _normalizar(contenido).strip("¡!¿?.,;:()\"'* ")
    if len(c) <= 3 or c in SALUDOS_TRIVIALES:
        return True
    return any(f in c for f in FRASES_NO_SUSTANTIVAS)


def _es_multimedia(contenido: str | None) -> bool:
    c = _normalizar(contenido)
    if not c:
        return True
    if any(ext in c for ext in MULTIMEDIA_EXTENSIONES):
        return True
    if "omitid" in c:
        return True
    return c.strip("[]<>() ") in MULTIMEDIA_MARCADORES


def es_cliente(i: Interaccion) -> bool:
    return i.es_inbound


def es_bot(i: Interaccion) -> bool:
    return i.es_outbound and _usuario_es_sistema(i.usuario)


def es_humano(i: Interaccion) -> bool:
    return i.es_outbound and not _usuario_es_sistema(i.usuario)


def _tiempo_promedio_entre_mensajes(ordenadas: list[Interaccion]) -> float | None:
    if len(ordenadas) < 2:
        return None
    deltas = [
        (ordenadas[k + 1].fecha_creacion - ordenadas[k].fecha_creacion).total_seconds()
        for k in range(len(ordenadas) - 1)
    ]
    return round((sum(deltas) / len(deltas)) / 60.0, 3)


def _icc_desde_minutos(min_prom: float | None) -> int | None:
    if min_prom is None:
        return None
    if min_prom <= 2:
        return 100
    if min_prom <= 5:
        return 80
    if min_prom <= 10:
        return 50
    return 20


def _nombre_agente(usuario: str | None) -> str | None:
    if not usuario:
        return None
    return usuario.split(" - ")[0].strip() or None


def analizar_caso(interacciones: list[Interaccion]) -> ResultadoCaso | None:
    if not interacciones:
        return None

    nro = interacciones[0].nro_caso
    resultado = ResultadoCaso(nro_caso=nro, metricas=None)
    resultado.fecha_caso = min(i.fecha_creacion for i in interacciones)

    # 1) Duplicados exactos
    vistos: set[tuple] = set()
    unicas: list[Interaccion] = []
    dup_sustantivo = False
    for i in interacciones:
        clave = (i.fecha_creacion, i.direccionamiento, i.usuario, i.contenido)
        if clave in vistos:
            resultado.duplicados_eliminados += 1
            if not _es_mensaje_trivial(i.contenido):
                dup_sustantivo = True
            continue
        vistos.add(clave)
        unicas.append(i)

    # 2) Llamadas
    hubo_llamada = any(_es_marcador_llamada(i) for i in unicas)
    chat = [i for i in unicas if not _es_marcador_llamada(i)]
    ordenadas = sorted(chat, key=lambda i: i.fecha_creacion)
    inbounds = [i for i in ordenadas if es_cliente(i)]
    outbounds = [i for i in ordenadas if i.es_outbound]

    if hubo_llamada:
        if inbounds and outbounds:
            resultado.categorias.append("con_llamada")
        else:
            resultado.categorias.append("llamada")
            return resultado

    # 3) Vacío
    if not ordenadas:
        resultado.categorias.append("vacio")
        return resultado

    # 4) Un solo mensaje
    if len(ordenadas) == 1:
        return resultado

    # 5) Fechas incoherentes
    for k in range(len(ordenadas) - 1):
        horas = (ordenadas[k + 1].fecha_creacion
                 - ordenadas[k].fecha_creacion).total_seconds() / 3600.0
        if horas > GAP_MAX_HORAS:
            resultado.categorias.append("fechas_incoherentes")
            return resultado

    # 6) No-conversación
    if inbounds and not outbounds:
        if dup_sustantivo:
            resultado.categorias.append("duplicados")
        resultado.categorias.append("solo_inbound")
        return resultado
    if outbounds and not inbounds:
        resultado.categorias.append("solo_outbound")
        return resultado

    # 7) Mismo mensaje del cliente repetido
    textos_cliente = [t for t in (_normalizar(i.contenido) for i in inbounds) if t]
    if len(textos_cliente) >= 2 and len(set(textos_cliente)) == 1:
        resultado.categorias.append("mensaje_repetido")
        return resultado

    if dup_sustantivo:
        resultado.categorias.append("duplicados")

    # 8) Charla aparte
    es_venta = any(_contiene(i.contenido, PALABRAS_VENTA) for i in ordenadas)
    if not es_venta:
        hay_colaborador = any(
            _contiene(i.contenido, PALABRAS_COLABORADOR) for i in ordenadas)
        resultado.categorias.append(
            "colaborador" if hay_colaborador else "sin_palabras_venta")
        return resultado

    # 9) Respuesta HUMANA posterior al primer cliente
    primera_cliente = inbounds[0]
    t0 = primera_cliente.fecha_creacion
    primer_humano = next(
        (i for i in ordenadas if es_humano(i) and i.fecha_creacion >= t0), None)
    if primer_humano is None:
        resultado.categorias.append("sin_atencion_humana")
        return resultado

    # 10) El bot es OPCIONAL. Si NO hubo bot, se marca 'sin_bot' pero SÍ se calcula.
    primer_bot = next(
        (i for i in ordenadas if es_bot(i) and i.fecha_creacion >= t0), None)
    if primer_bot is None:
        resultado.categorias.append("sin_bot")

    # 11) Cálculo de métricas
    primer = ordenadas[0]
    ultimo = ordenadas[-1]
    total = len(ordenadas)
    if total > MAX_MENSAJES_EXTRAORDINARIO:
        resultado.categorias.append("extraordinario")

    prom_entre = _tiempo_promedio_entre_mensajes(ordenadas)

    resultado.metricas = MetricasCaso(
        nro_caso=nro,
        primera_interaccion_cliente=t0,
        primera_interaccion_bot=primer_bot.fecha_creacion if primer_bot else None,
        primera_interaccion_humano=primer_humano.fecha_creacion,
        ultima_interaccion=ultimo.fecha_creacion,
        ftr_bot_min=_delta_min(t0, primer_bot.fecha_creacion) if primer_bot else None,
        tfr_human_min=_delta_min(t0, primer_humano.fecha_creacion),
        tiempo_promedio_de_interaccion_min=_delta_min(
            primer.fecha_creacion, ultimo.fecha_creacion),
        canal_primera_interaccion=primer.canal,
        campania=primer.campania,
        total_mensajes=total,
        mensajes_cliente=len(inbounds),
        mensajes_bot=sum(1 for i in ordenadas if es_bot(i)),
        mensajes_humano=sum(1 for i in ordenadas if es_humano(i)),
        mensajes_multimedia=sum(1 for i in ordenadas if _es_multimedia(i.contenido)),
        atendido_por_humano=True,
        cumple_min_mensajes=total > 2,
        es_venta=True,
        fecha_calculo=datetime.now(),
        tiempo_promedio_entre_mensajes_min=prom_entre,
        icc_score=_icc_desde_minutos(prom_entre),
        agente=_nombre_agente(primer_humano.usuario),
        tuvo_bot=primer_bot is not None,
    )
    return resultado


def calcular_metricas_caso(interacciones: list[Interaccion]) -> MetricasCaso | None:
    r = analizar_caso(interacciones)
    return r.metricas if r else None


def _delta_min(t_ini: datetime, t_fin: datetime) -> float:
    return round((t_fin - t_ini).total_seconds() / 60.0, 3)