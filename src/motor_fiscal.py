from dataclasses import dataclass
from typing import Iterable

from config.tabla_art241 import (
    BENEFICIO_FACTURACION_ELECTRONICA_TOPE_UVT,
    DEPENDIENTES_ART387_PORCENTAJE,
    DEPENDIENTES_ART387_TOPE_UVT_MES,
    DEPENDIENTES_LEY2277_MAX_DEPENDIENTES,
    DEPENDIENTES_LEY2277_UVT_POR_DEPENDIENTE,
    GMF_PORCENTAJE_DEDUCIBLE,
    INTERESES_VIVIENDA_TOPE_UVT_ANIO,
    LIMITE_GENERAL_ART336_PORCENTAJE,
    LIMITE_GENERAL_ART336_TOPE_UVT,
    MEDICINA_PREPAGADA_TOPE_UVT_MES,
    RENTA_EXENTA_LABORAL_PORCENTAJE,
    RENTA_EXENTA_LABORAL_TOPE_UVT,
    TABLA_ART241,
    UVT,
)
from extractor_local import ContribuyenteExogena


@dataclass
class ResultadoCedulaGeneral:
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


def valor_uvt(ano_gravable: int) -> float:
    if ano_gravable not in UVT:
        raise KeyError(f"No hay UVT configurada para el año gravable {ano_gravable}")
    return UVT[ano_gravable]


def ingresos_brutos_por_conceptos(
    contribuyente: ContribuyenteExogena, conceptos: set[str]
) -> float:
    return sum(
        dato.valor_ingreso
        for dato in contribuyente.datos_fiscales
        if dato.concepto in conceptos
    )


def impuesto_art241(renta_liquida_gravable_uvt: float) -> float:
    if renta_liquida_gravable_uvt <= 0:
        return 0.0
    for limite_inferior, limite_superior, tarifa, base_uvt in TABLA_ART241:
        if renta_liquida_gravable_uvt <= limite_superior:
            return base_uvt + (renta_liquida_gravable_uvt - limite_inferior) * tarifa
    raise ValueError("Renta líquida gravable fuera de los rangos del Art. 241")


def renta_exenta_laboral_25(ingresos_brutos_laborales: float, ano_gravable: int) -> float:
    uvt = valor_uvt(ano_gravable)
    tope = RENTA_EXENTA_LABORAL_TOPE_UVT * uvt
    return min(ingresos_brutos_laborales * RENTA_EXENTA_LABORAL_PORCENTAJE, tope)


def deduccion_medicina_prepagada(
    pagos_mensuales: Iterable[float], ano_gravable: int
) -> float:
    uvt = valor_uvt(ano_gravable)
    tope_mensual = MEDICINA_PREPAGADA_TOPE_UVT_MES * uvt
    return sum(min(pago, tope_mensual) for pago in pagos_mensuales)


def deduccion_intereses_vivienda(intereses_pagados_anual: float, ano_gravable: int) -> float:
    uvt = valor_uvt(ano_gravable)
    tope = INTERESES_VIVIENDA_TOPE_UVT_ANIO * uvt
    return min(intereses_pagados_anual, tope)


def deduccion_dependientes_art387(
    ingresos_brutos_laborales_mensuales: Iterable[float], ano_gravable: int
) -> float:
    uvt = valor_uvt(ano_gravable)
    tope_mensual = DEPENDIENTES_ART387_TOPE_UVT_MES * uvt
    return sum(
        min(ingreso_mes * DEPENDIENTES_ART387_PORCENTAJE, tope_mensual)
        for ingreso_mes in ingresos_brutos_laborales_mensuales
    )


def beneficio_dependientes_ley2277(num_dependientes: int, ano_gravable: int) -> float:
    uvt = valor_uvt(ano_gravable)
    dependientes_reconocidos = min(num_dependientes, DEPENDIENTES_LEY2277_MAX_DEPENDIENTES)
    return dependientes_reconocidos * DEPENDIENTES_LEY2277_UVT_POR_DEPENDIENTE * uvt


def beneficio_compras_factura_electronica(
    valor_compras_factura_electronica: float, ano_gravable: int
) -> float:
    uvt = valor_uvt(ano_gravable)
    tope = BENEFICIO_FACTURACION_ELECTRONICA_TOPE_UVT * uvt
    return min(valor_compras_factura_electronica * 0.01, tope)


