from datetime import date
from decimal import Decimal

from app.database.connection import SessionLocal
from sqlalchemy import text

# Nombres de mes en español para el historial que consume la pantalla de Recibos.
MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

# Fila del libro diario. Se trae la dirección actual de la propiedad además del
# concepto guardado, para poder enlazar la fila con la propiedad desde el front.
MOVIMIENTO_SELECT = """
    SELECT
      ld.movimiento_id, ld.fecha, ld.concepto, ld.monto, ld.tipo, ld.cuenta,
      ld.propiedad_id, ld.piso, ld.depto,
      p.direccion
    FROM libroDiario ld
    LEFT JOIN propiedad p ON p.propiedad_id = ld.propiedad_id
"""

FILTRO_MES = " WHERE YEAR(ld.fecha) = :anio AND MONTH(ld.fecha) = :mes"


def _serializar(row) -> dict:
    movimiento = dict(row)
    # Ni Decimal ni date son serializables a JSON por FastAPI sin convertirlos antes.
    if isinstance(movimiento.get("monto"), Decimal):
        movimiento["monto"] = float(movimiento["monto"])
    if isinstance(movimiento.get("fecha"), date):
        movimiento["fecha"] = movimiento["fecha"].isoformat()
    return movimiento


def get_movimientos(anio: int, mes: int) -> list:
    """Movimientos del mes, del más nuevo al más viejo.

    Los retiros de caja van aparte, no entran en la tabla. El desempate por
    movimiento_id importa: los movimientos de un mismo día comparten fecha.
    """
    db = SessionLocal()
    try:
        query = text(
            MOVIMIENTO_SELECT + FILTRO_MES +
            " AND ld.tipo <> 'RETIRO' ORDER BY ld.fecha DESC, ld.movimiento_id DESC"
        )
        filas = db.execute(query, {"anio": anio, "mes": mes}).mappings().all()
        return [_serializar(row) for row in filas]
    finally:
        db.close()


def get_retiros(anio: int, mes: int) -> list:
    db = SessionLocal()
    try:
        query = text(
            MOVIMIENTO_SELECT + FILTRO_MES +
            " AND ld.tipo = 'RETIRO' ORDER BY ld.fecha, ld.movimiento_id"
        )
        filas = db.execute(query, {"anio": anio, "mes": mes}).mappings().all()
        return [_serializar(row) for row in filas]
    finally:
        db.close()


def get_resumen_caja(anio: int, mes: int) -> dict:
    """Estado de la caja del mes.

    En la caja hay efectivo y nada más. Lo que se cobra por transferencia va derecho
    a una cuenta, así que se informa aparte pero no entra en el total en caja.
    Los egresos y los retiros sí salen de la caja y por eso se restan.
    """
    db = SessionLocal()
    try:
        query = text("""
            SELECT
              COALESCE(SUM(CASE WHEN tipo = 'INGRESO'  THEN monto END), 0) AS total_efectivo,
              COALESCE(SUM(CASE WHEN tipo = 'DEPOSITO' THEN monto END), 0) AS total_transferencias,
              COALESCE(SUM(CASE WHEN tipo = 'EGRESO'   THEN monto END), 0) AS total_egresos,
              COALESCE(SUM(CASE WHEN tipo = 'RETIRO'   THEN monto END), 0) AS total_retiros
            FROM libroDiario
            WHERE YEAR(fecha) = :anio AND MONTH(fecha) = :mes
        """)
        fila = db.execute(query, {"anio": anio, "mes": mes}).mappings().first()

        resumen = {campo: float(valor) for campo, valor in dict(fila).items()}
        resumen["total_caja"] = (
            resumen["total_efectivo"] - resumen["total_egresos"] - resumen["total_retiros"]
        )
        return resumen
    finally:
        db.close()


def create_movimiento(movimiento_data: dict) -> dict:
    """Inserta el movimiento y, si corresponde, deja la propiedad como abonada.

    Las dos operaciones van en la misma transacción: no puede quedar el cobro
    registrado con la propiedad todavía en 'Adeuda'.
    """
    db = SessionLocal()
    try:
        query = text("""
            INSERT INTO libroDiario (fecha, propiedad_id, piso, depto, concepto, monto, tipo, cuenta)
            VALUES (:fecha, :propiedad_id, :piso, :depto, :concepto, :monto, :tipo, :cuenta)
        """)
        resultado = db.execute(query, {
            "fecha": movimiento_data.get("fecha"),
            "propiedad_id": movimiento_data.get("propiedad_id"),
            "piso": movimiento_data.get("piso"),
            "depto": movimiento_data.get("depto"),
            "concepto": movimiento_data.get("concepto"),
            "monto": movimiento_data.get("monto"),
            "tipo": movimiento_data.get("tipo"),
            "cuenta": movimiento_data.get("cuenta"),
        })
        movimiento_id = resultado.lastrowid

        if movimiento_data.get("tipo") in ("INGRESO", "DEPOSITO") and movimiento_data.get("propiedad_id"):
            db.execute(
                text("UPDATE propiedad SET estado_alquiler = 'Abono' WHERE propiedad_id = :propiedad_id"),
                {"propiedad_id": movimiento_data.get("propiedad_id")},
            )

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return get_movimiento_by_id(movimiento_id)


def get_movimiento_by_id(movimiento_id: int) -> dict:
    db = SessionLocal()
    try:
        query = text(MOVIMIENTO_SELECT + " WHERE ld.movimiento_id = :movimiento_id")
        fila = db.execute(query, {"movimiento_id": movimiento_id}).mappings().first()
        return _serializar(fila) if fila else None
    finally:
        db.close()


def delete_movimiento(movimiento_id: int) -> bool:
    db = SessionLocal()
    try:
        resultado = db.execute(
            text("DELETE FROM libroDiario WHERE movimiento_id = :movimiento_id"),
            {"movimiento_id": movimiento_id},
        )
        db.commit()
        return resultado.rowcount > 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_historial_mensual() -> list:
    """Total de ingresos por mes. Es lo que muestra la card de la pantalla de Recibos."""
    db = SessionLocal()
    try:
        query = text("""
            SELECT YEAR(fecha) AS anio, MONTH(fecha) AS mes, SUM(monto) AS total
            FROM libroDiario
            WHERE tipo = 'INGRESO'
            GROUP BY YEAR(fecha), MONTH(fecha)
            ORDER BY anio DESC, mes DESC
        """)
        return [
            {
                "id": f"{row['anio']}-{row['mes']:02d}",
                "mes": MESES[row["mes"] - 1],
                "anio": str(row["anio"]),
                "total": float(row["total"]),
            }
            for row in db.execute(query).mappings().all()
        ]
    finally:
        db.close()


def marcar_todas_adeuda() -> int:
    """Arranca el período nuevo: todas las propiedades activas vuelven a estar impagas.

    Se llama al generar los recibos del mes.
    """
    db = SessionLocal()
    try:
        resultado = db.execute(
            text("UPDATE propiedad SET estado_alquiler = 'Adeuda' WHERE estado = 'Activa'")
        )
        db.commit()
        return resultado.rowcount
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
