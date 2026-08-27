"""Helpers compartidos por la capa de servicios.

Acá vive la serialización de filas SQL, que antes estaba duplicada casi idéntica
en cliente_services, propiedades_services y libro_diario_service.
"""

from datetime import date, datetime
from decimal import Decimal

from fastapi import Query
from sqlalchemy import text

from app.schemas.common import PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX


def serializar_fila(row) -> dict:
    """Convierte una fila de SQLAlchemy a dict JSON-serializable.

    Decimal pasa a float porque el cliente espera números: Pydantic v2 serializa
    Decimal como string en JSON. La precisión se cuida en la entrada, donde los
    schemas usan Decimal contra las columnas DECIMAL(12,2).
    """
    fila = dict(row)
    for campo, valor in fila.items():
        if isinstance(valor, Decimal):
            fila[campo] = float(valor)
        elif isinstance(valor, datetime):
            fila[campo] = valor.isoformat()
        elif isinstance(valor, date):
            fila[campo] = valor.isoformat()
    return fila


class Paginacion:
    """Parámetros de paginación, compartidos por todas las colecciones.

    Se usa como dependencia: `paginacion: Paginacion = Depends()`.
    """

    def __init__(
        self,
        page: int = Query(1, ge=1, description="Número de página, arranca en 1"),
        page_size: int = Query(
            PAGE_SIZE_DEFAULT, ge=1, le=PAGE_SIZE_MAX,
            description=f"Filas por página (máximo {PAGE_SIZE_MAX})",
        ),
    ):
        self.page = page
        self.page_size = page_size

    @property
    def limit(self) -> int:
        return self.page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def contar(db, from_where_sql: str, params: dict) -> int:
    """Total de filas que matchean, para calcular la cantidad de páginas."""
    return db.execute(text(f"SELECT COUNT(*) FROM {from_where_sql}"), params).scalar() or 0

