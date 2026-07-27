import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from extractor_local import ContribuyenteExogena
from motor_fiscal import depurar_cedula_general

ANO_GRAVABLE = 2025


def test_caso_a_asalariado_satura_tope_40_por_ciento():
    contribuyente = ContribuyenteExogena(
        nit="10203040-5",
        nombre="EMPLEADO ASALARIADO",
        datos_fiscales=[
            {
                "concepto": "5001",
                "descripcion_concepto": "Salarios",
                "nit_informante": "890903938",
                "razon_social_informante": "EMPLEADOR S.A.",
                "valor_ingreso": 150_000_000.0,
                "valor_retencion": 0.0,
                "ano_gravable": ANO_GRAVABLE,
            }
        ],
    )

    resultado = depurar_cedula_general(
        contribuyente=contribuyente,
        ano_gravable=ANO_GRAVABLE,
        conceptos_ingresos_laborales={"5001"},
        pagos_medicina_prepagada_mensuales=[2_000_000] * 12,
        intereses_vivienda_pagados_anual=25_000_000,
        ingresos_brutos_laborales_mensuales=[12_500_000] * 12,
        num_dependientes=2,
    )

    assert resultado.subtotal_topeado_art336 == pytest.approx(60_000_000.0)
    assert resultado.beneficio_dependientes_ley2277 == pytest.approx(7_171_056.0)
    assert resultado.renta_liquida_gravable == pytest.approx(82_828_944.0)
    assert resultado.impuesto_pesos == pytest.approx(5_424_126.46, rel=1e-6)


def test_caso_b_fuerza_publica_exceso_salario_100_exento():
    contribuyente = ContribuyenteExogena(
        nit="20304050-1",
        nombre="MIEMBRO FUERZA PUBLICA",
        datos_fiscales=[
            {
                "concepto": "5001",
                "descripcion_concepto": "Salarios y prestaciones fuerza pública",
                "nit_informante": "899999061",
                "razon_social_informante": "MINISTERIO DE DEFENSA NACIONAL",
                "valor_ingreso": 96_000_000.0,
                "valor_retencion": 0.0,
                "ano_gravable": ANO_GRAVABLE,
            }
        ],
    )

    resultado = depurar_cedula_general(
        contribuyente=contribuyente,
        ano_gravable=ANO_GRAVABLE,
        conceptos_ingresos_laborales={"5001"},
        exceso_salario_basico_fuerza_publica=60_000_000.0,
    )

    assert resultado.renta_exenta_fuerza_publica == pytest.approx(60_000_000.0)
    assert resultado.renta_liquida_gravable == pytest.approx(12_000_000.0)
    assert resultado.impuesto_pesos == pytest.approx(0.0)


def test_caso_c_contratista_rentas_no_laborales_gmf_y_factura_electronica():
    contribuyente = ContribuyenteExogena(
        nit="30405060-2",
        nombre="CONTRATISTA INDEPENDIENTE",
        datos_fiscales=[
            {
                "concepto": "3008",
                "descripcion_concepto": "Honorarios",
                "nit_informante": "800100100",
                "razon_social_informante": "CLIENTE CONTRATANTE S.A.S.",
                "valor_ingreso": 80_000_000.0,
                "valor_retencion": 0.0,
                "ano_gravable": ANO_GRAVABLE,
            }
        ],
    )

    resultado = depurar_cedula_general(
        contribuyente=contribuyente,
        ano_gravable=ANO_GRAVABLE,
        conceptos_ingresos_laborales={"3008"},
        valor_compras_factura_electronica=10_000_000.0,
        gmf_pagado_anual=800_000.0,
        aplica_renta_exenta_laboral_25=False,
    )

    assert resultado.renta_exenta_laboral == pytest.approx(0.0)
    assert resultado.beneficio_compras_factura_electronica == pytest.approx(100_000.0)
    assert resultado.beneficio_gmf == pytest.approx(400_000.0)
    assert resultado.renta_liquida_gravable == pytest.approx(79_500_000.0)
    assert resultado.impuesto_pesos == pytest.approx(4_791_627.10, rel=1e-6)
