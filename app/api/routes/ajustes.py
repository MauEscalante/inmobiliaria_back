from fastapi import APIRouter, Path, Query

from app.api.controllers.ajuste_controller import (
    ajustar_alquileres,
    get_historial_de_alquileres,
    listar_pendientes_de_ajuste,
)
from app.schemas.ajuste import AjusteAplicado, AjusteAplicar, AjustePendiente, TramoHistorial
from app.schemas.common import error_responses

router = APIRouter(prefix="/ajustes", tags=["ajustes"])


@router.get(
    "/pendientes",
    response_model=list[AjustePendiente],
    summary="Contratos a los que les toca ajuste en un período",
    response_description="Contratos que ajustan, con su alquiler vigente",
)
def listar_pendientes(
    mes: int = Query(..., ge=1, le=12, description="Mes de liquidación"),
    anio: int = Query(..., ge=2000, le=2100, description="Año de liquidación"),
):
    """Los mismos contratos que va a tocar POST /ajustes, con lo que muestra la grilla.

    Solo los de IPC: los contratos de ICL no los ajusta nadie todavía, así que no
    aparecen nunca acá.
    """
    return listar_pendientes_de_ajuste(mes, anio)


@router.post(
    "",
    response_model=AjusteAplicado,
    summary="Ajustar los alquileres de un período",
    response_description="Cuántos contratos ajustaron",
    responses=error_responses(409, 422),
)
def aplicar_ajuste(datos: AjusteAplicar):
    """Aplica el aumento del período abriendo el tramo nuevo de cada contrato.

    Ajusta **solo los alquileres**: no reescribe la planilla de recibos ni marca
    las propiedades como impagas, que es lo que hace de más el trabajo de Recibos.
    Por eso responde en el request y no encola nada.

    Repetirlo no vuelve a aumentar: el contrato que ya tiene el tramo del período
    se saltea y no cuenta en `contratos_ajustados`. Devuelve 409 si hay un ajuste
    de recibos en curso.
    """
    return ajustar_alquileres(datos.mes, datos.anio)


@router.get(
    "/{contrato_id}/historial",
    response_model=list[TramoHistorial],
    summary="Historial de alquileres de un contrato",
    responses=error_responses(404),
)
def listar_historial(
    contrato_id: str = Path(..., description="Identificador del contrato"),
):
    """Los tramos de valor_historico, del más viejo al más nuevo.

    Cada ajuste cierra el tramo anterior y abre uno, así que la lista es la
    historia del alquiler del contrato.
    """
    return get_historial_de_alquileres(contrato_id)
