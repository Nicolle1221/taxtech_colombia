from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from extractor_local import ContribuyenteExogena
from motor_fiscal import depurar_cedula_general

app = FastAPI(title="TaxTech Core Colombia")


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
    ingresos_brutos_laborales: float
    renta_exenta_laboral: float
    deduccion_medicina_prepagada: float
    deduccion_intereses_vivienda: float
    deduccion_dependientes_art387: float
    beneficio_dependientes_ley2277: float
    beneficio_compras_factura_electronica: float
    renta_exenta_fuerza_publica: float
    beneficio_gmf: float
    subtotal_topeado_art336: float
    renta_liquida_gravable: float
    impuesto_uvt: float
    impuesto_pesos: float


@app.post("/api/v1/calcular-renta", response_model=CalcularRentaResponse)
def calcular_renta(request: CalcularRentaRequest) -> CalcularRentaResponse:
    try:
        resultado = depurar_cedula_general(
            contribuyente=request.contribuyente,
            ano_gravable=request.ano_gravable,
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
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return CalcularRentaResponse(**resultado.__dict__)
