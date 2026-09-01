import logging
from datetime import date
from decimal import Decimal

from app.api.errors import raise_conflict
from app.api.services import ajuste_service
from app.api.services.libro_diario_service import marcar_todas_adeuda
from app.api.services.recibo_service import (
    actualizar_fechas,
    actualizar_importe,
    cargar_planilla,
    factor_ipc,
    get_ipc,
    get_propiedades_ajustar,
    nombres_de_hojas,
)
from app.api.services.valor_historico_service import aplicar_ajuste_del_periodo
from app.config import settings

logger = logging.getLogger(__name__)


def get_recibos_ajustar(mes_liquidacion: int, anio_liquidacion: int) -> list:
    return get_propiedades_ajustar(mes_liquidacion, anio_liquidacion)


def get_hojas_planilla() -> dict:
    """Resumen de la planilla de recibos.

    El handler viejo leía una variable `wb` que no existía en el módulo, así que
    este endpoint tiraba NameError -> 500 en cada llamada.
    """
    hojas = nombres_de_hojas()
    return {"cantidad_hojas": len(hojas), "hojas": hojas}


def ruta_planilla() -> str:
    return settings.RECIBOS_TEMPLATE


def actualizar_recibos(mes_liquidacion: int, anio_liquidacion: int) -> dict:
    """Ajusta la planilla del período y arranca el período nuevo.

    Devuelve el resumen de lo que tocó, para que el POST tenga una representación
    que mostrar en vez de responder null.
    """
    contratos_a_ajustar = get_propiedades_ajustar(mes_liquidacion, anio_liquidacion)

    # El ajuste se guarda en valor_historico ANTES de tocar la planilla, y el recibo
    # se escribe con el número que quedó en la base. Así el alquiler vigente vive en
    # la base —de donde lo leen el próximo re-ajuste y la penalidad por rescisión— y
    # no solo en el Excel. Es idempotente: repetir el período no vuelve a ajustar.
    importes = aplicar_ajuste_del_periodo(
        contratos_a_ajustar,
        date(anio_liquidacion, mes_liquidacion, 1),
        factor_ipc(get_ipc()) if contratos_a_ajustar else Decimal("1"),
    )

    # OJO: se compara el nombre de la hoja contra el contrato_id. Antes se comparaba
    # un str contra una lista de dicts, condición que nunca podía ser verdadera, así
    # que el ajuste no se ejecutaba nunca. Si las hojas no se llaman como el
    # contrato, este match sigue sin dar y hay que definir la convención de nombres.
    wb = cargar_planilla()
    ajustados = 0
    for recibo in wb.sheetnames:
        actualizar_fechas(recibo, mes_liquidacion, anio_liquidacion, wb)

        if recibo in importes:
            actualizar_importe(recibo, wb, importes[recibo])
            ajustados += 1

    wb.save(settings.RECIBOS_TEMPLATE)

    # Empieza un período nuevo: lo cobrado el mes pasado ya no cuenta.
    marcadas = marcar_todas_adeuda()

    return {
        "mes": mes_liquidacion,
        "anio": anio_liquidacion,
        "contratos_ajustados": ajustados,
        "propiedades_marcadas_adeuda": marcadas,
    }


def solicitar_ajuste(mes_liquidacion: int, anio_liquidacion: int) -> dict:
    """Encola un ajuste y devuelve el trabajo recien creado.

    Rechaza el pedido si ya hay uno corriendo: la planilla es un unico archivo y
    dos ejecuciones en paralelo la dejarian inconsistente.
    """
    if ajuste_service.hay_activo():
        raise_conflict(
            "Ya hay un ajuste de recibos en curso. Esperá a que termine.",
            code="ajuste_en_curso",
        )
    return ajuste_service.crear(mes_liquidacion, anio_liquidacion)


def ejecutar_ajuste(ajuste_id: int, mes_liquidacion: int, anio_liquidacion: int) -> None:
    """Corre el ajuste en segundo plano y deja registrado como termino.

    Atrapa cualquier excepcion a proposito: no hay ningun request esperando esta
    funcion, asi que un error que se escape no lo veria nadie y el trabajo quedaria
    colgado en 'en_proceso', bloqueando todos los ajustes siguientes.
    """
    try:
        ajuste_service.marcar_en_proceso(ajuste_id)
        resultado = actualizar_recibos(mes_liquidacion, anio_liquidacion)
        ajuste_service.marcar_completado(ajuste_id, resultado)
    except Exception as e:
        logger.exception("Fallo el ajuste de recibos %s", ajuste_id)
        try:
            ajuste_service.marcar_fallido(ajuste_id, f"{type(e).__name__}: {e}")
        except Exception:
            # Si tampoco se puede escribir el fallo, al menos queda en el log.
            logger.exception("No se pudo registrar el fallo del ajuste %s", ajuste_id)
