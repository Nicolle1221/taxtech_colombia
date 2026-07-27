import sys

from anthropic import Anthropic
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auditor_ia import generar_reporte_auditoria
from extractor_local import ContribuyenteExogena, extraer_texto_pdf_bytes, texto_a_estructura
from guardar_reporte import guardar_reporte_contribuyente
from motor_fiscal import depurar_cedula_general

app = FastAPI(title="TaxTech Core Colombia")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)


class CalcularRentaRequest(BaseModel):
    contribuyente: ContribuyenteExogena
    ano_gravable: int
    conceptos_ingresos_laborales: set[str]
    pagos_medicina_prepagada_mensuales: list[float] = []
    intereses_vivienda_pagados_anual: float = 0.0
    ingresos_brutos_laborales_mensuales: list[float] = []
    num_dependientes: int = 0
    valor_compras_factura_electronica: float = 0.0
    aplica_renta_exenta_laboral_25: bool = True
    exceso_salario_basico_fuerza_publica: float = 0.0
    gmf_pagado_anual: float = 0.0


class CalcularRentaResponse(BaseModel):
    nit: str
    nombre: str
    ingresos_brutos_laborales: float
    renta_exenta_laboral: float
    deduccion_medicina_prepagada: float
    deduccion_intereses_vivienda: float
    deduccion_dependientes_art387: float
    beneficio_dependientes_ley2277: float
    beneficio_compras_factura_electronica: float
    renta_exenta_fuerza_publica: float
    beneficio_gmf: float
    tope_art336: float
    subtotal_topeado_art336: float
    renta_liquida_gravable: float
    impuesto_uvt: float
    impuesto_pesos: float
    reporte_auditoria: str


def _guardar_reporte_en_segundo_plano(
    nit: str, nombre: str, resultado_motor_fiscal: dict, reporte_auditoria_markdown: str
) -> None:
    try:
        guardar_reporte_contribuyente(
            nit, nombre, resultado_motor_fiscal, reporte_auditoria_markdown
        )
        print(f"OK: reporte guardado en Supabase para NIT {nit}")
    except Exception as exc:
        print(f"ERROR: no se pudo guardar en Supabase para NIT {nit}: {exc}", file=sys.stderr)


def _calcular_y_auditar(
    contribuyente: ContribuyenteExogena,
    ano_gravable: int,
    background_tasks: BackgroundTasks,
    **kwargs_depuracion,
) -> CalcularRentaResponse:
    try:
        resultado = depurar_cedula_general(
            contribuyente=contribuyente, ano_gravable=ano_gravable, **kwargs_depuracion
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        reporte_auditoria = generar_reporte_auditoria(
            contribuyente=contribuyente, resultado=resultado, ano_gravable=ano_gravable
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"No se pudo generar el reporte de auditoría: {exc}"
        ) from exc

    background_tasks.add_task(
        _guardar_reporte_en_segundo_plano,
        contribuyente.nit,
        contribuyente.nombre,
        resultado.__dict__,
        reporte_auditoria,
    )

    return CalcularRentaResponse(
        nit=contribuyente.nit,
        nombre=contribuyente.nombre,
        reporte_auditoria=reporte_auditoria,
        **resultado.__dict__,
    )


def _parse_csv_floats(valor: str) -> list[float]:
    return [float(v) for v in valor.split(",") if v.strip()]


@app.post("/api/v1/calcular-renta", response_model=CalcularRentaResponse)
def calcular_renta(
    request: CalcularRentaRequest, background_tasks: BackgroundTasks
) -> CalcularRentaResponse:
    return _calcular_y_auditar(
        contribuyente=request.contribuyente,
        ano_gravable=request.ano_gravable,
        background_tasks=background_tasks,
        conceptos_ingresos_laborales=request.conceptos_ingresos_laborales,
        pagos_medicina_prepagada_mensuales=request.pagos_medicina_prepagada_mensuales,
        intereses_vivienda_pagados_anual=request.intereses_vivienda_pagados_anual,
        ingresos_brutos_laborales_mensuales=request.ingresos_brutos_laborales_mensuales,
        num_dependientes=request.num_dependientes,
        valor_compras_factura_electronica=request.valor_compras_factura_electronica,
        aplica_renta_exenta_laboral_25=request.aplica_renta_exenta_laboral_25,
        exceso_salario_basico_fuerza_publica=request.exceso_salario_basico_fuerza_publica,
        gmf_pagado_anual=request.gmf_pagado_anual,
    )


@app.post("/api/v1/procesar-pdf", response_model=CalcularRentaResponse)
async def procesar_pdf(
    background_tasks: BackgroundTasks,
    archivo: UploadFile = File(...),
    ano_gravable: int = Form(...),
    conceptos_ingresos_laborales: str = Form(...),
    pagos_medicina_prepagada_mensuales: str = Form(""),
    intereses_vivienda_pagados_anual: float = Form(0.0),
    ingresos_brutos_laborales_mensuales: str = Form(""),
    num_dependientes: int = Form(0),
    valor_compras_factura_electronica: float = Form(0.0),
    aplica_renta_exenta_laboral_25: bool = Form(True),
    exceso_salario_basico_fuerza_publica: float = Form(0.0),
    gmf_pagado_anual: float = Form(0.0),
) -> CalcularRentaResponse:
    if archivo.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF")

    contenido = await archivo.read()
    try:
        texto = extraer_texto_pdf_bytes(contenido)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No se pudo leer el PDF: {exc}") from exc

    try:
        contribuyente = texto_a_estructura(Anthropic(), texto)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"No se pudo extraer la información del PDF: {exc}"
        ) from exc

    return _calcular_y_auditar(
        contribuyente=contribuyente,
        ano_gravable=ano_gravable,
        background_tasks=background_tasks,
        conceptos_ingresos_laborales=set(conceptos_ingresos_laborales.split(",")),
        pagos_medicina_prepagada_mensuales=_parse_csv_floats(pagos_medicina_prepagada_mensuales),
        intereses_vivienda_pagados_anual=intereses_vivienda_pagados_anual,
        ingresos_brutos_laborales_mensuales=_parse_csv_floats(ingresos_brutos_laborales_mensuales),
        num_dependientes=num_dependientes,
        valor_compras_factura_electronica=valor_compras_factura_electronica,
        aplica_renta_exenta_laboral_25=aplica_renta_exenta_laboral_25,
        exceso_salario_basico_fuerza_publica=exceso_salario_basico_fuerza_publica,
        gmf_pagado_anual=gmf_pagado_anual,
    )