def renta_exenta_fuerza_publica(exceso_salario_basico: float) -> float:
    return max(0.0, exceso_salario_basico)


def beneficio_gmf(gmf_pagado_anual: float) -> float:
    return gmf_pagado_anual * GMF_PORCENTAJE_DEDUCIBLE


def limite_general_art336(
    subtotal_exentas_deducciones: float, ingresos_netos: float, ano_gravable: int
) -> float:
    uvt = valor_uvt(ano_gravable)
    tope = min(ingresos_netos * LIMITE_GENERAL_ART336_PORCENTAJE, LIMITE_GENERAL_ART336_TOPE_UVT * uvt)
    return min(subtotal_exentas_deducciones, tope)


def depurar_cedula_general(
    contribuyente: ContribuyenteExogena,
    ano_gravable: int,
    conceptos_ingresos_laborales: set[str],
    pagos_medicina_prepagada_mensuales: Iterable[float] = (),
    intereses_vivienda_pagados_anual: float = 0.0,
    ingresos_brutos_laborales_mensuales: Iterable[float] = (),
    num_dependientes: int = 0,
    valor_compras_factura_electronica: float = 0.0,
    aplica_renta_exenta_laboral_25: bool = True,
    exceso_salario_basico_fuerza_publica: float = 0.0,
    gmf_pagado_anual: float = 0.0,
) -> ResultadoCedulaGeneral:
    ingresos_brutos_laborales = ingresos_brutos_por_conceptos(
        contribuyente, conceptos_ingresos_laborales
    )

    renta_exenta = (
        renta_exenta_laboral_25(ingresos_brutos_laborales, ano_gravable)
        if aplica_renta_exenta_laboral_25
        else 0.0
    )
    ded_medicina = deduccion_medicina_prepagada(
        pagos_medicina_prepagada_mensuales, ano_gravable
    )
    ded_intereses = deduccion_intereses_vivienda(
        intereses_vivienda_pagados_anual, ano_gravable
    )
    ded_dependientes = deduccion_dependientes_art387(
        ingresos_brutos_laborales_mensuales, ano_gravable
    )

    subtotal_dentro_tope = ded_medicina + ded_intereses + ded_dependientes + renta_exenta
    subtotal_topeado = limite_general_art336(
        subtotal_dentro_tope, ingresos_brutos_laborales, ano_gravable
    )

    beneficio_dependientes = beneficio_dependientes_ley2277(num_dependientes, ano_gravable)
    beneficio_facturacion = beneficio_compras_factura_electronica(
        valor_compras_factura_electronica, ano_gravable
    )
    renta_exenta_militar = renta_exenta_fuerza_publica(exceso_salario_basico_fuerza_publica)
    beneficio_gmf_valor = beneficio_gmf(gmf_pagado_anual)

    renta_liquida_gravable = max(
        0.0,
        ingresos_brutos_laborales
        - subtotal_topeado
        - beneficio_dependientes
        - beneficio_facturacion
        - renta_exenta_militar
        - beneficio_gmf_valor,
    )

    uvt = valor_uvt(ano_gravable)
    impuesto_uvt = impuesto_art241(renta_liquida_gravable / uvt)
    impuesto_pesos = impuesto_uvt * uvt

    return ResultadoCedulaGeneral(
        ingresos_brutos_laborales=ingresos_brutos_laborales,
        renta_exenta_laboral=renta_exenta,
        deduccion_medicina_prepagada=ded_medicina,
        deduccion_intereses_vivienda=ded_intereses,
        deduccion_dependientes_art387=ded_dependientes,
        beneficio_dependientes_ley2277=beneficio_dependientes,
        beneficio_compras_factura_electronica=beneficio_facturacion,
        renta_exenta_fuerza_publica=renta_exenta_militar,
        beneficio_gmf=beneficio_gmf_valor,
        subtotal_topeado_art336=subtotal_topeado,
        renta_liquida_gravable=renta_liquida_gravable,
        impuesto_uvt=impuesto_uvt,
        impuesto_pesos=impuesto_pesos,
    )
