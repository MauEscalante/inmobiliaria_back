from fastapi import APIRouter, Depends, Path, Query, Response, status

from app.api.controllers.libro_diario_controller import (
    create_new_movimiento,
    eliminar_movimiento,
    get_libro_diario,
    get_movimiento,
)
from app.config import settings
from app.models.libro_diario import TipoMovimiento
from app.schemas.common import Page, error_responses
from app.schemas.movimiento import MovimientoCreate, MovimientoRead
from app.utils.helpers import Paginacion

# El recurso son los movimientos, no el libro: el libro es la vista de reportes
# que vive en /caja. El prefijo viejo /libroDiario además iba en camelCase.
router = APIRouter(prefix="/movimientos", tags=["movimientos"])


@router.get(
    "",
    response_model=Page[MovimientoRead],
    summary="Listar movimientos",
    response_description="Página de movimientos",
)
def listar_movimientos(
    paginacion: Paginacion = Depends(),
    anio: int | None = Query(None, ge=1900, le=2100, description="Año del movimiento"),
    mes: int | None = Query(None, ge=1, le=12, description="Mes del movimiento"),
    tipo: list[TipoMovimiento] | None = Query(
        None, description="Se puede repetir: ?tipo=INGRESO&tipo=DEPOSITO"
    ),
    sort: str | None = Query(
        None,
        description=(
            "Campo de orden: fecha, monto o movimiento_id. "
            "Con '-' adelante es descendente."
        ),
    ),
):
    """Colección de movimientos, filtrable por período y por tipo.

    Reemplaza a `/libroDiario/{anio}/{mes}` y a `/libroDiario/retiros/{anio}/{mes}`,
    que era este mismo listado con `tipo = RETIRO` fijo en la URL. Ahora los cuatro
    tipos se pueden pedir igual.
    """
    items, total = get_libro_diario(
        anio,
        mes,
        [t.value for t in tipo] if tipo else None,
        sort,
        paginacion.limit,
        paginacion.offset,
    )
    return Page.crear(items, total, paginacion.page, paginacion.page_size)


@router.post(
    "",
    response_model=MovimientoRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un movimiento",
    responses=error_responses(422),
)
def crear_movimiento(datos: MovimientoCreate, response: Response):
    """Registra el movimiento y, en ingresos y depósitos, marca la propiedad como abonada."""
    movimiento = create_new_movimiento(datos.model_dump())
    movimiento_id = movimiento["movimiento_id"]
    response.headers["Location"] = f"{settings.API_PREFIX}/movimientos/{movimiento_id}"
    return movimiento


@router.get(
    "/{movimiento_id}",
    response_model=MovimientoRead,
    summary="Obtener un movimiento",
    responses=error_responses(404),
)
def obtener_movimiento(movimiento_id: int = Path(..., description="Identificador del movimiento")):
    return get_movimiento(movimiento_id)


@router.delete(
    "/{movimiento_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un movimiento",
    responses=error_responses(404),
)
def borrar_movimiento(movimiento_id: int = Path(..., description="Identificador del movimiento")):
    eliminar_movimiento(movimiento_id)
