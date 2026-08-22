from app.database.connection import SessionLocal
from app.utils.helpers import serializar_fila
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

# Columnas por las que se puede ordenar. Es una lista blanca: el valor del cliente
# no se interpola nunca sin pasar por acá.
ORDENABLES = {
    "fecha": "ld.fecha",
    "monto": "ld.monto",
    "movimiento_id": "ld.movimiento_id",
}

ORDEN_POR_DEFECTO = "-fecha"


def _orden(sort: str | None) -> str:
    """Traduce `?sort=-fecha` a un ORDER BY. El '-' adelante significa descendente.

    Se desempata siempre por movimiento_id: los movimientos de un mismo día
    comparten fecha y sin desempate el orden no sería estable entre páginas.
    """
    criterio = (sort or ORDEN_POR_DEFECTO).strip()
    descendente = criterio.startswith("-")
    campo = criterio.lstrip("-")

    columna = ORDENABLES.get(campo)
    if not columna:
        columna = ORDENABLES["fecha"]
        descendente = True

    direccion = "DESC" if descendente else "ASC"
    return f" ORDER BY {columna} {direccion}, ld.movimiento_id {direccion}"


def _filtros(anio: int | None, mes: int | None, tipos: list[str] | None) -> tuple[str, dict]:
    condiciones = []
    params: dict = {}

    if anio:
        condiciones.append("YEAR(ld.fecha) = :anio")
        params["anio"] = anio
    if mes:
        condiciones.append("MONTH(ld.fecha) = :mes")
        params["mes"] = mes

    if tipos:
        marcadores = []
        for indice, valor in enumerate(tipos):
            clave = f"tipo_{indice}"
            marcadores.append(f":{clave}")
            params[clave] = valor
        condiciones.append(f"ld.tipo IN ({', '.join(marcadores)})")

    where = f" WHERE {' AND '.join(condiciones)}" if condiciones else ""
    return where, params


def get_movimientos(
    anio: int | None,
    mes: int | None,
    tipos: list[str] | None,
    sort: str | None,
    limit: int,
    offset: int,
) -> tuple[list, int]:
    """Página de movimientos más el total que matchea el filtro.

    Unifica los dos endpoints viejos: el listado del mes y el de retiros, que era
    este mismo query con `tipo = 'RETIRO'` fijo en la URL.
    """
    db = SessionLocal()
    try:
        where, params = _filtros(anio, mes, tipos)

        total = db.execute(
            text(f"SELECT COUNT(*) FROM libroDiario ld{where}"), params
        ).scalar() or 0

        query = text(
            MOVIMIENTO_SELECT + where + _orden(sort) + " LIMIT :_limit OFFSET :_offset"
        )
        filas = db.execute(query, {**params, "_limit": limit, "_offset": offset}).mappings().all()
        return [serializar_fila(fila) for fila in filas], total
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
        return serializar_fila(fila) if fila else None
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


def get_historial_mensual(limit: int, offset: int) -> tuple[list, int]:
    """Total de ingresos por mes. Es lo que muestra la card de la pantalla de Recibos."""
    db = SessionLocal()
    try:
        total = db.execute(
            text("""
                SELECT COUNT(*) FROM (
                  SELECT 1 FROM libroDiario
                  WHERE tipo = 'INGRESO'
                  GROUP BY YEAR(fecha), MONTH(fecha)
                ) AS periodos
            """)
        ).scalar() or 0

        query = text("""
            SELECT YEAR(fecha) AS anio, MONTH(fecha) AS mes, SUM(monto) AS total
            FROM libroDiario
            WHERE tipo = 'INGRESO'
            GROUP BY YEAR(fecha), MONTH(fecha)
            ORDER BY anio DESC, mes DESC
            LIMIT :_limit OFFSET :_offset
        """)
        filas = [
            {
                "id": f"{row['anio']}-{row['mes']:02d}",
                "mes": MESES[row["mes"] - 1],
                "anio": str(row["anio"]),
                "total": float(row["total"]),
            }
            for row in db.execute(query, {"_limit": limit, "_offset": offset}).mappings().all()
        ]
        return filas, total
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
