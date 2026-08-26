import os

from fastapi import APIRouter, BackgroundTasks, Path, Query, Response, status
from fastapi.responses import FileResponse

from app.api.controllers.recibo_controller import (
    ejecutar_ajuste,
    get_hojas_planilla,
    get_recibos_ajustar,
    ruta_planilla,
    solicitar_ajuste,
)
from app.api.errors import raise_not_found
from app.api.services.ajuste_service import get_by_id as get_ajuste
from app.config import settings
from app.schemas.common import error_responses
from app.schemas.recibo import AjusteCreate, AjusteRead, ContratoAAjustar, PlanillaResumen

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

router = APIRouter(prefix="/recibos", tags=["recibos"])


@router.get(
    "",
    response_model=PlanillaResumen,
    summary="Resumen de la planilla de recibos",
)
def obtener_planilla():
    """Hojas que tiene hoy la planilla.

    El handler viejo leía una variable `wb` inexistente, así que respondía 500 en
    cada llamada.
    """
    return get_hojas_planilla()


@router.get(
    "/archivo",
    summary="Descargar la planilla de recibos",
    response_class=FileResponse,
    responses=error_responses(404),
)
def descargar_planilla():
    """Devuelve el .xlsx como adjunto, en vez de dejarlo solo en el disco del servidor."""
    ruta = ruta_planilla()
    if not os.path.exists(ruta):
        raise_not_found("Planilla de recibos", ruta, femenino=True)

    return FileResponse(
        ruta,
        media_type=XLSX_MEDIA_TYPE,
        filename=os.path.basename(ruta),
    )


@router.get(
    "/pendientes",
    response_model=list[ContratoAAjustar],
    summary="Contratos con ajuste pendiente en un período",
)
def listar_pendientes(
    mes: int = Query(..., ge=1, le=12, description="Mes de liquidación"),
    anio: int = Query(..., ge=1900, le=2100, description="Año de liquidación"),
):
    """Reemplaza a `GET /recibos/ajustar/{mes}/{anio}`.

    El período pasa a ser un filtro y no un identificador, y ahora se valida: antes
    `mes` y `anio` eran dos enteros en el path y un llamado con el orden invertido
    se aceptaba sin chistar.
    """
    return get_recibos_ajustar(mes, anio)


@router.post(
    "/ajustes",
    response_model=AjusteRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Encolar el ajuste de recibos de un período",
    responses=error_responses(409, 422),
)
def crear_ajuste(datos: AjusteCreate, background: BackgroundTasks, response: Response):
    """Encola el ajuste y devuelve el trabajo, sin esperar a que termine.

    Ajustar la planilla tarda más de un minuto (openpyxl parsea las 120 hojas) y
    además consulta el IPC contra un servicio externo. Resolverlo dentro del
    request dejaba al cliente sin saber qué pasó si la conexión se cortaba, y la
    operación no es inocua: reescribe la planilla y marca todas las propiedades
    como impagas.

    Responde 202 con el trabajo en estado `pendiente`; el progreso se consulta en
    la URL del header `Location`. Devuelve 409 si ya hay un ajuste en curso.
    """
    ajuste = solicitar_ajuste(datos.mes, datos.anio)
    background.add_task(ejecutar_ajuste, ajuste["ajuste_id"], datos.mes, datos.anio)
    response.headers["Location"] = f"{settings.API_PREFIX}/recibos/ajustes/{ajuste['ajuste_id']}"
    return ajuste


@router.get(
    "/ajustes/{ajuste_id}",
    response_model=AjusteRead,
    summary="Estado de un ajuste de recibos",
    responses=error_responses(404),
)
def obtener_ajuste(ajuste_id: int = Path(..., description="Identificador del ajuste")):
    """Estado del trabajo: `pendiente`, `en_proceso`, `completado` o `fallido`.

    Al completarse trae los contadores; si falló, el motivo en `error`.
    """
    ajuste = get_ajuste(ajuste_id)
    if not ajuste:
        raise_not_found("Ajuste", ajuste_id)
    return ajuste
