Versión de prueba para mejora de proyecto métricas de WhatsApp extrayendo de SQL Server guardando los datos localmente.

## Estructura hexagonal

```
proyecto_whatsapp/
├── config/
│   ├── settings.py          
│   └── container.py         
├── src/whatsapp_metrics/
│   ├── domain/              
│   │   ├── entities.py
│   │   ├── metrics_calculator.py
│   │   └── ports/           
│   │       ├── source_repository.py
│   │       └── target_repository.py
│   └── application/         
│   │   ├── extract_to_local.py
│   │   └── compute_metrics_from_local.py
│   └── infrastructure/          
│       ├── sqlserver/sagicc_repository.py    
│       └── localfiles/file_repository.py   
├── apps/etl_runner/run.py   
├── tests/unit/tests_metrics_calculator.py        
├── output/      
│   ├── auditoria/   
│   ├── metricas/      
│   ├── raw/      
│   ├── reportes/                     
├── logs/
├── .env
├── auditoria_excel.py
├── build_report.py
├── unify.py
└── requirements.txt
```

## Reglas de negocio

Las métricas conservan los nombres del query SQL original:

| Métrica | Definición |
|---|---|
| `nro_caso` | Caso |
| `canal_primera_interaccion` | Canal del primer mensaje |
| `primera_interaccion_cliente` | Fecha/hora primer mensaje del cliente |
| `primera_interaccion_bot` | Fecha/hora primera respuesta del bot |
| `primera_interaccion_humano` | Fecha/hora primera respuesta del teleoperador |
| `ftr_bot_min` | Minutos entre `primera_interaccion_cliente` y `primera_interaccion_bot` |
| `tfr_human_min` | Minutos entre `primera_interaccion_cliente` y `primera_interaccion_humano` |
| `ultima_interaccion` | Fecha/hora último mensaje |
| `tiempo_promedio_de_interaccion_min` | Minutos entre `primera_interaccion` y `ultima_interaccion` |
| `total_mensajes` | Cantidad total de mensajes |
| `mensajes_cliente` / `mensajes_bot` / `mensajes_humano` | Desagregado |
| `atendido_por_humano` | bool: hubo televendedor humano |
| `cumple_min_mensajes` | bool: total_mensajes > 2  |


## Uso

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt                                 

# Validar la lógica sin tocar la BD
pytest tests/unit/ -v

# Probar conexión a SQL Server 
python -m apps.etl_runner.run --probar-conexion --fecha 2026-06-01


# Día específico
python -m apps.etl_runner.run --fecha 22026-06-01

# Rango 
python -m apps.etl_runner.run --desde 2026-06-01 --hasta 2026-06-02

# Solo descargar raw (sin calcular métricas)
python -m apps.etl_runner.run --fecha 2026-06-01 --solo-extract

# Solo recalcular métricas desde raw ya descargado
python -m apps.etl_runner.run --fecha 2026-06-01 --solo-metricas

# Generación de reporte para Power BI (Tercera tabla para pruebas)
python build_report.py --desde 2026-06-01 --hasta 2026-06-02

# Unificación de reportes por rango
python unify.py --desde 2026-06-01 --hasta 2026-06-02

# Unificación de todos los reportes 
python unify.py --todos
```

## Archivos generados (en `output/`)

Se encuentran 5 tipos de archivos generados

- `raw_YYYY-MM-DD_YYYY-MM-DD.parquet` y `.csv` — interacciones crudas
- `metricas_YYYY-MM-DD_YYYY-MM-DD.parquet` y `.csv` — métricas por caso
- `reporte_YYYY-MM-DD_YYYY-MM-DD.parquet` y `.csv` — métricas para reporte Power BI
- `casos_YYYY-MM-DD_YYYY-MM-DD.parquet` y `.csv` — total de casos incluidos no atendidos para reporte Power BI
- `auditoria_YYYY-MM-DD_YYYY-MM-DD.parquet` y `.csv` — seguimiento de casos con condiciones planteadas
- `auditoria_general.xlsx` y `.json` — seguimiento general independientemente de fecha


Importante: re-correr para la misma fecha sobrescribe los archivos.