from app.database.connection import SessionLocal
from app.api.services.propiedades_services import _serializar
from sqlalchemy import text

# Clientes que ya son propietarios, con la comisión que tienen registrada. La
# comisión no vive en `cliente` sino en `propiedad_propietario`, y es siempre la
# misma para el propietario, por eso alcanza con tomar MAX.
PROPIETARIO_SELECT = """
    SELECT cl.cliente_num, cl.nombre, cl.apellido, cl.dni,
           (SELECT MAX(pp.comision)
              FROM propiedad_propietario pp
             WHERE pp.cliente = cl.cliente_num) AS comision
    FROM cliente cl
    WHERE cl.tipo = 'Propietario'
    ORDER BY cl.apellido, cl.nombre
"""


def get_propietarios() -> list:
    db = SessionLocal()
    try:
        return [_serializar(row) for row in db.execute(text(PROPIETARIO_SELECT)).mappings().all()]
    finally:
        db.close()
