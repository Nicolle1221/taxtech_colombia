# TaxTech Core Colombia

Motor de auditoría fiscal para la Cédula General del Formulario 210 (DIAN, Colombia). Extrae información exógena desde PDF, calcula la depuración y el impuesto con funciones deterministas, genera un reporte de auditoría con IA, y lo expone vía API + frontend web.

## Arquitectura

```
documentos/               PDF de prueba (exogena_ejemplo.pdf)
config/
  tabla_art241.py          Constantes: UVT, tabla de tarifas Art. 241, topes Art. 336/387,
                            Ley 2277, GMF — única fuente de verdad para cifras oficiales
src/
  extractor_local.py        pypdf + Anthropic (tool use) -> ContribuyenteExogena (JSON estructurado)
  motor_fiscal.py            Funciones puras: depuración Cédula General, tope Art. 336,
                              impuesto Art. 241. Ningún cálculo fiscal pasa por lenguaje natural.
  auditor_ia.py               Alertas de coherencia + oportunidades de optimización calculadas
                              en Python puro; Anthropic solo redacta el Markdown, nunca calcula.
  guardar_reporte.py           Upsert en Supabase (tabla contribuyentes_exogena)
  main.py                       API FastAPI: conecta extractor -> motor -> auditor -> Supabase
  index.html                    Frontend (Tailwind + Alpine.js + Lucide, sin build step)
tests/
  test_casos_reales.py       3 casos reales: asalariado saturando el tope, fuerza pública
                              (Art. 206 núm. 8), contratista (rentas no laborales, GMF)
  test_api_pdf.py             Integración: endpoint de subida de PDF end-to-end
```

**Regla de diseño (`prompt_rules.md`):** ningún cálculo tributario se resuelve con lenguaje natural. Todo cómputo vive en `motor_fiscal.py` y `auditor_ia.py` como funciones Python puras; el modelo de IA solo extrae texto a JSON (`extractor_local.py`) o redacta prosa a partir de números ya calculados (`auditor_ia.py`).

## Endpoints (FastAPI)

Prefijo base: `/api/v1`

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/v1/calcular-renta` | Recibe `ContribuyenteExogena` ya estructurado (JSON) + parámetros de deducciones. Devuelve el cálculo completo + `reporte_auditoria`. |
| `POST` | `/api/v1/procesar-pdf` | `multipart/form-data`: `archivo` (PDF) + campos de deducciones. Extrae el PDF con IA, calcula y audita. Mismo `response_model` que el anterior. |

Ambos devuelven `CalcularRentaResponse`: `nit`, `nombre`, `ingresos_brutos_laborales`, `renta_exenta_laboral`, deducciones individuales, `tope_art336`, `subtotal_topeado_art336`, `renta_liquida_gravable`, `impuesto_uvt`, `impuesto_pesos`, `reporte_auditoria` (Markdown).

El guardado en Supabase ocurre en segundo plano (`BackgroundTasks`) — la respuesta HTTP no espera a la base de datos.

CORS: `allow_origins=["*"]` (uso de desarrollo/demo; restringir en producción real).

## Pruebas locales

```bash
PYTHONPATH=src:. venv/bin/pytest tests/ -q
```

Corre desde la raíz del proyecto. `PYTHONPATH=src:.` es necesario porque los módulos de `src/` se importan entre sí de forma plana (`from motor_fiscal import ...`), y `motor_fiscal.py` a su vez importa `config.tabla_art241` desde la raíz.

## Correr el servidor localmente

```bash
PYTHONPATH=src:. venv/bin/uvicorn main:app --reload --app-dir src --port 8000
```

Variables de entorno requeridas: `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`.

Luego abre `src/index.html` directamente en el navegador (sin servidor propio) — hace `fetch` a `http://127.0.0.1:8000`.

## Despliegue en Render

1. **Web Service** nuevo, vinculado al repo de GitHub.
2. **Build Command:** `pip install -r requirements.txt`
3. **Start Command** — usar exactamente esta línea (ver nota abajo):
   ```
   PYTHONPATH=src:. uvicorn main:app --app-dir src --host 0.0.0.0 --port $PORT
   ```
4. **Variables de entorno** en el dashboard de Render: `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`.
5. El repo incluye `Procfile` con este mismo comando — si el **Start Command** del dashboard se deja vacío, Render lo toma automáticamente de ahí.

> **Importante:** el comando `uvicorn src.main:app --host 0.0.0.0 --port $PORT` (cargando `main.py` como `src.main`) **falla en producción** — verificado localmente con `ModuleNotFoundError: No module named 'auditor_ia'`. Los módulos de `src/` se importan entre sí sin el prefijo `src.`, así que `src/` debe estar en el `PYTHONPATH` explícitamente, no basta con que `main.py` se cargue como submódulo. Usa siempre el comando con `PYTHONPATH=src:.` y `--app-dir src` de arriba.

## Frontend en Vercel (pendiente)

`src/index.html` apunta a `http://127.0.0.1:8000` — antes de subirlo a Vercel, cambiar `API_BASE_URL` en el `<script>` del archivo a la URL pública del servicio de Render.
