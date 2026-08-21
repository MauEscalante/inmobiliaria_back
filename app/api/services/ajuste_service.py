"""Persistencia de los trabajos de ajuste de recibos.

El estado vive en la base y no en memoria a proposito: `uvicorn --reload` reinicia
el proceso con cada cambio, y un trabajo en curso se perderia sin dejar rastro.
"""

from app.database.connection import SessionLocal
from app.models.ajuste_recibo import EstadoAjuste
from app.utils.helpers import serializar_fila
from sqlalchemy import text

AJUSTE_SELECT = """
    SELECT ajuste_id, mes, anio, estado, contratos_ajustados,
           propiedades_marcadas_adeuda, error, creado_en, finalizado_en
    FROM ajuste_recibo
"""

# Longitud de la columna `error`; los mensajes largos se recortan para que guardar
# el fallo nunca falle a su vez.
MAX_ERROR = 500


def get_by_id(ajuste_id: int) -> dict | None:
    db = SessionLocal()
    try:
        fila = db.execute(
            text(AJUSTE_SELECT + " WHERE ajuste_id = :ajuste_id"),
            {"ajuste_id": ajuste_id},
        ).mappings().first()
        return serializar_fila(fila) if fila else None
    finally:
        db.close()


def hay_activo() -> bool:
    """Hay un trabajo pendiente o corriendo, asi que no se puede arrancar otro."""
    db = SessionLocal()
    try:
        fila = db.execute(
            text(
                "SELECT 1 FROM ajuste_recibo"
                " WHERE estado IN ('pendiente', 'en_proceso') LIMIT 1"
            )
        ).first()
        return fila is not None
    finally:
        db.close()


def crear(mes: int, anio: int) -> dict:
    db = SessionLocal()
    try:
        resultado = db.execute(
            text(
                "INSERT INTO ajuste_recibo (mes, anio, estado)"
                " VALUES (:mes, :anio, :estado)"
            ),
            {"mes": mes, "anio": anio, "estado": EstadoAjuste.pendiente.value},
        )
        ajuste_id = resultado.lastrowid
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return get_by_id(ajuste_id)


def marcar_en_proceso(ajuste_id: int) -> None:
    db = SessionLocal()
    try:
        db.execute(
            text("UPDATE ajuste_recibo SET estado = :estado WHERE ajuste_id = :ajuste_id"),
            {"estado": EstadoAjuste.en_proceso.value, "ajuste_id": ajuste_id},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def marcar_completado(ajuste_id: int, resultado: dict) -> None:
    db = SessionLocal()
    try:
        db.execute(
            text("""
                UPDATE ajuste_recibo
                SET estado = :estado,
                    contratos_ajustados = :contratos,
                    propiedades_marcadas_adeuda = :propiedades,
                    finalizado_en = NOW()
                WHERE ajuste_id = :ajuste_id
            """),
            {
                "estado": EstadoAjuste.completado.value,
                "contratos": resultado.get("contratos_ajustados"),
                "propiedades": resultado.get("propiedades_marcadas_adeuda"),
                "ajuste_id": ajuste_id,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def marcar_fallido(ajuste_id: int, mensaje: str) -> None:
    db = SessionLocal()
    try:
        db.execute(
            text("""
                UPDATE ajuste_recibo
                SET estado = :estado, error = :error, finalizado_en = NOW()
                WHERE ajuste_id = :ajuste_id
            """),
            {
                "estado": EstadoAjuste.fallido.value,
                "error": (mensaje or "Error desconocido")[:MAX_ERROR],
                "ajuste_id": ajuste_id,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def limpiar_interrumpidos() -> int:
    """Cierra los trabajos que quedaron a medias cuando se corto el proceso.

    Se llama al arrancar la app. Sin esto, un corte en medio de un ajuste deja la
    fila en 'en_proceso' para siempre y el candado de hay_activo() bloquearia
    todos los ajustes siguientes.
    """
    db = SessionLocal()
    try:
        resultado = db.execute(
            text("""
                UPDATE ajuste_recibo
                SET estado = :fallido,
                    error = 'El proceso se reinicio mientras el ajuste estaba en curso',
                    finalizado_en = NOW()
                WHERE estado IN ('pendiente', 'en_proceso')
            """),
            {"fallido": EstadoAjuste.fallido.value},
        )
        db.commit()
        return resultado.rowcount
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
