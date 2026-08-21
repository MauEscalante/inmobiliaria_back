from datetime import date

from fastapi import HTTPException

from app.api.services.libro_diario_service import (
    get_movimientos,
    get_retiros,
    get_resumen_caja,
    get_historial_mensual,
    create_movimiento,
    delete_movimiento,
    get_movimiento_by_id,
)
from app.api.services.propiedades_services import get_inmueble_by_id
from app.models.libro_diario import CuentaTransferencia, TipoMovimiento

# Ingresos y depósitos son plata de una propiedad, por eso hay que indicar cuál.
TIPOS_CON_PROPIEDAD = ("INGRESO", "DEPOSITO")

# Lo que sale de la caja sale en efectivo, así que no puede salir más de lo que hay.
TIPOS_QUE_SACAN_EFECTIVO = ("EGRESO", "RETIRO")


def _validar_mes(anio: int, mes: int):
    if mes < 1 or mes > 12:
        raise HTTPException(status_code=400, detail="El mes debe estar entre 1 y 12")
    if anio < 1900:
        raise HTTPException(status_code=400, detail="Año inválido")


def get_libro_diario(anio: int, mes: int):
    _validar_mes(anio, mes)
    return get_movimientos(anio, mes)


def get_retiros_caja(anio: int, mes: int):
    _validar_mes(anio, mes)
    return get_retiros(anio, mes)


def get_estado_caja(anio: int, mes: int):
    _validar_mes(anio, mes)
    return get_resumen_caja(anio, mes)


def get_historial():
    return get_historial_mensual()


def _armar_concepto(propiedad: dict, piso: str, depto: str) -> str:
    """"Cotagaita 786" + piso 3 + depto B -> "Cotagaita 786 3° B"."""
    partes = [propiedad.get("direccion")]
    if piso:
        partes.append(f"{piso}°")
    if depto:
        partes.append(depto)
    return " ".join(partes)


def _validar_periodo(fecha_movimiento: date):
    """Los meses que ya pasaron quedan cerrados: solo se registra en el mes en curso."""
    hoy = date.today()
    if (fecha_movimiento.year, fecha_movimiento.month) < (hoy.year, hoy.month):
        raise HTTPException(
            status_code=400,
            detail="No se pueden registrar movimientos en meses anteriores al actual",
        )


def _formato_pesos(monto: float) -> str:
    """1234.5 -> "$ 1.234,50". El formato de Python es al revés del nuestro."""
    entero, decimales = f"{monto:,.2f}".split(".")
    return f"$ {entero.replace(',', '.')},{decimales}"


def _validar_saldo_caja(tipo: str, fecha_movimiento: date, monto: float):
    """La caja no puede quedar en negativo: no se saca más efectivo del que hay.

    Se mide contra el mes del movimiento, no contra el que el usuario esté mirando
    en pantalla, que puede ser otro.
    """
    if tipo not in TIPOS_QUE_SACAN_EFECTIVO:
        return

    disponible = get_resumen_caja(fecha_movimiento.year, fecha_movimiento.month)["total_caja"]
    # Redondeo a centavos: los montos son DECIMAL(12,2) y comparar floats pelados
    # rechazaría un retiro por el total exacto de la caja.
    if round(monto - disponible, 2) > 0:
        raise HTTPException(
            status_code=400,
            detail=f"No hay suficiente efectivo en caja: quedan {_formato_pesos(disponible)}",
        )


def create_new_movimiento(movimiento_data: dict):
    tipo = movimiento_data.get("tipo")
    if tipo not in [t.value for t in TipoMovimiento]:
        raise HTTPException(status_code=400, detail="El tipo de movimiento es inválido")

    fecha = movimiento_data.get("fecha")
    if not fecha:
        raise HTTPException(status_code=400, detail="La fecha es obligatoria")
    try:
        fecha_movimiento = date.fromisoformat(str(fecha))
    except ValueError:
        raise HTTPException(status_code=400, detail="La fecha es inválida")
    _validar_periodo(fecha_movimiento)

    try:
        monto = float(movimiento_data.get("monto"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="El monto es obligatorio")
    if monto <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser mayor a cero")

    cuenta = movimiento_data.get("cuenta") or None
    if cuenta and cuenta not in [c.value for c in CuentaTransferencia]:
        raise HTTPException(status_code=400, detail="La cuenta debe ser Kike o Dai")
    # En un depósito la cuenta es el dato que dice a dónde se transfirió la plata.
    if tipo == "DEPOSITO" and not cuenta:
        raise HTTPException(status_code=400, detail="Indicá a qué cuenta se transfirió el depósito")

    piso = (movimiento_data.get("piso") or "").strip() or None
    depto = (movimiento_data.get("depto") or "").strip() or None
    propiedad_id = movimiento_data.get("propiedad_id")
    concepto = (movimiento_data.get("concepto") or "").strip()

    if tipo in TIPOS_CON_PROPIEDAD:
        if not propiedad_id:
            raise HTTPException(status_code=400, detail="Indicá la propiedad")
        propiedad = get_inmueble_by_id(propiedad_id)
        if not propiedad:
            raise HTTPException(status_code=404, detail="Propiedad no encontrada")
        concepto = _armar_concepto(propiedad, piso, depto)
    else:
        # Los egresos y retiros no tienen propiedad: el concepto lo escribe el usuario.
        if not concepto:
            raise HTTPException(status_code=400, detail="El concepto es obligatorio")
        propiedad_id = None
        piso = None
        depto = None

    _validar_saldo_caja(tipo, fecha_movimiento, monto)

    return create_movimiento({
        "fecha": fecha,
        "propiedad_id": propiedad_id,
        "piso": piso,
        "depto": depto,
        "concepto": concepto,
        "monto": monto,
        "tipo": tipo,
        "cuenta": cuenta,
    })


def eliminar_movimiento(movimiento_id: int):
    if not get_movimiento_by_id(movimiento_id):
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    delete_movimiento(movimiento_id)
    return {"movimiento_id": movimiento_id}
