from app.api.services.evento_service import registrar
from app.models.cliente import Cliente, ClienteTipo
from app.models.evento import TipoEvento
from app.database.connection import SessionLocal
from app.utils.helpers import serializar_fila
from sqlalchemy import text

# Campos que la edición puede tocar. El tipo no está: se deriva de las relaciones.
CLIENTE_FIELDS = ("nombre", "apellido", "dni", "telefono", "email", "direccion", "cuil", "nacionalidad")

# El tipo del cliente se deriva de dónde aparece: si tiene propiedades es Propietario,
# si tiene contratos es Inquilino, y puede ser las dos cosas a la vez. La columna
# cliente.tipo solo se usa como respaldo para clientes que todavía no tienen relaciones.
# La comisión se trae acá para que el selector de propietarios pueda usar esta misma
# colección filtrada, en vez del viejo endpoint /propietarios.
CLIENTE_SELECT = """
    SELECT
      c.cliente_num, c.nombre, c.apellido, c.dni, c.telefono,
      c.email, c.direccion, c.cuil, c.nacionalidad,
      CASE
        WHEN pp.n > 0 AND ci.n > 0 THEN 'Ambos'
        WHEN pp.n > 0 THEN 'Propietario'
        WHEN ci.n > 0 THEN 'Inquilino'
        ELSE c.tipo
      END AS tipo,
      (SELECT MAX(ppc.comision)
         FROM propiedad_propietario ppc
        WHERE ppc.cliente = c.cliente_num) AS comision
    FROM cliente c
    LEFT JOIN (SELECT cliente, COUNT(*) n FROM propiedad_propietario GROUP BY cliente) pp
           ON pp.cliente = c.cliente_num
    LEFT JOIN (SELECT cliente, COUNT(*) n FROM contrato_inquilino GROUP BY cliente) ci
           ON ci.cliente = c.cliente_num
"""

# Un cliente que es las dos cosas cuenta como propietario y como inquilino, así que
# los filtros por tipo incluyen 'Ambos'. Esto mantiene el resultado del viejo
# GET /propietarios, que salía de un JOIN contra propiedad_propietario.
TIPOS_EQUIVALENTES = {
    "Propietario": ("Propietario", "Ambos"),
    "Inquilino": ("Inquilino", "Ambos"),
    "Ambos": ("Ambos",),
}


def _filtros(tipo: str | None, q: str | None) -> tuple[str, dict]:
    """Arma el WHERE de la colección sobre la subconsulta derivada."""
    condiciones = []
    params: dict = {}

    if tipo:
        equivalentes = TIPOS_EQUIVALENTES.get(tipo, (tipo,))
        marcadores = []
        for indice, valor in enumerate(equivalentes):
            clave = f"tipo_{indice}"
            marcadores.append(f":{clave}")
            params[clave] = valor
        condiciones.append(f"cl.tipo IN ({', '.join(marcadores)})")

    if q:
        condiciones.append(
            "(cl.nombre LIKE :q OR cl.apellido LIKE :q OR cl.dni LIKE :q OR cl.email LIKE :q)"
        )
        params["q"] = f"%{q}%"

    where = f" WHERE {' AND '.join(condiciones)}" if condiciones else ""
    return where, params


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

    # Solo los propietarios van al panel de actividad. Un inquilino nuevo no
    # genera evento propio: ya se ve en el "Se creó el contrato" que lo trajo.
    if tipo == ClienteTipo.Propietario:
        registrar(
            db,
            TipoEvento.propietario_creado.value,
            f"Cliente nuevo - {cliente.nombre} {cliente.apellido}".strip(),
            "cliente",
            cliente.cliente_num,
        )

    return cliente


def get_clientes(tipo: str | None, q: str | None, limit: int, offset: int) -> tuple[list, int]:
    """Página de clientes más el total que matchea el filtro."""
    db = SessionLocal()
    try:
        where, params = _filtros(tipo, q)
        derivada = f"({CLIENTE_SELECT}) AS cl"

        total = db.execute(
            text(f"SELECT COUNT(*) FROM {derivada}{where}"), params
        ).scalar() or 0

        query = text(
            f"SELECT * FROM {derivada}{where}"
            " ORDER BY cl.apellido, cl.nombre"
            " LIMIT :_limit OFFSET :_offset"
        )
        filas = db.execute(query, {**params, "_limit": limit, "_offset": offset}).mappings().all()
        return [serializar_fila(fila) for fila in filas], total
    finally:
        db.close()


def get_cliente_by_id(cliente_id: int) -> dict:
    db = SessionLocal()
    try:
        query = text(CLIENTE_SELECT + " WHERE c.cliente_num = :cliente_id")
        cliente = db.execute(query, {"cliente_id": cliente_id}).mappings().first()
        return serializar_fila(cliente) if cliente else None
    finally:
        db.close()


def buscar_duplicado(cliente_id: int, dni: str, email: str) -> str:
    """Devuelve 'dni' o 'email' si otro cliente ya usa ese valor, o None.

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
                return "dni"

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
    """Reemplazo total (PUT). El alta sigue siendo automática, esto solo edita."""
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


def patch_cliente(cliente_id: int, campos: dict) -> dict:
    """Actualización parcial: solo escribe las columnas presentes en `campos`.

    Reemplaza a update_email y update_celular, que además de mandar el valor por
    query string no verificaban que el cliente existiera.
    """
    editables = {campo: valor for campo, valor in campos.items() if campo in CLIENTE_FIELDS}
    if not editables:
        return get_cliente_by_id(cliente_id)

    db = SessionLocal()
    try:
        asignaciones = ", ".join(f"{campo} = :{campo}" for campo in editables)
        query = text(f"UPDATE cliente SET {asignaciones} WHERE cliente_num = :cliente_id")
        db.execute(query, {**editables, "cliente_id": cliente_id})
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return get_cliente_by_id(cliente_id)
