"""Modelos compartidos por todos los recursos: paginación y formato de error."""

from pydantic import BaseModel, Field

# Coincide con los límites que fija el checklist de la guía de diseño:
# tamaño por defecto 20, tope 100.
PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MAX = 100


class Page[T](BaseModel):
    """Página de una colección. Toda colección se devuelve envuelta en esto."""

    items: list[T]
    total: int = Field(..., description="Total de filas que matchean el filtro")
    page: int
    page_size: int
    pages: int = Field(..., description="Cantidad total de páginas")

    @classmethod
    def crear(cls, items: list[T], total: int, page: int, page_size: int) -> Page[T]:
        pages = (total + page_size - 1) // page_size if page_size else 0
        return cls(items=items, total=total, page=page, page_size=page_size, pages=pages)


class ErrorDetail(BaseModel):
    """Error a nivel campo. `field` es None cuando el error no es de un campo puntual."""

    field: str | None = None
    message: str
    code: str


class ErrorResponse(BaseModel):
    """Envelope único de error. Todos los 4xx/5xx salen con esta forma."""

    error: str = Field(..., description="Nombre del tipo de error, p. ej. NotFound")
    message: str = Field(..., description="Mensaje legible para mostrar al usuario")
    details: list[ErrorDetail] | None = None
    timestamp: str
    path: str


# Atajo para declarar los `responses` de OpenAPI sin repetir el modelo.
def error_responses(*codigos: int) -> dict:
    return {codigo: {"model": ErrorResponse} for codigo in codigos}
