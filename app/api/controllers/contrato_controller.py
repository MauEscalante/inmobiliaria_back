from calendar import monthrange
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.api.errors import raise_conflict, raise_not_found, raise_unprocessable
from app.api.services.contrato_services import (
    cancelar_aviso_rescision,
    cerrar_rescision,
    crear_contrato,
    eliminar_contrato,
    existe_contrato,
    get_contrato_by_id,
    get_contrato_detalle,
    get_contratos,
    get_garantes_de_contrato,
    get_inquilinos_de_contrato,
    registrar_aviso_rescision,
)
from app.api.services.propiedades_services import get_inmueble_by_id
from app.api.services.valor_historico_service import get_importe_vigente_del_mes
from app.models.contrato import EstadoContrato

# Lo que se cobra al inquilino que se va antes de tiempo: el 10% de lo que
# quedaba por pagar hasta el final del contrato.
PORCENTAJE_PENALIDAD = Decimal("0.10")

# Meses hacia adelante que se aceptan como mes de salida, contando desde el actual.
# Más allá del mes que viene el importe sería pura proyección: ni siquiera existe el
# índice con el que se ajustaría.
MESES_VENTANA_SALIDA = 1


def get_all_contratos(estado: str | None, propiedad_id: int | None, limit: int, offset: int):
    return get_contratos(estado, propiedad_id, limit, offset)


def get_contrato_detail(contrato_id: str):
    """Antes devolvía 200 null cuando el contrato no existía."""
    contrato = get_contrato_detalle(contrato_id)
    if not contrato:
        raise_not_found("Contrato", contrato_id)
    return contrato


def get_inquilinos(contrato_id: str):
    if not existe_contrato(contrato_id):
        raise_not_found("Contrato", contrato_id)
    return get_inquilinos_de_contrato(contrato_id)


def get_garantes(contrato_id: str):
    if not existe_contrato(contrato_id):
        raise_not_found("Contrato", contrato_id)
    return get_garantes_de_contrato(contrato_id)


def create_contrato(contrato_data: dict):
    # La propiedad referenciada tiene que existir: es un dato del body inválido,
    # o sea 422, no un 404 (la colección /contratos sí existe).
    if not get_inmueble_by_id(contrato_data.get("propiedad")):
        raise_unprocessable(
            f"No existe la propiedad {contrato_data.get('propiedad')}",
            field="propiedad",
            code="referencia_inexistente",
        )
    return crear_contrato(contrato_data)


def delete_contrato(contrato_id: str) -> None:
    """Antes db.delete(None) tiraba un 500 cuando el id no existía."""
    if not eliminar_contrato(contrato_id):
        raise_not_found("Contrato", contrato_id)


