from app.api.services.cliente_services import find_or_create_cliente
from app.api.services.evento_service import registrar
from app.models.cliente import Cliente, ClienteTipo
from app.models.evento import TipoEvento
from app.models.propiedad import EstadoAlquiler, EstadoPropiedad, Propiedad, PropiedadPropietario
from app.database.connection import SessionLocal
from app.utils.helpers import serializar_fila
from sqlalchemy import text

# Campos que el cliente puede setear; el resto (estado inicial, id) lo decide el backend.
PROPIEDAD_FIELDS = {"direccion", "ambientes"}

# Columnas que acepta la edición parcial.
PROPIEDAD_EDITABLES = ("direccion", "ambientes", "estado", "estado_alquiler")

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
                 AND c.estado = 'Activo'
                 AND CURDATE() BETWEEN c.fecha_inicio AND c.fecha_fin
               ORDER BY c.fecha_inicio DESC, c.contrato_id DESC
               LIMIT 1)) AS inquilino
    FROM propiedad p
"""

PROPIETARIOS_SELECT = """
    SELECT cl.cliente_num, CONCAT(cl.nombre, ' ', cl.apellido) AS nombre,
           pp.porcentaje, pp.comision
    FROM propiedad_propietario pp
    JOIN cliente cl ON cl.cliente_num = pp.cliente
    WHERE pp.propiedad_id = :propiedad_id
    ORDER BY cl.apellido
"""


def _filtros(estado: str | None, estado_alquiler: str | None, q: str | None) -> tuple[str, dict]:
    condiciones = []
    params: dict = {}

    if estado:
        condiciones.append("p.estado = :estado")
        params["estado"] = estado
    if estado_alquiler:
        condiciones.append("p.estado_alquiler = :estado_alquiler")
        params["estado_alquiler"] = estado_alquiler
    if q:
        condiciones.append("p.direccion LIKE :q")
        params["q"] = f"%{q}%"

    where = f" WHERE {' AND '.join(condiciones)}" if condiciones else ""
    return where, params


def get_inmuebles(
    estado: str | None, estado_alquiler: str | None, q: str | None, limit: int, offset: int
) -> tuple[list, int]:
    """Página de propiedades más el total que matchea el filtro."""
    db = SessionLocal()
    try:
        where, params = _filtros(estado, estado_alquiler, q)

        total = db.execute(
            text(f"SELECT COUNT(*) FROM propiedad p{where}"), params
        ).scalar() or 0

        query = text(
            PROPIEDAD_SELECT + where + " ORDER BY p.propiedad_id LIMIT :_limit OFFSET :_offset"
        )
        filas = db.execute(query, {**params, "_limit": limit, "_offset": offset}).mappings().all()
        return [serializar_fila(fila) for fila in filas], total
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
            text(PROPIETARIOS_SELECT), {"propiedad_id": propiedad_id}
        ).mappings().all()

        detalle = serializar_fila(propiedad)
        detalle["propietarios"] = [serializar_fila(fila) for fila in propietarios]
        return detalle
    finally:
        db.close()


class PropietarioInexistenteError(Exception):
    """El alta referencia un cliente_num que no existe."""

    def __init__(self, cliente_num):
        self.cliente_num = cliente_num
        super().__init__(f"El propietario {cliente_num} no existe")


def get_propietarios_de_propiedad(propiedad_id: int) -> list:
    """Sub-recurso /propiedades/{id}/propietarios: la asociación con su porcentaje."""
    db = SessionLocal()
    try:
        filas = db.execute(
            text(PROPIETARIOS_SELECT), {"propiedad_id": propiedad_id}
        ).mappings().all()
        return [serializar_fila(fila) for fila in filas]
    finally:
        db.close()


def create_inmueble(propiedad_data: dict) -> dict:
    """Crea la propiedad y, en la misma transacción, sus propietarios.

    Los propietarios que no existen se dan de alta como clientes acá: es la única
    forma de que un propietario entre al sistema, igual que el inquilino entra al
    crear el contrato.
    """
    db = SessionLocal()
    try:
        campos = {k: v for k, v in propiedad_data.items() if k in PROPIEDAD_FIELDS}
        nueva_propiedad = Propiedad(
            **campos,
            estado=EstadoPropiedad.Activa,
            estado_alquiler=EstadoAlquiler.Adeuda,
        )
        db.add(nueva_propiedad)
        db.flush()  # asigna propiedad_id antes del commit
        propiedad_id = nueva_propiedad.propiedad_id

        registrar(
            db,
            TipoEvento.propiedad_creada.value,
            f"Ingresó la propiedad {nueva_propiedad.direccion}",
            "propiedad",
            propiedad_id,
        )

        # La comisión es de la propiedad pero se guarda en cada fila de propietario,
        # que es de donde la lee PROPIEDAD_SELECT.
        comision = propiedad_data.get("comision")

        for propietario_data in propiedad_data.get("propietarios") or []:
            cliente_num = propietario_data.get("cliente_num")
            if cliente_num:
                # Sin este chequeo el cliente_num inexistente reventaba como error
                # de FK, o sea un 500 en vez de un body inválido.
                if not db.get(Cliente, cliente_num):
                    raise PropietarioInexistenteError(cliente_num)
            else:
                cliente_num = find_or_create_cliente(db, propietario_data, ClienteTipo.Propietario).cliente_num

            db.add(PropiedadPropietario(
                propiedad_id=propiedad_id,
                cliente_num=cliente_num,
                porcentaje=propietario_data.get("porcentaje") or 100,
                comision=comision,
            ))

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return get_inmueble_by_id(propiedad_id)


def update_inmueble(propiedad_id: int, propiedad_data: dict) -> dict:
    """Reemplazo total. El schema garantiza que vengan todas las columnas NOT NULL."""
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


def patch_inmueble(propiedad_id: int, campos: dict) -> dict:
    """Actualización parcial: reemplaza a update_direccion_by_id y update_estado_by_id."""
    editables = {campo: valor for campo, valor in campos.items() if campo in PROPIEDAD_EDITABLES}
    if not editables:
        return get_inmueble_by_id(propiedad_id)

    db = SessionLocal()
    try:
        asignaciones = ", ".join(f"{campo} = :{campo}" for campo in editables)
        query = text(f"UPDATE propiedad SET {asignaciones} WHERE propiedad_id = :propiedad_id")
        db.execute(query, {**editables, "propiedad_id": propiedad_id})
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
