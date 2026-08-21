from decimal import Decimal

from app.models.cliente import Cliente, ClienteTipo
from app.database.connection import SessionLocal
from sqlalchemy import text

# Campos que la edición puede tocar. El tipo no está: se deriva de las relaciones.
CLIENTE_FIELDS = ("nombre", "apellido", "dni", "telefono", "email", "direccion", "cuil", "nacionalidad")

# El tipo del cliente se deriva de dónde aparece: si tiene propiedades es Propietario,
# si tiene contratos es Inquilino, y puede ser las dos cosas a la vez. La columna
# cliente.tipo solo se usa como respaldo para clientes que todavía no tienen relaciones.
CLIENTE_SELECT = """
    SELECT
      c.cliente_num, c.nombre, c.apellido, c.dni, c.telefono,
      c.email, c.direccion, c.cuil, c.nacionalidad,
      CASE
        WHEN pp.n > 0 AND ci.n > 0 THEN 'Ambos'
        WHEN pp.n > 0 THEN 'Propietario'
        WHEN ci.n > 0 THEN 'Inquilino'
        ELSE c.tipo
      END AS tipo
    FROM cliente c
    LEFT JOIN (SELECT cliente, COUNT(*) n FROM propiedad_propietario GROUP BY cliente) pp
           ON pp.cliente = c.cliente_num
    LEFT JOIN (SELECT cliente, COUNT(*) n FROM contrato_inquilino GROUP BY cliente) ci
           ON ci.cliente = c.cliente_num
"""


def _serializar(row) -> dict:
    cliente = dict(row)
    # Decimal no es serializable a JSON por FastAPI sin convertirlo antes.
    if isinstance(cliente.get("comision"), Decimal):
        cliente["comision"] = float(cliente["comision"])
    return cliente


def find_or_create_cliente(db, cliente_data: dict, tipo: ClienteTipo) -> Cliente:
    """Busca un cliente por DNI dentro de la sesión dada; si no existe, lo crea con el tipo indicado."""
    dni = (cliente_data.get("dni") or "").strip()

    cliente = None
    if dni:
        cliente = db.query(Cliente).filter(Cliente.dni == dni).first()

    if cliente:
        return cliente

    cliente = Cliente(
        nombre=cliente_data.get("nombre", ""),
        apellido=cliente_data.get("apellido", ""),
        dni=dni,
        telefono=cliente_data.get("telefono", ""),
        email=cliente_data.get("email") or None,
        direccion=cliente_data.get("direccion") or None,
        cuil=cliente_data.get("cuil") or None,
        nacionalidad=cliente_data.get("nacionalidad") or None,
        tipo=tipo,
    )
    db.add(cliente)
    db.flush()
    return cliente


def get_clientes() -> list:
    db = SessionLocal()
    try:
        query = text(CLIENTE_SELECT + " ORDER BY c.apellido, c.nombre")
        return [_serializar(row) for row in db.execute(query).mappings().all()]
    finally:
        db.close()


def get_cliente_by_id(cliente_id: int) -> dict:
    db = SessionLocal()
    try:
        query = text(CLIENTE_SELECT + " WHERE c.cliente_num = :cliente_id")
        cliente = db.execute(query, {"cliente_id": cliente_id}).mappings().first()
        return _serializar(cliente) if cliente else None
    finally:
        db.close()


def get_propietarios() -> list:
    """Clientes que ya son propietarios de alguna propiedad, para el selector del alta."""
    db = SessionLocal()
    try:
        query = text("""
            SELECT c.cliente_num, c.nombre, c.apellido, c.dni, MAX(pp.comision) AS comision
            FROM cliente c
            JOIN propiedad_propietario pp ON pp.cliente = c.cliente_num
            GROUP BY c.cliente_num, c.nombre, c.apellido, c.dni
            ORDER BY c.apellido, c.nombre
        """)
        return [_serializar(row) for row in db.execute(query).mappings().all()]
    finally:
        db.close()


def buscar_duplicado(cliente_id: int, dni: str, email: str) -> str:
    """Devuelve 'DNI' o 'email' si otro cliente ya usa ese valor, o None.

    El modelo declara ambos como UNIQUE pero la tabla no tiene esos índices, así que
    la unicidad se valida acá. Importa: find_or_create_cliente deduplica por DNI, y
    dos clientes con el mismo DNI romperían el alta automática.
    """
    db = SessionLocal()
    try:
        if dni:
            existe = db.execute(
                text("SELECT 1 FROM cliente WHERE dni = :dni AND cliente_num <> :cliente_id LIMIT 1"),
                {"dni": dni, "cliente_id": cliente_id},
            ).first()
            if existe:
                return "DNI"

        if email:
            existe = db.execute(
                text("SELECT 1 FROM cliente WHERE email = :email AND cliente_num <> :cliente_id LIMIT 1"),
                {"email": email, "cliente_id": cliente_id},
            ).first()
            if existe:
                return "email"

        return None
    finally:
        db.close()


def update_cliente(cliente_id: int, cliente_data: dict) -> dict:
    """Corrige los datos de un cliente. El alta sigue siendo automática, esto solo edita."""
    db = SessionLocal()
    try:
        query = text("""
            UPDATE cliente
            SET nombre = :nombre,
                apellido = :apellido,
                dni = :dni,
                telefono = :telefono,
                email = :email,
                direccion = :direccion,
                cuil = :cuil,
                nacionalidad = :nacionalidad
            WHERE cliente_num = :cliente_id
        """)
        params = {campo: (cliente_data.get(campo) or None) for campo in CLIENTE_FIELDS}
        params["cliente_id"] = cliente_id
        db.execute(query, params)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return get_cliente_by_id(cliente_id)


def update_email(cliente_id: int, email: str) -> None:
    db = SessionLocal()
    try:
        query = text("""
        UPDATE cliente
        SET email= :email
        WHERE cliente_num= :cliente_id
        """)
        db.execute(query, {"email": email, "cliente_id": cliente_id})
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def update_celular(cliente_id: int, telefono: str) -> None:
    db = SessionLocal()
    try:
        query = text("""
        UPDATE cliente
        SET telefono= :telefono
        WHERE cliente_num= :cliente_id
        """)
        db.execute(query, {"telefono": telefono, "cliente_id": cliente_id})
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
