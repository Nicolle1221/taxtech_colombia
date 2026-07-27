import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import main
from extractor_local import ContribuyenteExogena

PDF_PATH = ROOT / "documentos" / "exogena_ejemplo.pdf"


def _contribuyente_fake(anthropic_client, texto):
    return ContribuyenteExogena(
        nit="10203040-5",
        nombre="CARLOS MENDOZA",
        datos_fiscales=[
            {
                "concepto": "5001",
                "descripcion_concepto": "Salarios",
                "nit_informante": "890903938",
                "razon_social_informante": "BANCOLOMBIA S.A.",
                "valor_ingreso": 84_500_000.0,
                "valor_retencion": 3_200_000.0,
                "ano_gravable": 2025,
            }
        ],
    )


def test_procesar_pdf_end_to_end(monkeypatch):
    monkeypatch.setattr(main, "texto_a_estructura", _contribuyente_fake)
    monkeypatch.setattr(
        main,
        "generar_reporte_auditoria",
        lambda contribuyente, resultado, ano_gravable: "## Alertas de Coherencia\nOK\n",
    )
    monkeypatch.setattr(main, "guardar_reporte_contribuyente", lambda *a, **k: None)

    client = TestClient(main.app)
    with open(PDF_PATH, "rb") as f:
        respuesta = client.post(
            "/api/v1/procesar-pdf",
            files={"archivo": ("exogena_ejemplo.pdf", f.read(), "application/pdf")},
            data={
                "ano_gravable": "2025",
                "conceptos_ingresos_laborales": "5001",
                "num_dependientes": "2",
            },
        )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["ingresos_brutos_laborales"] == 84_500_000.0
    assert "Alertas de Coherencia" in cuerpo["reporte_auditoria"]


def test_procesar_pdf_rechaza_archivos_no_pdf():
    client = TestClient(main.app)
    respuesta = client.post(
        "/api/v1/procesar-pdf",
        files={"archivo": ("nota.txt", b"hola", "text/plain")},
        data={"ano_gravable": "2025", "conceptos_ingresos_laborales": "5001"},
    )
    assert respuesta.status_code == 400
