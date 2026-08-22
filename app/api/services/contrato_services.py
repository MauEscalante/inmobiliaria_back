from app.models.contrato import Contrato, ContratoInquilino, EstadoContrato
from app.models.cliente import ClienteTipo
from app.api.services.cliente_services import find_or_create_cliente
from app.api.services.evento_service import registrar
from app.api.services.garante_services import crear_garante
from app.api.services.valor_historico_service import sembrar_tramo_inicial
from app.models.evento import TipoEvento
from app.models.propiedad import Propiedad
from app.database.connection import SessionLocal
from app.utils.helpers import serializar_fila
from sqlalchemy import text

# Campos que pertenecen realmente a la tabla contrato; el resto (p. ej. inquilinos)
# se maneja aparte para no intentar setearlos como columnas.
CONTRATO_FIELDS = {
    "propiedad",
    "fecha_inicio",
    "fecha_fin",
    "tipo_ajuste",
    "periodicidad",
    "importe_inicial",
    "deposito",
    "estado",
    "garantia",
    "direccion_garantia",
}

INQUILINOS_SELECT = """
    SELECT cl.cliente_num, cl.nombre, cl.apellido, cl.dni
    FROM contrato_inquilino ci
    JOIN cliente cl ON cl.cliente_num = ci.cliente
    WHERE ci.contrato = :contrato_id
"""

GARANTES_SELECT = """
    SELECT garante_id, nombre, apellido, telefono, dni, sueldo, email
    FROM garante
    WHERE contrato = :contrato_id
"""


def _generar_contrato_id(db) -> str:
    ultimo = db.execute(text("SELECT MAX(CAST(contrato_id AS UNSIGNED)) FROM contrato")).scalar()
    siguiente = (ultimo or 0) + 1
    return str(siguiente).zfill(6)


def get_contratos(
    estado: str | None, propiedad_id: int | None, limit: int, offset: int
) -> tuple[list, int]:
    """Página de contratos más el total que matchea el filtro.

    Se devuelven objetos del modelo, pero la ruta declara response_model, así que
    lo que sale es el schema y no las columnas crudas de la tabla.
    """
    db = SessionLocal()
    try:
        query = db.query(Contrato)
        if estado:
            query = query.filter(Contrato.estado == estado)
        if propiedad_id:
            query = query.filter(Contrato.propiedad == propiedad_id)

        total = query.count()
        contratos = (
            query.order_by(Contrato.contrato_id.desc()).limit(limit).offset(offset).all()
        )
        # Se materializan dentro de la sesión: después del close quedan detached.
        db.expunge_all()
        return contratos, total
    finally:
        db.close()


def get_contrato_by_id(contrato_id: str):
    db = SessionLocal()
    try:
        return db.query(Contrato).where(Contrato.contrato_id == contrato_id).first()
    finally:
        db.close()


def get_contrato_detalle(contrato_id: str):
    db = SessionLocal()
    try:
        contrato = db.execute(
            text("""
                SELECT c.contrato_id, c.fecha_inicio, c.fecha_fin, c.importe_inicial,
                       c.deposito, c.tipo_ajuste, c.periodicidad, c.estado,
                       c.garantia, c.direccion_garantia,
                       c.fecha_rescision, c.penalidad,
                       p.propiedad_id, p.direccion
                FROM contrato c
                JOIN propiedad p ON p.propiedad_id = c.propiedad
                WHERE c.contrato_id = :id
            """),
            {"id": contrato_id},
        ).mappings().first()

        if not contrato:
            return None

        propietarios = db.execute(
            text("""
                SELECT cl.cliente_num, cl.nombre, cl.apellido, pp.porcentaje
                FROM propiedad_propietario pp
                JOIN cliente cl ON cl.cliente_num = pp.cliente
                WHERE pp.propiedad_id = :propiedad_id
            """),
            {"propiedad_id": contrato["propiedad_id"]},
        ).mappings().all()

        inquilinos = db.execute(
            text(INQUILINOS_SELECT), {"contrato_id": contrato_id}
        ).mappings().all()

        garantes = db.execute(
            text(GARANTES_SELECT), {"contrato_id": contrato_id}
        ).mappings().all()

        return {
            "contrato_id": contrato["contrato_id"],
            "propiedad": {
                "propiedad_id": contrato["propiedad_id"],
                "direccion": contrato["direccion"],
            },
            "propietarios": [serializar_fila(fila) for fila in propietarios],
            "inquilinos": [serializar_fila(fila) for fila in inquilinos],
            "garantia": contrato["garantia"],
            "direccion_garantia": contrato["direccion_garantia"],
            "garantes": [serializar_fila(fila) for fila in garantes],
            "fecha_inicio": contrato["fecha_inicio"],
            "fecha_fin": contrato["fecha_fin"],
            "importe_inicial": contrato["importe_inicial"],
            "deposito": contrato["deposito"],
            "tipo_ajuste": contrato["tipo_ajuste"],
            "periodicidad": contrato["periodicidad"],
            "estado": contrato["estado"],
            "fecha_rescision": contrato["fecha_rescision"],
            "penalidad": contrato["penalidad"],
        }
    finally:
        db.close()


