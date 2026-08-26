from datetime import timedelta

from app.models.contrato import Contrato, ContratoInquilino
from app.models.cliente import ClienteTipo
from app.api.services.cliente_services import find_or_create_cliente
from app.api.services.garante_services import crear_garante
from app.database.connection import SessionLocal
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

def _generar_contrato_id(db) -> str:
    ultimo = db.execute(text("SELECT MAX(CAST(contrato_id AS UNSIGNED)) FROM contrato")).scalar()
    siguiente = (ultimo or 0) + 1
    return str(siguiente).zfill(6)

def get_contratos():
    db = SessionLocal()
    try:
        contratos=db.query(Contrato).all()

        return contratos
    finally:
        db.close()

def get_contrato_by_id(id: int):
    db = SessionLocal()
    try:
        return db.query(Contrato).where(Contrato.contrato_id == id).first()
    finally:
        db.close()

def get_contrato_detalle(id: int):
    db = SessionLocal()
    try:
        contrato = db.execute(
            text("""
                SELECT c.contrato_id, c.fecha_inicio, c.fecha_fin, c.importe_inicial,
                       c.deposito, c.tipo_ajuste, c.periodicidad, c.estado,
                       c.garantia, c.direccion_garantia,
                       p.propiedad_id, p.direccion
                FROM contrato c
                JOIN propiedad p ON p.propiedad_id = c.propiedad
                WHERE c.contrato_id = :id
            """),
            {"id": id},
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
            text("""
                SELECT cl.cliente_num, cl.nombre, cl.apellido, cl.dni
                FROM contrato_inquilino ci
                JOIN cliente cl ON cl.cliente_num = ci.cliente
                WHERE ci.contrato = :contrato_id
            """),
            {"contrato_id": id},
        ).mappings().all()

        garantes = db.execute(
            text("""
                SELECT garante_id, nombre, apellido, telefono, dni, sueldo, email
                FROM garante
                WHERE contrato = :contrato_id
            """),
            {"contrato_id": id},
        ).mappings().all()

        return {
            "contrato_id": contrato["contrato_id"],
            "propiedad": {
                "propiedad_id": contrato["propiedad_id"],
                "direccion": contrato["direccion"],
            },
            "propietarios": [dict(row) for row in propietarios],
            "inquilinos": [dict(row) for row in inquilinos],
            "garantia": contrato["garantia"],
            "direccion_garantia": contrato["direccion_garantia"],
            "garantes": [dict(row) for row in garantes],
            "fecha_inicio": contrato["fecha_inicio"],
            "fecha_fin": contrato["fecha_fin"],
            "importe_inicial": contrato["importe_inicial"],
            "deposito": contrato["deposito"],
            "tipo_ajuste": contrato["tipo_ajuste"],
            "periodicidad": contrato["periodicidad"],
            "estado": contrato["estado"],
        }
    finally:
        db.close()

def _fusionar_vigencias(filas: list) -> list:
    """Junta renglones consecutivos del mismo contrato que repiten el importe.

    `valor_historico` guarda un renglón por mes, así que un alquiler que estuvo
    cuatro meses sin ajustarse ocupa cuatro filas idénticas salvo por las fechas.
    Lo que interesa es cuándo cambió el importe, no cuántos meses aguantó: la racha
    se colapsa en un solo período, del primer `fecha_inicio` al último `fecha_fin`.

    Un hueco entre un renglón y el siguiente corta la racha aunque el importe
    coincida: son dos vigencias distintas, no una.

    Espera las filas ordenadas por contrato y `fecha_inicio` ascendente.
    """
    vigencias = []
    for fila in filas:
        anterior = vigencias[-1] if vigencias else None
        sigue_la_racha = (
            anterior is not None
            and anterior["contrato"] == fila["contrato"]
            and anterior["importe_inicial"] == fila["importe_inicial"]
            and fila["fecha_inicio"] == anterior["fecha_fin"] + timedelta(days=1)
        )
        if sigue_la_racha:
            anterior["fecha_fin"] = fila["fecha_fin"]
        else:
            vigencias.append(dict(fila))
    return vigencias


def get_valores_historicos_por_cliente(cliente_id: int) -> list:
    """Historial de importes de los contratos ligados a un cliente.

    Un cliente llega a un contrato por dos caminos: como inquilino, por
    `contrato_inquilino`; como propietario, por la propiedad del contrato. Los
    meses que comparten importe se devuelven como un solo período, así que la
    lista queda con un renglón por ajuste.
    """
    db = SessionLocal()
    try:
        query = text("""
            SELECT vh.contrato, vh.fecha_inicio, vh.fecha_fin, vh.importe_inicial,
                   p.direccion
            FROM valor_historico vh
            JOIN contrato c ON c.contrato_id = vh.contrato
            JOIN propiedad p ON p.propiedad_id = c.propiedad
            WHERE vh.contrato IN (
                    SELECT ci.contrato
                    FROM contrato_inquilino ci
                    WHERE ci.cliente = :cliente_id
                UNION
                    SELECT c2.contrato_id
                    FROM contrato c2
                    JOIN propiedad_propietario pp ON pp.propiedad_id = c2.propiedad
                    WHERE pp.cliente = :cliente_id
            )
            ORDER BY vh.contrato, vh.fecha_inicio
        """)
        filas = [dict(row) for row in db.execute(query, {"cliente_id": cliente_id}).mappings().all()]
        vigencias = _fusionar_vigencias(filas)
        # La consulta ordena por contrato para poder fusionar; la pantalla quiere lo
        # más reciente arriba.
        vigencias.sort(key=lambda vigencia: vigencia["fecha_inicio"], reverse=True)
        return vigencias
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

        db.commit()
        db.refresh(contrato)
        return contrato
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def eliminar_contrato(id: int):
    db = SessionLocal()
    try:
        contrato = db.query(Contrato).where(Contrato.contrato_id == id).first()
        db.delete(contrato)
        db.commit()
    finally:
        db.close()