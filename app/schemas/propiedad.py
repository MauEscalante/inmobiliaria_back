"""Schemas del recurso propiedad y de su sub-recurso propietarios."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.propiedad import EstadoAlquiler, EstadoPropiedad
from app.schemas.validators import EMAIL_PATTERN


class PropietarioInput(BaseModel):
    """Propietario dentro del alta: o uno existente por cliente_num, o los datos
    para darlo de alta como cliente nuevo."""

    cliente_num: int | None = None
    porcentaje: Decimal = Field(..., gt=0, le=100, decimal_places=2)
    nombre: str | None = Field(None, max_length=15)
    apellido: str | None = Field(None, max_length=15)
    telefono: str | None = Field(None, max_length=15)
    dni: str | None = Field(None, max_length=9)
    cuil: str | None = Field(None, max_length=15)
    nacionalidad: str | None = Field(None, max_length=50)
    direccion: str | None = Field(None, max_length=255)
    email: str | None = Field(None, max_length=100, pattern=EMAIL_PATTERN)

    @model_validator(mode="after")
    def _existente_o_con_dni(self):
        # Antes vivía en propiedades_controller como un 400 suelto; acá sale como
        # 422 con el campo señalado.
        if not self.cliente_num and not (self.dni or "").strip():
            raise ValueError("un propietario nuevo necesita DNI")
        return self


class PropiedadCreate(BaseModel):
    direccion: str = Field(..., min_length=1, max_length=255)
    ambientes: int | None = Field(None, ge=0)
    comision: Decimal | None = Field(
        None, ge=0, decimal_places=2,
        description="Comisión del propietario; se replica en cada fila de propietario",
    )
    propietarios: list[PropietarioInput] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _porcentajes_suman_100(self):
        suma = sum(p.porcentaje for p in self.propietarios)
        if abs(suma - 100) > Decimal("0.01"):
            raise ValueError(f"los porcentajes deben sumar 100%, suman {suma}%")
        return self


class PropiedadUpdate(BaseModel):
    """Reemplazo total (PUT). Todos los campos de la fila viajan siempre.

    Antes el UPDATE escribía NULL en las columnas que faltaran en el body, lo que
    reventaba contra las columnas NOT NULL; ahora son obligatorias acá.
    """

    direccion: str = Field(..., min_length=1, max_length=255)
    ambientes: int | None = Field(None, ge=0)
    estado: EstadoPropiedad
    estado_alquiler: EstadoAlquiler


class PropiedadPatch(BaseModel):
    """Actualización parcial. Reemplaza a /update/direccion/{id} y /update/estado/{id}."""

    direccion: str | None = Field(None, min_length=1, max_length=255)
    ambientes: int | None = Field(None, ge=0)
    estado: EstadoPropiedad | None = None
    estado_alquiler: EstadoAlquiler | None = None


class PropietarioDetalle(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cliente_num: int
    nombre: str = Field(..., description="Nombre y apellido concatenados")
    porcentaje: float
    comision: float | None = None


class PropiedadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    propiedad_id: int
    direccion: str
    ambientes: int | None = None
    propietario: str | None = Field(
        None, description='Nombre completo; si hay varios vienen separados por ", "'
    )
    inquilino: str | None = Field(
        None, description="Inquilino del contrato vigente a la fecha"
    )
    comision: float | None = None
    estado: EstadoPropiedad
    estado_alquiler: EstadoAlquiler


class PropiedadDetalle(PropiedadRead):
    propietarios: list[PropietarioDetalle] = []
