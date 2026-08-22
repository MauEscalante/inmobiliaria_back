from fastapi import APIRouter, Depends, Query

from app.api.controllers.evento_controller import get_all_eventos
from app.schemas.common import Page
from app.schemas.evento import EventoRead
from app.utils.helpers import Paginacion

router = APIRouter(prefix="/eventos", tags=["eventos"])

# Tope de la ventana. Es una bitácora para el panel de actividad reciente, no un
# historial de auditoría: pedir un año entero no es un caso de uso.
DIAS_MAX = 90


@router.get(
    "",
    response_model=Page[EventoRead],
    summary="Listar la actividad reciente",
    response_description="Página de eventos, del más nuevo al más viejo",
)
def listar_eventos(
    paginacion: Paginacion = Depends(),
    dias: int = Query(7, ge=1, le=DIAS_MAX, description="Ventana hacia atrás, en días"),
):
    """Altas registradas en los últimos `dias`.

    La tabla arranca vacía y se llena a medida que se opera: no hay bitácora de
    lo cargado antes de que existiera, porque las tablas no guardan fecha de alta.
    """
    items, total = get_all_eventos(dias, paginacion.limit, paginacion.offset)
    return Page.crear(items, total, paginacion.page, paginacion.page_size)
