"""Schemas del recurso cliente.

El alta no se expone: los clientes se crean solos al registrar un contrato
(inquilino) o una propiedad (propietario). Por eso no hay ClienteCreate.

Nota sobre montos: en los schemas de entrada se usa Decimal para no perder
precisión contra las columnas DECIMAL(12,2); en los de salida se usa float
porque Pydantic v2 serializa Decimal como string en JSON y el cliente espera
un número.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

# Largos tomados de las columnas reales de `cliente` (app/models/cliente.py).
from app.schemas.validators import EMAIL_PATTERN


class ClienteTipoDerivado(StrEnum):
    """El tipo no se guarda: se deriva de las relaciones, y puede ser las dos cosas."""

    Inquilino = "Inquilino"
    Propietario = "Propietario"
    Ambos = "Ambos"


class ClienteBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=15)
    apellido: str = Field(..., min_length=1, max_length=15)
    dni: str = Field(..., min_length=1, max_length=9)
    telefono: str = Field(..., min_length=1, max_length=15)
    email: str | None = Field(None, max_length=100, pattern=EMAIL_PATTERN)
    direccion: str | None = Field(None, max_length=255)
    cuil: str | None = Field(None, max_length=15)
    nacionalidad: str | None = Field(None, max_length=50)


class ClienteUpdate(ClienteBase):
    """Reemplazo total (PUT): todos los campos obligatorios viajan siempre."""


class ClientePatch(BaseModel):
    """Actualización parcial (PATCH): lo que no se manda, no se toca.

    Reemplaza a los viejos PUT /clientes/email/{id} y /clientes/telefono/{id},
    que mandaban el valor por query string.
    """

    nombre: str | None = Field(None, min_length=1, max_length=15)
    apellido: str | None = Field(None, min_length=1, max_length=15)
    dni: str | None = Field(None, min_length=1, max_length=9)
    telefono: str | None = Field(None, min_length=1, max_length=15)
    email: str | None = Field(None, max_length=100, pattern=EMAIL_PATTERN)
    direccion: str | None = Field(None, max_length=255)
    cuil: str | None = Field(None, max_length=15)
    nacionalidad: str | None = Field(None, max_length=50)


class ClienteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cliente_num: int
    nombre: str
    apellido: str
    dni: str
    telefono: str
    email: str | None = None
    direccion: str | None = None
    cuil: str | None = None
    nacionalidad: str | None = None
    tipo: ClienteTipoDerivado | None = Field(
        None, description="Derivado de contratos y propiedades; null si no tiene ninguna"
    )
    comision: float | None = Field(
        None, description="Comisión del propietario. Null si el cliente no es propietario."
    )
