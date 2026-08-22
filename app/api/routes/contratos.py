from fastapi import APIRouter, Depends, Path, Query, Response, status

from app.api.controllers.contrato_controller import (
    calcular_rescision,
    cancelar_rescision,
    cerrar_por_entrega_llaves,
    create_contrato,
    delete_contrato,
    get_all_contratos,
    get_contrato_detail,
    get_garantes,
    get_inquilinos,
    registrar_rescision,
)
from app.config import settings
from app.models.contrato import EstadoContrato
from app.schemas.common import Page, error_responses
from app.schemas.contrato import (
    ContratoCreate,
    ContratoDetalle,
    ContratoRead,
    EntregaLlavesCreate,
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
    summary="Registrar el aviso de rescisión de un contrato",
    response_description="La estimación de la penalidad al momento del aviso",
    responses=error_responses(404, 409, 422),
)
def registrar_rescision_endpoint(
    datos: RescisionCreate,
    contrato_id: str = Path(..., description="Identificador del contrato"),
):
    """Anota que el inquilino se va tal mes. NO cierra el contrato.

    El contrato queda Activo con `fecha_rescision` cargada: ese mes lo paga, y tiene
    que seguir liquidando y ajustando como cualquier otro. La penalidad se calcula
    recién al cerrar por entrega de llaves, cuando el alquiler del mes de salida ya
    se conoce; hasta entonces el número que devuelve este endpoint es una estimación
    sobre el último importe cargado.
    """
    return registrar_rescision(contrato_id, datos.anio, datos.mes)


@router.post(
    "/{contrato_id}/entrega-llaves",
    response_model=RescisionCalculo,
    summary="Cerrar la rescisión con la entrega de llaves",
    response_description="El cálculo definitivo que quedó guardado en el contrato",
    responses=error_responses(404, 409, 422),
)
def entregar_llaves_endpoint(
    datos: EntregaLlavesCreate,
    contrato_id: str = Path(..., description="Identificador del contrato"),
):
    """Deja el contrato en Rescindido con la penalidad definitiva.

    Manda el mes de la entrega, no el que se avisó. Si ese mes todavía no tiene su
    importe en `valor_historico` responde 422 con `importe_del_mes_desconocido`, y hay
    que reintentar mandando `importe_alquiler`: es preferible pedir el dato a congelar
    una penalidad sobre un alquiler viejo.

    La penalidad queda registrada pero no se cobra: el ingreso se carga aparte desde
    el libro diario, cuando la plata entra de verdad.
    """
    return cerrar_por_entrega_llaves(contrato_id, datos.fecha_entrega, datos.importe_alquiler)


@router.delete(
    "/{contrato_id}/rescision",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancelar el aviso de rescisión",
    responses=error_responses(404, 409),
)
def cancelar_rescision_endpoint(
    contrato_id: str = Path(..., description="Identificador del contrato"),
):
    """Borra un aviso mal cargado. No sirve sobre un contrato ya cerrado."""
    cancelar_rescision(contrato_id)


@router.delete(
    "/{contrato_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un contrato",
    responses=error_responses(404),
)
def eliminar_contrato(contrato_id: str = Path(..., description="Identificador del contrato")):
    delete_contrato(contrato_id)
