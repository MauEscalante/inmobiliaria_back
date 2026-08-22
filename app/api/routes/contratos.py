from fastapi import APIRouter, Depends, Path, Query, Response, status

from app.api.controllers.contrato_controller import (
    calcular_rescision,
    create_contrato,
    delete_contrato,
    get_all_contratos,
    get_contrato_detail,
    get_garantes,
    get_inquilinos,
    rescindir,
)
from app.config import settings
from app.models.contrato import EstadoContrato
from app.schemas.common import Page, error_responses
from app.schemas.contrato import (
    ContratoCreate,
    ContratoDetalle,
    ContratoRead,
    InquilinoRead,
    RescisionCalculo,
    RescisionCreate,
)
from app.schemas.garante import GaranteRead
from app.utils.helpers import Paginacion

router = APIRouter(prefix="/contratos", tags=["contratos"])


@router.get(
    "",
    response_model=Page[ContratoRead],
    summary="Listar contratos",
    response_description="Página de contratos",
)
def listar_contratos(
    paginacion: Paginacion = Depends(),
    estado: EstadoContrato | None = Query(None, description="Activo, Inactivo o Rescindido"),
    propiedad_id: int | None = Query(None, description="Contratos de una propiedad"),
):
    items, total = get_all_contratos(
        estado.value if estado else None, propiedad_id, paginacion.limit, paginacion.offset
    )
    return Page.crear(items, total, paginacion.page, paginacion.page_size)


@router.post(
    "",
    response_model=ContratoRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un contrato",
    responses=error_responses(422),
)
def crear_contrato(datos: ContratoCreate, response: Response):
    """Crea el contrato con sus inquilinos y garantes en la misma transacción.

    Los inquilinos que todavía no son clientes se dan de alta acá; si el DNI ya
    existe se reusa ese cliente.
    """
    contrato = create_contrato(datos.model_dump())
    response.headers["Location"] = f"{settings.API_PREFIX}/contratos/{contrato.contrato_id}"
    return contrato


@router.get(
    "/{contrato_id}",
    response_model=ContratoDetalle,
    summary="Obtener un contrato",
    responses=error_responses(404),
)
def obtener_contrato(
    contrato_id: str = Path(..., description="Identificador del contrato, p. ej. 000001"),
):
    """El contrato_id es un varchar con ceros a la izquierda, no un entero."""
    return get_contrato_detail(contrato_id)


@router.get(
    "/{contrato_id}/inquilinos",
    response_model=list[InquilinoRead],
    summary="Listar los inquilinos de un contrato",
    responses=error_responses(404),
)
def listar_inquilinos(contrato_id: str = Path(..., description="Identificador del contrato")):
    return get_inquilinos(contrato_id)


@router.get(
    "/{contrato_id}/garantes",
    response_model=list[GaranteRead],
    summary="Listar los garantes de un contrato",
    responses=error_responses(404),
)
def listar_garantes(contrato_id: str = Path(..., description="Identificador del contrato")):
    """Vacío cuando la garantía es GPremier, que por definición no lleva garantes."""
    return get_garantes(contrato_id)


@router.get(
    "/{contrato_id}/rescision",
    response_model=RescisionCalculo,
    summary="Calcular la rescisión de un contrato",
    response_description="Penalidad que corresponde si el inquilino se va ese mes",
    responses=error_responses(404, 409, 422),
)
def calcular_rescision_contrato(
    contrato_id: str = Path(..., description="Identificador del contrato"),
    anio: int = Query(..., ge=2000, le=2100, description="Año en que se va el inquilino"),
    mes: int = Query(..., ge=1, le=12, description="Mes en que se va el inquilino"),
):
    """Simula la rescisión sin persistir nada, para mostrar el número antes de confirmar.

    El día dentro del mes es indistinto: el inquilino paga el mes completo, así que
    la salida se toma siempre al cierre del mes elegido.
    """
    return calcular_rescision(contrato_id, anio, mes)


@router.post(
    "/{contrato_id}/rescision",
    response_model=RescisionCalculo,
    summary="Rescindir un contrato",
    response_description="El cálculo que quedó guardado en el contrato",
    responses=error_responses(404, 409, 422),
)
def rescindir_contrato_endpoint(
    datos: RescisionCreate,
    contrato_id: str = Path(..., description="Identificador del contrato"),
):
    """Deja el contrato en estado Rescindido con la fecha de salida y la penalidad.

    Recalcula del lado del servidor en vez de confiar en el monto que vio el cliente.
    La penalidad queda registrada pero no se cobra: el ingreso se carga aparte desde
    el libro diario, cuando la plata entra de verdad.
    """
    return rescindir(contrato_id, datos.anio, datos.mes)


@router.delete(
    "/{contrato_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un contrato",
    responses=error_responses(404),
)
def eliminar_contrato(contrato_id: str = Path(..., description="Identificador del contrato")):
    delete_contrato(contrato_id)
