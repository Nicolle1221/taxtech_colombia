import json
import os
import sys
from pathlib import Path

from anthropic import Anthropic
from pydantic import BaseModel
from pypdf import PdfReader
from supabase import create_client

PDF_PATH = Path("documentos/exogena_ejemplo.pdf")
MODEL = "claude-sonnet-5"


class DatoFiscal(BaseModel):
    concepto: str
    descripcion_concepto: str
    nit_informante: str
    razon_social_informante: str
    valor_ingreso: float
    valor_retencion: float
    ano_gravable: int


class ContribuyenteExogena(BaseModel):
    nit: str
    nombre: str
    datos_fiscales: list[DatoFiscal]


def extraer_texto_pdf(ruta: Path) -> str:
    reader = PdfReader(str(ruta))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def texto_a_estructura(client: Anthropic, texto: str) -> ContribuyenteExogena:
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        tools=[
            {
                "name": "registrar_contribuyente_exogena",
                "description": "Registra los datos estructurados de información exógena de un contribuyente.",
                "input_schema": ContribuyenteExogena.model_json_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": "registrar_contribuyente_exogena"},
        messages=[
            {
                "role": "user",
                "content": (
                    "Extrae la información exógena estructurada del siguiente texto "
                    f"proveniente de un reporte DIAN:\n\n{texto}"
                ),
            }
        ],
    )
    for block in response.content:
        if block.type == "tool_use":
            return ContribuyenteExogena.model_validate(block.input)
    raise RuntimeError("El modelo no devolvió una respuesta estructurada")


def guardar_en_supabase(datos: ContribuyenteExogena) -> None:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL y SUPABASE_KEY deben estar definidas")
    client = create_client(url, key)
    client.table("contribuyentes_exogena").insert(
        json.loads(datos.model_dump_json())
    ).execute()


def main() -> None:
    if not PDF_PATH.exists():
        print(f"ERROR: no se encontró {PDF_PATH}", file=sys.stderr)
        sys.exit(1)

    texto = extraer_texto_pdf(PDF_PATH)
    client = Anthropic()
    datos = texto_a_estructura(client, texto)
    guardar_en_supabase(datos)
    print(f"OK: contribuyente {datos.nit} guardado en contribuyentes_exogena")


if __name__ == "__main__":
    main()
