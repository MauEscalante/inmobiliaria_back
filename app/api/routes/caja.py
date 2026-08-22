from fastapi import APIRouter, Depends, Query

from app.api.controllers.libro_diario_controller import get_estado_caja, get_historial
from app.schemas.common import Page
from app.schemas.movimiento import IngresoMensual, ResumenCaja
from app.utils.helpers import Paginacion

# Reportes derivados del libro diario. Van aparte de /movimientos porque son
# proyecciones calculadas, no filas direccionables: así 'resumen' e 'historial'
# dejan de ocupar el lugar del identificador, como pasaba en /libroDiario/resumen/...
router = APIRouter(prefix="/caja", tags=["caja"])


@router.get(
    "/resumen",
    response_model=ResumenCaja,
    summary="Estado de la caja de un mes",
)
def obtener_resumen(
    anio: int = Query(..., ge=1900, le=2100, description="Año del período"),
    mes: int = Query(..., ge=1, le=12, description="Mes del período"),
):
    """En la caja hay solo efectivo: las transferencias se informan aparte."""
    return get_estado_caja(anio, mes)


@router.get(
    "/historial",
    response_model=Page[IngresoMensual],
    summary="Historial de ingresos por mes",
)
def obtener_historial(paginacion: Paginacion = Depends()):
    """Total de ingresos agrupado por mes.

    Antes vivía en `GET /libroDiario/`, donde la colección devolvía un recurso
    distinto al de `GET /libroDiario/{anio}/{mes}`.
    """
    items, total = get_historial(paginacion.limit, paginacion.offset)
    return Page.crear(items, total, paginacion.page, paginacion.page_size)