def get_inquilinos_de_contrato(contrato_id: str) -> list:
    """Sub-recurso /contratos/{id}/inquilinos."""
    db = SessionLocal()
    try:
        filas = db.execute(text(INQUILINOS_SELECT), {"contrato_id": contrato_id}).mappings().all()
        return [serializar_fila(fila) for fila in filas]
    finally:
        db.close()


def get_garantes_de_contrato(contrato_id: str) -> list:
    """Sub-recurso /contratos/{id}/garantes."""
    db = SessionLocal()
    try:
        filas = db.execute(text(GARANTES_SELECT), {"contrato_id": contrato_id}).mappings().all()
        return [serializar_fila(fila) for fila in filas]
    finally:
        db.close()


def existe_contrato(contrato_id: str) -> bool:
    db = SessionLocal()
    try:
        fila = db.execute(
            text("SELECT 1 FROM contrato WHERE contrato_id = :id LIMIT 1"),
            {"id": contrato_id},
        ).first()
        return fila is not None
    finally:
        db.close()


def crear_contrato(contrato_data: dict):
    db = SessionLocal()
    try:
        inquilinos_data = contrato_data.get("inquilinos") or []
        campos_contrato = {k: v for k, v in contrato_data.items() if k in CONTRATO_FIELDS}
        campos_contrato["contrato_id"] = _generar_contrato_id(db)

        contrato = Contrato(**campos_contrato)
        db.add(contrato)
        db.flush()  # asigna contrato.contrato_id antes del commit

        for inquilino_data in inquilinos_data:
            cliente = find_or_create_cliente(db, inquilino_data, ClienteTipo.Inquilino)
            db.add(ContratoInquilino(contrato_id=contrato.contrato_id, cliente_num=cliente.cliente_num))

        for garante_data in contrato_data.get("garantes") or []:
            crear_garante(db, garante_data, contrato.contrato_id)

        # El importe vigente de un contrato se lee de valor_historico, así que el
        # alta tiene que dejar sembrado el primer tramo o el contrato nace sin
        # importe consultable por fecha.
        sembrar_tramo_inicial(db, contrato)

        # El contrato solo guarda el id de la propiedad, y el evento muestra la
        # dirección: hay que traerla de la misma sesión.
        propiedad = db.get(Propiedad, contrato.propiedad)
        registrar(
            db,
            TipoEvento.contrato_creado.value,
            f"Se creó el contrato de {propiedad.direccion}" if propiedad else "Se creó un contrato",
            "contrato",
            contrato.contrato_id,
        )

        db.commit()
        db.refresh(contrato)
        db.expunge(contrato)
        return contrato
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def rescindir_contrato(contrato_id: str, fecha_salida, penalidad):
    """Cierra el contrato por rescisión. Devuelve None si no existe.

    `fecha_fin` no se toca: guarda el plazo pactado, que es contra lo que se
    calculó la penalidad. Quien quiera saber hasta cuándo estuvo ocupada la
    propiedad mira `fecha_rescision`.
    """
    db = SessionLocal()
    try:
        contrato = db.query(Contrato).where(Contrato.contrato_id == contrato_id).first()
        if not contrato:
            return None

        contrato.estado = EstadoContrato.Rescindido
        contrato.fecha_rescision = fecha_salida
        contrato.penalidad = penalidad

        propiedad = db.get(Propiedad, contrato.propiedad)
        registrar(
            db,
            TipoEvento.contrato_rescindido.value,
            f"Se rescindió el contrato de {propiedad.direccion}"
            if propiedad
            else "Se rescindió un contrato",
            "contrato",
            contrato.contrato_id,
        )

        db.commit()
        db.refresh(contrato)
        db.expunge(contrato)
        return contrato
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def eliminar_contrato(contrato_id: str) -> bool:
    """Borra el contrato. Devuelve False si no existe.

    Antes se llamaba db.delete(contrato) sin chequear el None que devuelve first(),
    así que un id inexistente reventaba con un 500 en vez de un 404.
    """
    db = SessionLocal()
    try:
        contrato = db.query(Contrato).where(Contrato.contrato_id == contrato_id).first()
        if not contrato:
            return False

        db.delete(contrato)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
