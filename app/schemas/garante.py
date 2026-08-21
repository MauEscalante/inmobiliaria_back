"""Schemas del sub-recurso garante, que cuelga de un contrato."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.validators import EMAIL_PATTERN


class GaranteCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=15)
    apellido: str = Field(..., min_length=1, max_length=15)
    telefono: str = Field(..., min_length=1, max_length=15)
    dni: str | None = Field(None, max_length=9)
    sueldo: Decimal | None = Field(None, ge=0, decimal_places=2)
    email: str | None = Field(None, max_length=100, pattern=EMAIL_PATTERN)


class GaranteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    garante_id: int
    nombre: str
    apellido: str
    telefono: str
    dni: str | None = None
    sueldo: float | None = None
    email: str | None = None
