from calendar import monthrange
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.api.errors import raise_conflict, raise_not_found, raise_unprocessable
from app.api.services.contrato_services import (
    agendar_rescision,
    cerrar_contrato_por_entrega,
    crear_contrato,
    eliminar_contrato,
    existe_contrato,
    get_contrato_by_id,
    get_contrato_detalle,
    get_contratos,
    get_garantes_de_contrato,
    get_inquilinos_de_contrato,
    limpiar_rescision,
)
from app.api.services.propiedades_services import get_inmueble_by_id
from app.api.services.valor_historico_service import get_importe_vigente_del_mes
from app.models.contrato import MESES_POR_PERIODICIDAD, EstadoContrato, TipoAjuste

# Lo que se cobra al inquilino que se va antes de tiempo: el 10% de lo que
# quedaba por pagar hasta el final del contrato.
PORCENTAJE_PENALIDAD = Decimal("0.10")

# Meses hacia adelante que se aceptan como mes de salida, contando desde el actual.
# Los tramos de valor_historico se escriben al liquidar cada mes, así que más allá
# del mes que viene el importe sería una proyección y no un dato.
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


def _indice_mes(anio: int, mes: int) -> int:
    """Mes como número corrido, para restar dos fechas sin pelear con el calendario."""
    return anio * 12 + mes


