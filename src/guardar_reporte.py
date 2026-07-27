from __future__ import annotations

import os
from typing import Any

from supabase import Client, create_client


def _cliente_supabase(client: Client | None = None) -> Client:
    if client is not None:
        return client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL y SUPABASE_KEY deben estar definidas")
    return create_client(url, key)


def guardar_reporte_contribuyente(
    nit: str,
    nombre: str,
    resultado_motor_fiscal: dict[str, Any],
    reporte_auditoria_markdown: str,
    client: Client | None = None,
) -> dict[str, Any]:
    supabase = _cliente_supabase(client)
    registro = {
        "nit": nit,
        "nombre": nombre,
        "datos_fiscales": {
            "resultado_motor_fiscal": resultado_motor_fiscal,
            "reporte_auditoria_markdown": reporte_auditoria_markdown,
        },
    }
    respuesta = (
        supabase.table("contribuyentes_exogena")
        .upsert(registro, on_conflict="nit")
        .execute()
    )
    return respuesta.data
