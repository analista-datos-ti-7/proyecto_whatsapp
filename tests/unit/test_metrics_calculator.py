from __future__ import annotations
from datetime import datetime
from src.whatsapp_metrics.domain.entities import Direccionamiento, Interaccion
from src.whatsapp_metrics.domain.metrics_calculator import (
    MAX_MENSAJES_EXTRAORDINARIO, analizar_caso,
)

IN, OUT = Direccionamiento.INBOUND, Direccionamiento.OUTBOUND
SISTEMA = "SAGICC SISTEMA - sistema@sagicc.co"
API = "SAGICC API - api@sagicc.co"
AGENTE = "MARIA RONDON - maria@avsasa.com"


def _msg(minuto, direc, usuario, contenido, segundo=0):
    return Interaccion(1, datetime(2026, 6, 1, 10 + minuto // 60, minuto % 60, segundo),
                       direc, usuario, "CANAL", "GIRON", contenido)


def _msg_f(fecha, direc, usuario, contenido):
    return Interaccion(1, fecha, direc, usuario, "CANAL", "GIRON", contenido)


class TestConversacionValida:
    def test_cliente_bot_humano(self):
        r = analizar_caso([
            _msg(0, IN, SISTEMA, "buenas, precio del pollo?"),
            _msg(1, OUT, SISTEMA, "Bienvenido"),
            _msg(5, OUT, AGENTE, "el kilo a 12.000"),
        ])
        m = r.metricas
        assert m is not None and m.ftr_bot_min == 1.0 and m.tfr_human_min == 5.0

    def test_sagicc_api_es_bot(self):
        r = analizar_caso([
            _msg(0, IN, SISTEMA, "precio del combo?"),
            _msg(2, OUT, API, "auto"),
            _msg(9, OUT, AGENTE, "le confirmo el valor"),
        ])
        assert r.metricas.ftr_bot_min == 2.0 and r.metricas.tfr_human_min == 9.0

    def test_sin_bot_si_se_calcula(self):
        r = analizar_caso([
            _msg(0, IN, SISTEMA, "precio del pollo?"),
            _msg(4, OUT, AGENTE, "12.000 el kilo"),
        ])
        m = r.metricas
        assert m is not None
        assert m.ftr_bot_min is None
        assert m.primera_interaccion_bot is None
        assert m.tfr_human_min == 4.0
        assert "sin_bot" in r.categorias
        assert m.tuvo_bot is False


class TestAtencionHumana:
    def test_sin_humano_se_descarta(self):
        r = analizar_caso([
            _msg(0, IN, SISTEMA, "precio del pollo?"),
            _msg(1, OUT, SISTEMA, "respuesta del bot"),
        ])
        assert r.metricas is None and "sin_atencion_humana" in r.categorias


class TestSinVenta:
    def test_charla_sin_venta_se_descarta(self):
        r = analizar_caso([
            _msg(0, IN, SISTEMA, "viste el partido anoche?"),
            _msg(2, OUT, AGENTE, "jaja si tremendo"),
        ])
        assert r.metricas is None
        assert "sin_palabras_venta" in r.categorias

    def test_colaborador_se_descarta(self):
        r = analizar_caso([
            _msg(0, IN, SISTEMA, "parce me cambias el turno?"),
            _msg(2, OUT, AGENTE, "listo, hablo con el jefe"),
        ])
        assert r.metricas is None
        assert "colaborador" in r.categorias


class TestFechasIncoherentes:
    def test_hueco_grande_se_descarta(self):
        r = analizar_caso([
            _msg_f(datetime(2026, 6, 1, 10, 0), IN, SISTEMA, "precio del pollo?"),
            _msg_f(datetime(2026, 6, 3, 9, 0), OUT, AGENTE, "12.000"),
        ])
        assert r.metricas is None
        assert "fechas_incoherentes" in r.categorias


class TestMensajeRepetido:
    def test_mismo_mensaje_no_es_conversacion(self):
        r = analizar_caso([
            _msg(0, IN, SISTEMA, "necesito mi factura del pedido"),
            _msg(7, IN, SISTEMA, "necesito mi factura del pedido"),
            _msg(15, IN, SISTEMA, "necesito mi factura del pedido"),
            _msg(20, OUT, AGENTE, "se la envío"),
        ])
        assert r.metricas is None and "mensaje_repetido" in r.categorias


class TestLlamadas:
    def test_inbound_mas_llamada_se_descarta(self):
        r = analizar_caso([
            _msg(0, IN, SISTEMA, "precio del pollo"),
            _msg(3, OUT, AGENTE, "Llamada Saliente"),
        ])
        assert r.metricas is None and "llamada" in r.categorias

    def test_llamada_con_chat_se_calcula(self):
        r = analizar_caso([
            _msg(0, IN, SISTEMA, "precio del pollo?"),
            _msg(2, OUT, AGENTE, "12.000 el kilo"),
            _msg(5, OUT, AGENTE, "Llamada Saliente"),
        ])
        assert r.metricas is not None and "con_llamada" in r.categorias
        assert r.metricas.total_mensajes == 2


class TestNoConversacion:
    def test_solo_inbound_dos(self):
        r = analizar_caso([_msg(0, IN, SISTEMA, "hola"), _msg(1, IN, SISTEMA, "?")])
        assert r.metricas is None and "solo_inbound" in r.categorias

    def test_unico_sin_marcar(self):
        r = analizar_caso([_msg(0, IN, SISTEMA, "hola")])
        assert r.metricas is None and r.categorias == []


class TestDuplicados:
    def test_dup_sustantivo_marca(self):
        r = analizar_caso([
            _msg(0, IN, SISTEMA, "dame 2 horas para el pedido"),
            _msg(0, IN, SISTEMA, "dame 2 horas para el pedido"),
            _msg(1, IN, SISTEMA, "mejor un kilo de alas"),
            _msg(4, OUT, AGENTE, "listo"),
        ])
        assert r.metricas is not None and "duplicados" in r.categorias
        assert r.duplicados_eliminados == 1

    def test_dup_encuesta_no_marca(self):
        r = analizar_caso([
            _msg(0, IN, SISTEMA, "califica mi servicio del 1 al 5"),
            _msg(0, IN, SISTEMA, "califica mi servicio del 1 al 5"),
            _msg(1, IN, SISTEMA, "precio del pollo?"),
            _msg(4, OUT, AGENTE, "12.000"),
        ])
        assert r.metricas is not None
        assert "duplicados" not in r.categorias

    def test_saludo_repetido_no_marca(self):
        r = analizar_caso([
            _msg(0, IN, SISTEMA, "Hola!"),
            _msg(0, IN, SISTEMA, "Hola!"),
            _msg(1, IN, SISTEMA, "precio del pollo?"),
            _msg(4, OUT, AGENTE, "12.000"),
        ])
        assert r.metricas is not None and "duplicados" not in r.categorias


class TestExtraordinarios:
    def test_mas_de_30_se_marca(self):
        msgs = [_msg(0, IN, SISTEMA, "precio del pollo?")]
        for k in range(MAX_MENSAJES_EXTRAORDINARIO):
            d = IN if k % 2 else OUT
            u = SISTEMA if k % 2 else AGENTE
            msgs.append(_msg(1 + k, d, u, f"mensaje {k}", segundo=30))
        r = analizar_caso(msgs)
        assert r.metricas is not None and "extraordinario" in r.categorias


class TestMultimedia:
    def test_audios_cuentan(self):
        r = analizar_caso([
            _msg(0, IN, SISTEMA, "le mando la foto del pedido"),
            _msg(1, IN, SISTEMA, None),
            _msg(2, IN, SISTEMA, "imagen_3422.jpg"),
            _msg(4, OUT, AGENTE, "recibido, va su pedido"),
        ])
        m = r.metricas
        assert m.total_mensajes == 4 and m.mensajes_cliente == 3
        assert m.mensajes_multimedia == 2


class TestMultiCategoria:
    def test_solo_outbound_con_dup_no_marca_duplicados(self):
        r = analizar_caso([
            _msg(0, OUT, SISTEMA, "le recordamos su pedido pendiente"),
            _msg(0, OUT, SISTEMA, "le recordamos su pedido pendiente"),
            _msg(1, OUT, SISTEMA, "no se la pierda"),
        ])
        assert r.metricas is None
        assert "solo_outbound" in r.categorias
        assert "duplicados" not in r.categorias
        assert r.duplicados_eliminados == 1

    def test_solo_inbound_con_dup_si_marca_ambas(self):
        r = analizar_caso([
            _msg(0, IN, SISTEMA, "dame 2 horas para confirmar el pedido"),
            _msg(0, IN, SISTEMA, "dame 2 horas para confirmar el pedido"),
            _msg(1, IN, SISTEMA, "sigo esperando respuesta"),
        ])
        assert r.metricas is None
        assert "solo_inbound" in r.categorias
        assert "duplicados" in r.categorias


class TestSinBot:
    def test_con_bot_no_marca_sin_bot(self):
        r = analizar_caso([
            _msg(0, IN, SISTEMA, "precio del pollo?"),
            _msg(1, OUT, SISTEMA, "Bienvenido"),
            _msg(5, OUT, AGENTE, "12.000 el kilo"),
        ])
        assert r.metricas is not None
        assert "sin_bot" not in r.categorias
        assert r.metricas.tuvo_bot is True

    def test_sin_bot_marca_y_calcula(self):
        r = analizar_caso([
            _msg(0, IN, SISTEMA, "precio del combo?"),
            _msg(3, OUT, AGENTE, "el combo a 25.000"),
            _msg(6, IN, SISTEMA, "perfecto, lo quiero"),
        ])
        assert r.metricas is not None          
        assert "sin_bot" in r.categorias        
        assert r.metricas.tuvo_bot is False
        assert r.metricas.ftr_bot_min is None


class TestICC:
    def test_icc_100_muy_rapido(self):
        # huecos: 1 y 1 min -> promedio 1.0 -> ICC 100
        r = analizar_caso([
            _msg(0, IN, SISTEMA, "precio del pollo?"),
            _msg(1, OUT, AGENTE, "12.000"),
            _msg(2, IN, SISTEMA, "listo gracias"),
        ])
        m = r.metricas
        assert m.tiempo_promedio_entre_mensajes_min == 1.0
        assert m.icc_score == 100

    def test_icc_80_fluida(self):
        # huecos 4 y 4 -> promedio 4 -> ICC 80
        r = analizar_caso([
            _msg(0, IN, SISTEMA, "precio del pollo?"),
            _msg(4, OUT, AGENTE, "12.000"),
            _msg(8, IN, SISTEMA, "vale lo llevo"),
        ])
        assert r.metricas.icc_score == 80

    def test_icc_20_frio(self):
        # huecos 15 y 15 -> promedio 15 -> ICC 20
        r = analizar_caso([
            _msg(0, IN, SISTEMA, "precio del pollo?"),
            _msg(15, OUT, AGENTE, "12.000"),
            _msg(30, IN, SISTEMA, "ok"),
        ])
        assert r.metricas.icc_score == 20


class TestAgente:
    def test_nombre_agente_se_extrae(self):
        r = analizar_caso([
            _msg(0, IN, SISTEMA, "precio del pollo?"),
            _msg(2, OUT, AGENTE, "12.000 el kilo"),
        ])
        assert r.metricas.agente == "MARIA RONDON"