from decimal import Decimal

from app.models.propiedad import EstadoAlquiler, EstadoPropiedad, Propiedad
from app.database.connection import SessionLocal
from sqlalchemy import text

# Campos que el cliente puede setear; el resto (estado inicial, id) lo decide el backend.
PROPIEDAD_FIELDS = {"direccion", "ambientes"}

# Fila enriquecida de propiedad: suma propietario, inquilino vigente y comisión.
# La comisión pertenece al propietario (es la misma en todas sus propiedades), por eso
# se lee de propiedad_propietario y no de la propiedad.
PROPIEDAD_SELECT = """
    SELECT
      p.propiedad_id, p.direccion, p.ambientes, p.estado, p.estado_alquiler,
      (SELECT GROUP_CONCAT(CONCAT(cl.nombre, ' ', cl.apellido) ORDER BY cl.apellido SEPARATOR ', ')
         FROM propiedad_propietario pp
         JOIN cliente cl ON cl.cliente_num = pp.cliente
        WHERE pp.propiedad_id = p.propiedad_id) AS propietario,
      (SELECT MAX(pp.comision)
         FROM propiedad_propietario pp
        WHERE pp.propiedad_id = p.propiedad_id) AS comision,
      -- Inquilinos del contrato vigente más reciente. Se resuelve primero cuál es ese
      -- contrato para no mezclar inquilinos de contratos superpuestos; un mismo contrato
      -- sí puede tener varios co-inquilinos.
      (SELECT GROUP_CONCAT(CONCAT(cl.nombre, ' ', cl.apellido) ORDER BY cl.apellido SEPARATOR ', ')
         FROM contrato_inquilino ci
         JOIN cliente cl ON cl.cliente_num = ci.cliente
        WHERE ci.contrato = (
              SELECT c.contrato_id
                FROM contrato c
               WHERE c.propiedad = p.propiedad_id
                 AND CURDATE() BETWEEN c.fecha_inicio AND c.fecha_fin
               ORDER BY c.fecha_inicio DESC, c.contrato_id DESC
               LIMIT 1)) AS inquilino
    FROM propiedad p
"""


def _serializar(row) -> dict:
    propiedad = dict(row)
    # Decimal no es serializable a JSON por FastAPI sin convertirlo antes.
    for campo in ("comision", "porcentaje"):
        if isinstance(propiedad.get(campo), Decimal):
            propiedad[campo] = float(propiedad[campo])
    return propiedad


def get_inmuebles() -> list:
    db = SessionLocal()
    try:
        query = text(PROPIEDAD_SELECT + " ORDER BY p.propiedad_id")
        return [_serializar(row) for row in db.execute(query).mappings().all()]
    finally:
        db.close()


def get_inmueble_by_id(propiedad_id: int) -> dict:
    db = SessionLocal()
    try:
        query = text(PROPIEDAD_SELECT + " WHERE p.propiedad_id = :propiedad_id")
        propiedad = db.execute(query, {"propiedad_id": propiedad_id}).mappings().first()

        if not propiedad:
            return None

        propietarios = db.execute(
            text("""
                SELECT cl.cliente_num, CONCAT(cl.nombre, ' ', cl.apellido) AS nombre,
                       pp.porcentaje, pp.comision
                FROM propiedad_propietario pp
                JOIN cliente cl ON cl.cliente_num = pp.cliente
                WHERE pp.propiedad_id = :propiedad_id
                ORDER BY cl.apellido
            """),
            {"propiedad_id": propiedad_id},
        ).mappings().all()

        detalle = _serializar(propiedad)
        detalle["propietarios"] = [_serializar(row) for row in propietarios]
        return detalle
    finally:
        db.close()


def create_inmueble(propiedad_data: dict) -> dict:
    db = SessionLocal()
    try:
        campos = {k: v for k, v in propiedad_data.items() if k in PROPIEDAD_FIELDS}
        nueva_propiedad = Propiedad(
            **campos,
            estado=EstadoPropiedad.Activa,
            estado_alquiler=EstadoAlquiler.Adeuda,
        )
        db.add(nueva_propiedad)
        db.commit()
        db.refresh(nueva_propiedad)
        propiedad_id = nueva_propiedad.propiedad_id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return get_inmueble_by_id(propiedad_id)


def update_inmueble(propiedad_id: int, propiedad_data: dict) -> dict:
    db = SessionLocal()
    try:
        query = text("""
            UPDATE propiedad
            SET direccion = :direccion,
                ambientes = :ambientes,
                estado = :estado,
                estado_alquiler = :estado_alquiler
            WHERE propiedad_id = :propiedad_id
        """)
        db.execute(query, {
            "direccion": propiedad_data.get("direccion"),
            "ambientes": propiedad_data.get("ambientes"),
            "estado": propiedad_data.get("estado"),
            "estado_alquiler": propiedad_data.get("estado_alquiler"),
            "propiedad_id": propiedad_id,
        })
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return get_inmueble_by_id(propiedad_id)


def delete_inmueble(propiedad_id: int) -> bool:
    """Borra la propiedad. Devuelve False si tiene contratos asociados."""
    db = SessionLocal()
    try:
        contratos = db.execute(
            text("SELECT COUNT(*) FROM contrato WHERE propiedad = :propiedad_id"),
            {"propiedad_id": propiedad_id},
        ).scalar()

        if contratos:
            return False

        db.execute(
            text("DELETE FROM propiedad_propietario WHERE propiedad_id = :propiedad_id"),
            {"propiedad_id": propiedad_id},
        )
        db.execute(
            text("DELETE FROM propiedad WHERE propiedad_id = :propiedad_id"),
            {"propiedad_id": propiedad_id},
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def update_direccion_by_id(propiedad_id: int, direccion: str) -> None:
    db = SessionLocal()
    try:
        query = text("""
        UPDATE propiedad
        SET direccion= :direccion
        WHERE propiedad_id= :propiedad_id
        """)
        db.execute(query, {"direccion": direccion, "propiedad_id": propiedad_id})
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def update_estado_by_id(propiedad_id: int, estado: str) -> None:
    db = SessionLocal()
    try:
        query = text("""
        UPDATE propiedad
        SET estado= :estado
        WHERE propiedad_id= :propiedad_id
        """)
        db.execute(query, {"estado": estado, "propiedad_id": propiedad_id})
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
