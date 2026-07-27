from __future__ import annotations

import json

from anthropic import Anthropic

from extractor_local import ContribuyenteExogena
from motor_fiscal import ResultadoCedulaGeneral, tarifa_marginal_art241, valor_uvt

MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = (
    "Eres un redactor experto en auditoría fiscal colombiana. Recibes datos numéricos "
    "YA CALCULADOS por un motor determinista y tu única tarea es estructurarlos en un "
    "reporte Markdown claro y profesional. Tienes PROHIBIDO realizar o corregir cualquier "
    "cálculo aritmético: usa exclusivamente los valores numéricos que se te entregan, "
    "citados tal cual. No inventes cifras ni normas adicionales."
)


def detectar_alertas_coherencia(resultado: ResultadoCedulaGeneral) -> list[str]:
    alertas = []
    sin_ingresos = resultado.ingresos_brutos_laborales == 0
    if sin_ingresos and resultado.deduccion_medicina_prepagada > 0:
        alertas.append(
            "Se declaró deducción de medicina prepagada sin ingresos de la cédula asociada "
            "(posible causal de sanción por inexactitud, Art. 647 E.T.)."
        )
    if sin_ingresos and resultado.deduccion_intereses_vivienda > 0:
        alertas.append(
            "Se declaró deducción de intereses de vivienda sin ingresos de la cédula asociada "
            "(posible causal de sanción por inexactitud, Art. 647 E.T.)."
        )
    if sin_ingresos and resultado.deduccion_dependientes_art387 > 0:
        alertas.append(
            "Se declaró deducción de dependientes (Art. 387) sin ingresos de la cédula asociada "
            "(posible causal de sanción por inexactitud, Art. 647 E.T.)."
        )
    if not alertas:
        alertas.append(
            "No se detectaron inconsistencias entre las deducciones declaradas y los "
            "ingresos reportados."
        )
    return alertas


def calcular_oportunidad_optimizacion(
    resultado: ResultadoCedulaGeneral, ano_gravable: int
) -> dict:
    margen_disponible = max(0.0, resultado.tope_art336 - resultado.subtotal_topeado_art336)
    uvt = valor_uvt(ano_gravable)
    tarifa_marginal = tarifa_marginal_art241(resultado.renta_liquida_gravable / uvt)
    return {
        "tope_art336_pesos": resultado.tope_art336,
        "subtotal_aplicado_pesos": resultado.subtotal_topeado_art336,
        "margen_disponible_pesos": margen_disponible,
        "tarifa_marginal": tarifa_marginal,
        "ahorro_potencial_pesos": margen_disponible * tarifa_marginal,
    }


def sugerir_aporte_afc_pensiones(
    resultado: ResultadoCedulaGeneral, ano_gravable: int
) -> dict:
    margen_disponible = max(0.0, resultado.tope_art336 - resultado.subtotal_topeado_art336)
    uvt = valor_uvt(ano_gravable)
    tarifa_marginal = tarifa_marginal_art241(resultado.renta_liquida_gravable / uvt)
    return {
        "monto_sugerido_pesos": margen_disponible,
        "tarifa_marginal_referencia": tarifa_marginal,
        "nota": (
            "Estimación basada en el margen disponible del tope Art. 336 del año gravable "
            f"{ano_gravable}; se asume un ingreso similar en el año siguiente."
        ),
    }


def construir_datos_auditoria(
    contribuyente: ContribuyenteExogena,
    resultado: ResultadoCedulaGeneral,
    ano_gravable: int,
) -> dict:
    return {
        "contribuyente": {"nit": contribuyente.nit, "nombre": contribuyente.nombre},
        "resultado_motor_fiscal": resultado.__dict__,
        "alertas_coherencia": detectar_alertas_coherencia(resultado),
        "oportunidad_optimizacion": calcular_oportunidad_optimizacion(resultado, ano_gravable),
        "sugerencia_planeacion_siguiente_anio": sugerir_aporte_afc_pensiones(
            resultado, ano_gravable
        ),
    }


def generar_reporte_auditoria(
    contribuyente: ContribuyenteExogena,
    resultado: ResultadoCedulaGeneral,
    ano_gravable: int,
    client: Anthropic | None = None,
) -> str:
    datos = construir_datos_auditoria(contribuyente, resultado, ano_gravable)
    client = client or Anthropic()

    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    "Genera el reporte de auditoría en Markdown con las secciones "
                    "'## Alertas de Coherencia', '## Oportunidades de Optimización' y "
                    "'## Recomendaciones de Planeación Financiera', usando únicamente "
                    f"estos datos:\n\n{json.dumps(datos, ensure_ascii=False, indent=2)}"
                ),
            }
        ],
    )

    return "".join(
        block.text for block in response.content if block.type == "text"
    )
