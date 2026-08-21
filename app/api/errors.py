"""Helpers para levantar errores con una forma única.

El `detail` viaja como dict y no como string suelto: el handler global de
main.py lo convierte al envelope ErrorResponse, de modo que el cliente recibe
siempre `error`/`message`/`details` con un `code` que puede matchear por
programa, en vez de tener que parsear prosa en español.
"""

from fastapi import HTTPException, status


def _detalle(message: str, details: list[dict] | None = None) -> dict:
    return {"message": message, "details": details or []}


def raise_not_found(recurso: str, identificador, *, femenino: bool = False) -> None:
    """404 de un recurso. `femenino` hace concordar el participio: propiedad no encontrada."""
    terminacion = "a" if femenino else "o"
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=_detalle(
            f"{recurso} no encontrad{terminacion}",
            [{"field": None, "message": f"No existe {recurso} con id {identificador}", "code": "not_found"}],
        ),
    )


def raise_conflict(message: str, field: str | None = None, code: str = "conflict") -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=_detalle(message, [{"field": field, "message": message, "code": code}]),
    )


def raise_unprocessable(message: str, field: str | None = None, code: str = "invalid") -> None:
    """422: el body está bien formado pero no se puede procesar.

    Es lo que corresponde a las reglas de negocio que Pydantic no puede validar
    sola (saldo de caja, período cerrado, referencias inexistentes).
    """
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=_detalle(message, [{"field": field, "message": message, "code": code}]),
    )
