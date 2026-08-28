from datetime import date
from decimal import Decimal

from app.api.errors import raise_not_found, raise_unprocessable
from app.api.services.libro_diario_service import (
    create_movimiento,
    delete_movimiento,
    get_historial_mensual,
    get_movimiento_by_id,
    get_movimientos,
    get_resumen_caja,
)
from app.api.services.propiedades_services import get_inmueble_by_id
from app.models.libro_diario import TipoMovimiento

# Ingresos y depósitos pueden ser plata de una propiedad, y ahí el concepto se arma
# con la dirección.
TIPOS_CON_PROPIEDAD = ("INGRESO", "DEPOSITO")

# El depósito siempre es el cobro de un alquiler. El efectivo puede no serlo (una seña,
# una comisión suelta), y ahí el concepto lo escribe el usuario igual que en un egreso.
TIPOS_QUE_EXIGEN_PROPIEDAD = ("DEPOSITO",)

# Lo que sale de la caja sale en efectivo, así que no puede salir más de lo que hay.
TIPOS_QUE_SACAN_EFECTIVO = (TipoMovimiento.EGRESO.value, TipoMovimiento.RETIRO.value)


def get_libro_diario(
    anio: int | None,
    mes: int | None,
    tipos: list[str] | None,
    sort: str | None,
    limit: int,
    offset: int,
):
    """Los rangos de anio y mes los valida Query en la ruta."""
    return get_movimientos(anio, mes, tipos, sort, limit, offset)


def get_movimiento(movimiento_id: int):
    movimiento = get_movimiento_by_id(movimiento_id)
    if not movimiento:
        raise_not_found("Movimiento", movimiento_id)
    return movimiento


def get_estado_caja(anio: int, mes: int):
    return get_resumen_caja(anio, mes)


def get_historial(limit: int, offset: int):
    return get_historial_mensual(limit, offset)


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
        raise_unprocessable(
            "No se pueden registrar movimientos en meses anteriores al actual",
            field="fecha",
            code="periodo_cerrado",
        )


def _validar_saldo_caja(tipo: str, fecha_movimiento: date, monto: Decimal):
    """La caja no puede quedar en negativo: no se saca más efectivo del que hay.

    Se mide contra el mes del movimiento, no contra el que el usuario esté mirando
    en pantalla, que puede ser otro.
    """
    if tipo not in TIPOS_QUE_SACAN_EFECTIVO:
        return

    disponible = get_resumen_caja(fecha_movimiento.year, fecha_movimiento.month)["total_caja"]
    # Redondeo a centavos: los montos son DECIMAL(12,2) y comparar floats pelados
    # rechazaría un retiro por el total exacto de la caja.
    if round(float(monto) - disponible, 2) > 0:
        # El monto disponible va como número: formatearlo en pesos acá dejaba una
        # string de presentación adentro del error, que el cliente no puede usar.
        raise_unprocessable(
            f"No hay suficiente efectivo en caja: quedan {disponible}",
            field="monto",
            code="saldo_insuficiente",
        )


def create_new_movimiento(movimiento_data: dict):
    """La forma del body (tipo válido, monto > 0, cuenta en depósitos, concepto en
    egresos) ya la valida MovimientoCreate. Acá quedan solo las reglas que necesitan
    mirar la base o el reloj."""
    tipo = movimiento_data["tipo"]
    fecha_movimiento = movimiento_data["fecha"]
    monto = movimiento_data["monto"]

    _validar_periodo(fecha_movimiento)

    piso = (movimiento_data.get("piso") or "").strip() or None
    depto = (movimiento_data.get("depto") or "").strip() or None
    propiedad_id = movimiento_data.get("propiedad_id")
    concepto = (movimiento_data.get("concepto") or "").strip()

    if tipo in TIPOS_QUE_EXIGEN_PROPIEDAD and not propiedad_id:
        raise HTTPException(status_code=400, detail="Indicá la propiedad")

    # Manda si hay propiedad, no el tipo: así el efectivo entra por las dos ramas.
    if tipo in TIPOS_CON_PROPIEDAD and propiedad_id:
        propiedad = get_inmueble_by_id(propiedad_id)
        if not propiedad:
            # Una referencia inválida dentro del body es 422: el 404 diría que la
            # colección de movimientos no existe.
            raise_unprocessable(
                f"No existe la propiedad {propiedad_id}",
                field="propiedad_id",
                code="referencia_inexistente",
            )
        concepto = _armar_concepto(propiedad, piso, depto)
    else:
        # Sin propiedad el concepto lo escribe el usuario: egresos, retiros y los
        # ingresos en efectivo que no son de un alquiler.
        if not concepto:
            raise HTTPException(status_code=400, detail="El concepto es obligatorio")
        propiedad_id = None
        piso = None
        depto = None

    _validar_saldo_caja(tipo, fecha_movimiento, monto)

    return create_movimiento({
        "fecha": fecha_movimiento,
        "propiedad_id": propiedad_id,
        "piso": piso,
        "depto": depto,
        "concepto": concepto,
        "monto": monto,
        "tipo": tipo,
        "cuenta": movimiento_data.get("cuenta"),
    })


def eliminar_movimiento(movimiento_id: int) -> None:
    if not get_movimiento_by_id(movimiento_id):
        raise_not_found("Movimiento", movimiento_id)
    delete_movimiento(movimiento_id)
