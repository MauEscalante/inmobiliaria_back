"""Bitácora de altas: escritura desde los servicios y lectura para el panel."""

from sqlalchemy import text

from app.database.connection import SessionLocal
from app.models.evento import Evento
from app.utils.helpers import serializar_fila

EVENTO_SELECT = """
    SELECT e.evento_id, e.tipo, e.descripcion, e.entidad_tipo, e.entidad_id, e.creado_en
    FROM evento e
"""

# El filtro se calcula en la base y no en Python para que la ventana se mida
# contra el mismo reloj con el que se escribió creado_en (server_default=NOW()).
DESDE = " WHERE e.creado_en >= NOW() - INTERVAL :dias DAY"


def registrar(
    db,
    tipo: str,
    descripcion: str,
    entidad_tipo: str | None = None,
    entidad_id: str | int | None = None,
) -> None:
    """Deja el evento listo en la sesión que se le pasa, sin commitear.

    La sesión viene por parámetro a propósito: así el evento entra en la misma
    transacción que el alta que lo origina y un rollback se lo lleva puesto, en
    vez de dejar registrada una creación que nunca ocurrió.
    """
    db.add(Evento(
        tipo=tipo,
        descripcion=descripcion,
        entidad_tipo=entidad_tipo,
        entidad_id=str(entidad_id) if entidad_id is not None else None,
    ))


def get_eventos(dias: int, limit: int, offset: int) -> tuple[list, int]:
    """Página de eventos de los últimos `dias`, del más nuevo al más viejo."""
    db = SessionLocal()
    try:
        params = {"dias": dias}

        total = db.execute(
            text(f"SELECT COUNT(*) FROM evento e{DESDE}"), params
        ).scalar() or 0

        # Desempate por evento_id: dos altas de la misma transacción comparten
        # creado_en al segundo, y sin desempate el orden variaría entre páginas.
        filas = db.execute(
            text(
                f"{EVENTO_SELECT}{DESDE}"
                " ORDER BY e.creado_en DESC, e.evento_id DESC"
                " LIMIT :_limit OFFSET :_offset"
            ),
            {**params, "_limit": limit, "_offset": offset},
        ).mappings().all()

        return [serializar_fila(fila) for fila in filas], total
    finally:
        db.close()