def _mes_limite() -> tuple[int, int]:
    """Último (año, mes) que se acepta como salida: el que viene."""
    hoy = date.today()
    mes = hoy.month + MESES_VENTANA_SALIDA
    return (hoy.year + (mes - 1) // 12, (mes - 1) % 12 + 1)


def _validar_ventana_de_aviso(anio: int, mes: int) -> None:
    """El aviso solo se registra para el mes actual o el siguiente.

    No es una regla del cálculo sino del aviso: la entrega de llaves se carga unos
    días después de ocurrida y su mes puede ser el que recién cerró, así que el
    preview tiene que poder calcular ese mes igual.
    """
    hoy = date.today()
    if (anio, mes) < (hoy.year, hoy.month):
        # Un mes ya cerrado tiene los recibos emitidos y se calculó sobre otro escenario.
        raise_unprocessable(
            "No se puede rescindir en un mes ya cerrado: elegí el mes actual o el siguiente",
            field="mes",
            code="salida_antes_del_mes_actual",
        )

    limite = _mes_limite()
    if (anio, mes) > limite:
        raise_unprocessable(
            f"Solo se puede rescindir hasta {limite[1]:02d}/{limite[0]}, "
            "el mes siguiente al actual",
            field="mes",
            code="salida_fuera_de_ventana",
        )


def calcular_rescision(contrato_id: str, anio: int, mes: int) -> dict:
    """Cuánto sale irse en un mes dado, sin tocar nada.

    La fecha exacta de salida dentro del mes es indistinta: el inquilino paga el
    mes entero se vaya el 1 o el 30, así que la salida se toma siempre al cierre
    del mes elegido.
    """
    contrato = get_contrato_by_id(contrato_id)
    if not contrato:
        raise_not_found("Contrato", contrato_id)

    if contrato.estado != EstadoContrato.Activo:
        # Conflicto con el estado actual del recurso, igual que el candado de
        # ajustes en recibo_controller: 409, no 422.
        raise_conflict(
            f"El contrato {contrato_id} no está activo: su estado es {contrato.estado.value}",
            field="estado",
            code="contrato_no_activo",
        )

    if (anio, mes) < (contrato.fecha_inicio.year, contrato.fecha_inicio.month):
        raise_unprocessable(
            "El mes de salida no puede ser anterior al inicio del contrato",
            field="mes",
            code="salida_antes_del_inicio",
        )

    fecha_salida = date(anio, mes, monthrange(anio, mes)[1])

    # Meses calendario que quedaban por pagar después de la salida. Irse en el mes
    # de fecha_fin da 0: llegó a término y no hay penalidad. Irse después también
    # da 0, de ahí el max().
    meses_restantes = max(
        0, (contrato.fecha_fin.year - anio) * 12 + (contrato.fecha_fin.month - mes)
    )

    tramo = get_importe_vigente_del_mes(contrato_id, fecha_salida)
    if tramo is None:
        # No debería pasar: el alta siembra el tramo inicial y la migración
        # backfillea los contratos viejos. Preferible cortar acá antes que calcular
        # la penalidad sobre un importe inventado.
        raise_unprocessable(
            f"No hay un importe registrado para {mes:02d}/{anio} en el contrato {contrato_id}",
            field="mes",
            code="sin_importe_vigente",
        )

    return _armar_calculo(contrato, fecha_salida, meses_restantes, tramo)


def _armar_calculo(contrato, fecha_salida, meses_restantes, tramo, importe_manual=None):
    """Penalidad a partir de un tramo de valor_historico.

    `importe_manual` pisa el tramo: lo usa el cierre por entrega de llaves cuando el
    mes no está liquidado y el operador carga el alquiler a mano.
    """
    # El tramo arrastrado no es el valor del mes: es el último que se conoce.
    estimado = tramo["fecha_fin"] < fecha_salida
    importe = Decimal(importe_manual) if importe_manual is not None else tramo["importe_inicial"]

    penalidad = (importe * meses_restantes * PORCENTAJE_PENALIDAD).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    propiedad = get_inmueble_by_id(contrato.propiedad)

    return {
        "contrato_id": contrato.contrato_id,
        "direccion": propiedad["direccion"] if propiedad else "",
        "fecha_fin_original": contrato.fecha_fin,
        "fecha_salida": fecha_salida,
        "meses_restantes": meses_restantes,
        "anticipada": meses_restantes > 0,
        "importe_vigente": importe,
        "importe_vigente_desde": tramo["fecha_inicio"],
        # Un importe cargado a mano es, por definición, el del mes: deja de ser estimado.
        "importe_estimado": estimado and importe_manual is None,
        "porcentaje_penalidad": PORCENTAJE_PENALIDAD,
        "penalidad": penalidad,
    }


def registrar_rescision(contrato_id: str, anio: int, mes: int) -> dict:
    """Registra el aviso: el inquilino se va tal mes.

    Solo persiste la fecha de salida. El contrato sigue Activo —ese mes lo paga, así
    que todavía tiene que liquidar y ajustar— y la penalidad queda pendiente hasta la
    entrega de llaves, cuando el alquiler del mes ya se conoce. La penalidad que sale
    de acá es la estimación que se le muestra al operador, no un compromiso.
    """
    _validar_ventana_de_aviso(anio, mes)
    calculo = calcular_rescision(contrato_id, anio, mes)

    if not registrar_aviso_rescision(contrato_id, calculo["fecha_salida"]):
        # Se borró entre el cálculo y el update.
        raise_not_found("Contrato", contrato_id)

    return calculo


def cerrar_por_entrega_llaves(contrato_id: str, fecha_entrega, importe_manual=None) -> dict:
    """Cierra la rescisión con el alquiler real del mes en que se entregaron las llaves.

    Manda el mes de la entrega, no el que se avisó: en la práctica son el mismo, y si
    la entrega se corrió a un mes posterior ese mes se paga entero igual.
    """
    contrato = get_contrato_by_id(contrato_id)
    if not contrato:
        raise_not_found("Contrato", contrato_id)

    if contrato.estado != EstadoContrato.Activo or contrato.fecha_rescision is None:
        raise_conflict(
            f"El contrato {contrato_id} no tiene una rescisión pendiente de cierre",
            field="estado",
            code="sin_rescision_pendiente",
        )

    if fecha_entrega < contrato.fecha_inicio:
        raise_unprocessable(
            "La entrega de llaves no puede ser anterior al inicio del contrato",
            field="fecha_entrega",
            code="entrega_antes_del_inicio",
        )

    anio, mes = fecha_entrega.year, fecha_entrega.month
    fecha_salida = date(anio, mes, monthrange(anio, mes)[1])
    meses_restantes = max(
        0, (contrato.fecha_fin.year - anio) * 12 + (contrato.fecha_fin.month - mes)
    )

    tramo = get_importe_vigente_del_mes(contrato_id, fecha_salida)
    if tramo is None:
        raise_unprocessable(
            f"No hay un importe registrado para {mes:02d}/{anio} en el contrato {contrato_id}",
            field="fecha_entrega",
            code="sin_importe_vigente",
        )

    # El tramo no cubre el mes: el ajuste de ese mes no se cargó todavía. Antes que
    # congelar la penalidad sobre un alquiler viejo, se pide el valor.
    if tramo["fecha_fin"] < fecha_salida and importe_manual is None:
        raise_unprocessable(
            f"No está cargado el alquiler de {mes:02d}/{anio}: indicá el importe "
            "para poder calcular la penalidad",
            field="importe_alquiler",
            code="importe_del_mes_desconocido",
        )

    calculo = _armar_calculo(contrato, fecha_salida, meses_restantes, tramo, importe_manual)

    if not cerrar_rescision(contrato_id, fecha_entrega, fecha_salida, calculo["penalidad"]):
        raise_not_found("Contrato", contrato_id)

    return calculo


def cancelar_rescision(contrato_id: str) -> None:
    """Borra un aviso mal cargado. Sin esto solo se arregla por SQL."""
    contrato = get_contrato_by_id(contrato_id)
    if not contrato:
        raise_not_found("Contrato", contrato_id)

    if contrato.estado != EstadoContrato.Activo or contrato.fecha_rescision is None:
        raise_conflict(
            f"El contrato {contrato_id} no tiene una rescisión pendiente que cancelar",
            field="estado",
            code="sin_rescision_pendiente",
        )

    if not cancelar_aviso_rescision(contrato_id):
        raise_not_found("Contrato", contrato_id)
