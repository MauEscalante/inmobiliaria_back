from fastapi import APIRouter, Depends, Path, Query

from app.api.controllers.cliente_controller import (
    get_all_clientes,
    get_cliente,
    patch_cliente_parcial,
    update_cliente_completo,
)
from app.schemas.cliente import ClientePatch, ClienteRead, ClienteTipoDerivado, ClienteUpdate
from app.schemas.common import Page, error_responses
from app.utils.helpers import Paginacion

# No hay alta de clientes: se crean solos al registrar un contrato (inquilino)
# o una propiedad (propietario).
router = APIRouter(prefix="/clientes", tags=["clientes"])


@router.get(
    "",
    response_model=Page[ClienteRead],
    summary="Listar clientes",
    response_description="Página de clientes",
)
def listar_clientes(
    paginacion: Paginacion = Depends(),
    tipo: ClienteTipoDerivado | None = Query(
        None,
        description="Filtra por rol. 'Propietario' e 'Inquilino' incluyen a los que son ambos.",
    ),
    q: str | None = Query(
        None, max_length=100, description="Busca en nombre, apellido, DNI y email"
    ),
):
    """Colección de clientes, paginada y filtrable.

    Con `?tipo=Propietario` reemplaza al viejo endpoint `/propietarios`, que era
    esta misma colección con el filtro fijo en la URL.
    """
    items, total = get_all_clientes(
        tipo.value if tipo else None, q, paginacion.limit, paginacion.offset
    )
    return Page.crear(items, total, paginacion.page, paginacion.page_size)


@router.get(
    "/{cliente_num}",
    response_model=ClienteRead,
    summary="Obtener un cliente",
    responses=error_responses(404),
)
def obtener_cliente(cliente_num: int = Path(..., description="Identificador del cliente")):
    return get_cliente(cliente_num)


@router.put(
    "/{cliente_num}",
    response_model=ClienteRead,
    summary="Reemplazar un cliente",
    responses=error_responses(404, 409, 422),
)
def reemplazar_cliente(
    datos: ClienteUpdate,
    cliente_num: int = Path(..., description="Identificador del cliente"),
):
    """Reemplazo total: todos los campos editables viajan en el body."""
    return update_cliente_completo(cliente_num, datos.model_dump())


@router.patch(
    "/{cliente_num}",
    response_model=ClienteRead,
    summary="Actualizar campos de un cliente",
    responses=error_responses(404, 409, 422),
)
def actualizar_cliente(
    datos: ClientePatch,
    cliente_num: int = Path(..., description="Identificador del cliente"),
):
    """Actualización parcial: solo se tocan los campos presentes en el body.

    Reemplaza a `PUT /clientes/email/{id}` y `PUT /clientes/telefono/{id}`, que
    mandaban el valor nuevo por query string.
    """
    return patch_cliente_parcial(cliente_num, datos.model_dump(exclude_unset=True))