def _hay_ajuste_sin_registrar(contrato, tramo_inicio: date, anio: int, mes: int) -> bool:
    """Al contrato le toca al menos un ajuste entre el tramo vigente y el mes de salida.

    Ese ajuste todavía no está en valor_historico —el proceso de recibos abre el
    tramo recién cuando se liquida el mes—, así que el importe que se está usando
    es el anterior y la penalidad que sale de él es una estimación.

    La cuenta de a qué contrato le toca ajuste en un mes es la misma que hace
    recibo_service.CONTRATOS_A_AJUSTAR_SELECT: meses transcurridos desde el inicio
    múltiplo de la periodicidad. Solo se ajustan los de IPC, así que un contrato de
    ICL o sin tipo de ajuste nunca da estimado.
    """
    if contrato.tipo_ajuste != TipoAjuste.IPC or not contrato.periodicidad:
        return False

    cada = MESES_POR_PERIODICIDAD.get(contrato.periodicidad.value)
    if not cada:
        return False

    inicio = _indice_mes(contrato.fecha_inicio.year, contrato.fecha_inicio.month)
    desde = _indice_mes(tramo_inicio.year, tramo_inicio.month)
    hasta = _indice_mes(anio, mes)

    # Desde el mes siguiente al del tramo: el suyo propio ya está contemplado en el
    # importe que se leyó.
    return any(
        (indice - inicio) > 0 and (indice - inicio) % cada == 0
        for indice in range(desde + 1, hasta + 1)
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

    limite = _mes_limite()
    if (anio, mes) > limite:
        raise_unprocessable(
            f"Solo se puede rescindir hasta {limite[1]:02d}/{limite[0]}, "
            "el mes siguiente al actual",
            field="mes",
            code="salida_fuera_de_ventana",
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

    importe = tramo["importe_inicial"]
    penalidad = (importe * meses_restantes * PORCENTAJE_PENALIDAD).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    propiedad = get_inmueble_by_id(contrato.propiedad)

    return {
        "contrato_id": contrato_id,
        "direccion": propiedad["direccion"] if propiedad else "",
        "fecha_fin_original": contrato.fecha_fin,
        "fecha_salida": fecha_salida,
        "meses_restantes": meses_restantes,
        "anticipada": meses_restantes > 0,
        "importe_vigente": importe,
        # De qué tramo salió el importe. Cuando el mes de salida todavía no se
        # liquidó es anterior al mes elegido, y la pantalla lo aclara.
        "importe_vigente_desde": tramo["fecha_inicio"],
        # Entre ese tramo y el mes de salida le entra un ajuste que todavía no se
        # cargó: el número de abajo es orientativo y se rehace al entregar las llaves.
        "importe_estimado": _hay_ajuste_sin_registrar(
            contrato, tramo["fecha_inicio"], anio, mes
        ),
        "porcentaje_penalidad": PORCENTAJE_PENALIDAD,
        "penalidad": penalidad,
    }


def registrar_aviso(contrato_id: str, anio: int, mes: int) -> dict:
    """Registra que el inquilino se va tal mes. NO cierra el contrato.

    Queda Activo con la salida agendada porque ese mes lo paga y se sigue
    liquidando y ajustando como cualquier otro. La penalidad no se guarda todavía:
    hasta que no entregue las llaves no se sabe con qué alquiler se calcula, así
    que lo que devuelve esta función puede ser una estimación (`importe_estimado`).

    Recalcula del lado del servidor en vez de confiar en lo que vio el cliente.
    """
    calculo = calcular_rescision(contrato_id, anio, mes)

    if not agendar_rescision(contrato_id, calculo["fecha_salida"]):
        # Se borró entre el cálculo y el update.
        raise_not_found("Contrato", contrato_id)

    return calculo


def cerrar_por_entrega(contrato_id: str, fecha_entrega: date, importe_alquiler=None) -> dict:
    """Cierra el contrato con la fecha real de entrega y la penalidad definitiva.

    Se calcula contra el mes de la entrega y no contra el que se avisó: si la
    entrega se corrió de mes, ese mes se paga entero y los meses restantes se
    cuentan desde ahí.
    """
    contrato = get_contrato_by_id(contrato_id)
    if not contrato:
        raise_not_found("Contrato", contrato_id)

    if contrato.fecha_rescision is None:
        raise_conflict(
            f"El contrato {contrato_id} no tiene una rescisión registrada: "
            "primero hay que avisar la salida",
            field="fecha_rescision",
            code="sin_rescision_registrada",
        )

    calculo = calcular_rescision(contrato_id, fecha_entrega.year, fecha_entrega.month)

    # El ajuste del mes de salida no está cargado, así que el tramo no sirve de base:
    # el importe lo aporta quien registra la entrega, que ya tiene el recibo.
    if calculo["importe_estimado"]:
        if importe_alquiler is None:
            raise_unprocessable(
                f"El alquiler de {fecha_entrega.month:02d}/{fecha_entrega.year} todavía "
                "no está cargado: indicá el importe para calcular la penalidad",
                field="importe_alquiler",
                code="importe_alquiler_requerido",
            )

        base = Decimal(str(importe_alquiler))
        calculo["importe_vigente"] = base
        calculo["penalidad"] = (
            base * calculo["meses_restantes"] * PORCENTAJE_PENALIDAD
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        # Ya no lo es: se cerró con el importe real que pasó el operador.
        calculo["importe_estimado"] = False

    if not cerrar_contrato_por_entrega(contrato_id, fecha_entrega, calculo["penalidad"]):
        raise_not_found("Contrato", contrato_id)

    return calculo


def cancelar_aviso(contrato_id: str) -> None:
    """Deshace un aviso mal cargado y devuelve el contrato a su curso normal.

    Solo aplica mientras las llaves no se entregaron: un contrato ya cerrado no se
    reabre por acá.
    """
    contrato = get_contrato_by_id(contrato_id)
    if not contrato:
        raise_not_found("Contrato", contrato_id)

    if contrato.estado == EstadoContrato.Rescindido:
        raise_conflict(
            f"El contrato {contrato_id} ya está cerrado: cancelar el aviso no lo reabre",
            field="estado",
            code="contrato_ya_rescindido",
        )

    if contrato.fecha_rescision is None:
        raise_conflict(
            f"El contrato {contrato_id} no tiene una rescisión registrada",
            field="fecha_rescision",
            code="sin_rescision_registrada",
        )

    if not limpiar_rescision(contrato_id):
        raise_not_found("Contrato", contrato_id)
