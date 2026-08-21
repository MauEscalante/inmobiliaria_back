from fastapi import APIRouter, Depends, Path, Query, Response, status

from app.api.controllers.propiedades_controller import (
    create_new_propiedad,
    delete_propiedad,
    get_all_propiedades,
    get_propiedad_by_id,
    get_propietarios,
    patch_propiedad,
    update_propiedad,
)
from app.config import settings
from app.models.propiedad import EstadoAlquiler, EstadoPropiedad
from app.schemas.common import Page, error_responses
from app.schemas.propiedad import (
    PropiedadCreate,
    PropiedadDetalle,
    PropiedadPatch,
    PropiedadRead,
    PropiedadUpdate,
    PropietarioDetalle,
)
from app.utils.helpers import Paginacion

router = APIRouter(prefix="/propiedades", tags=["propiedades"])


@router.get(
    "",
    response_model=Page[PropiedadRead],
    summary="Listar propiedades",
    response_description="Página de propiedades",
)
def listar_propiedades(
    paginacion: Paginacion = Depends(),
    estado: EstadoPropiedad | None = Query(None, description="Activa o Inactiva"),
    estado_alquiler: EstadoAlquiler | None = Query(None, description="Abono o Adeuda"),
    q: str | None = Query(None, max_length=100, description="Busca en la dirección"),
):
    items, total = get_all_propiedades(
        estado.value if estado else None,
        estado_alquiler.value if estado_alquiler else None,
        q,
        paginacion.limit,
        paginacion.offset,
    )
    return Page.crear(items, total, paginacion.page, paginacion.page_size)


@router.post(
    "",
    response_model=PropiedadDetalle,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una propiedad",
    responses=error_responses(422),
)
def crear_propiedad(datos: PropiedadCreate, response: Response):
    """Crea la propiedad y sus propietarios en la misma transacción.

    Los propietarios que todavía no son clientes se dan de alta acá.
    """
    propiedad = create_new_propiedad(datos.model_dump())
    response.headers["Location"] = f"{settings.API_PREFIX}/propiedades/{propiedad['propiedad_id']}"
    return propiedad


@router.get(
    "/{propiedad_id}",
    response_model=PropiedadDetalle,
    summary="Obtener una propiedad",
    responses=error_responses(404),
)
def obtener_propiedad(propiedad_id: int = Path(..., description="Identificador de la propiedad")):
    return get_propiedad_by_id(propiedad_id)


@router.get(
    "/{propiedad_id}/propietarios",
    response_model=list[PropietarioDetalle],
    summary="Listar los propietarios de una propiedad",
    responses=error_responses(404),
)
def listar_propietarios(propiedad_id: int = Path(..., description="Identificador de la propiedad")):
    """Sub-recurso con la asociación propiedad-propietario y su porcentaje."""
    return get_propietarios(propiedad_id)


@router.put(
    "/{propiedad_id}",
    response_model=PropiedadDetalle,
    summary="Reemplazar una propiedad",
    responses=error_responses(404, 422),
)
def reemplazar_propiedad(
    datos: PropiedadUpdate,
    propiedad_id: int = Path(..., description="Identificador de la propiedad"),
):
    """Reemplazo total. No toca propietarios ni comisión."""
    return update_propiedad(propiedad_id, datos.model_dump())


@router.patch(
    "/{propiedad_id}",
    response_model=PropiedadDetalle,
    summary="Actualizar campos de una propiedad",
    responses=error_responses(404, 422),
)
def actualizar_propiedad(
    datos: PropiedadPatch,
    propiedad_id: int = Path(..., description="Identificador de la propiedad"),
):
    """Reemplaza a `/update/direccion/{id}` y `/update/estado/{id}`, que mandaban
    el valor por query string y aceptaban cualquier string como estado."""
    return patch_propiedad(propiedad_id, datos.model_dump(exclude_unset=True))


@router.delete(
    "/{propiedad_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una propiedad",
    responses=error_responses(404, 409),
)
def eliminar_propiedad(propiedad_id: int = Path(..., description="Identificador de la propiedad")):
    """Devuelve 409 si la propiedad tiene contratos asociados."""
    delete_propiedad(propiedad_id)
