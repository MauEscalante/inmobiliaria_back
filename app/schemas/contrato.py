"""Schemas del recurso contrato y de sus sub-recursos (inquilinos, garantes)."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.contrato import (
    EstadoContrato,
    PeriodicidadContrato,
    TipoAjuste,
    TipoGarantia,
)
from app.schemas.garante import GaranteCreate, GaranteRead
from app.schemas.validators import EMAIL_PATTERN


class InquilinoInput(BaseModel):
    """Inquilino del alta. Si el DNI ya existe se reusa ese cliente."""

    nombre: str = Field(..., min_length=1, max_length=15)
    apellido: str = Field(..., min_length=1, max_length=15)
    telefono: str = Field(..., min_length=1, max_length=15)
    dni: str = Field(..., min_length=1, max_length=9)
    cuil: str | None = Field(None, max_length=15)
    nacionalidad: str | None = Field(None, max_length=50)
    direccion: str | None = Field(None, max_length=255)
    email: str | None = Field(None, max_length=100, pattern=EMAIL_PATTERN)


class InquilinoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cliente_num: int
    nombre: str
    apellido: str
    dni: str


class PropietarioContratoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cliente_num: int
    nombre: str
    apellido: str
    porcentaje: float


class ContratoCreate(BaseModel):
    # `propiedad` es el nombre real de la columna FK (app/models/contrato.py).
    propiedad: int
    fecha_inicio: date
    fecha_fin: date
    importe_inicial: Decimal = Field(..., gt=0, decimal_places=2)
    deposito: Decimal | None = Field(None, ge=0, decimal_places=2)
    tipo_ajuste: TipoAjuste | None = None
    periodicidad: PeriodicidadContrato | None = None
    estado: EstadoContrato = EstadoContrato.Activo
    garantia: TipoGarantia = TipoGarantia.GPremier
    direccion_garantia: str | None = Field(None, max_length=255)
    inquilinos: list[InquilinoInput] = Field(..., min_length=1)
    garantes: list[GaranteCreate] = []

    @model_validator(mode="after")
    def _fechas_coherentes(self):
        if self.fecha_fin <= self.fecha_inicio:
            raise ValueError("fecha_fin debe ser posterior a fecha_inicio")
        return self

    @model_validator(mode="after")
    def _garantes_segun_garantia(self):
        # El modelo ya documenta la regla: GPremier nunca tiene garantes.
        if self.garantia == TipoGarantia.GPremier and self.garantes:
            raise ValueError("un contrato con garantía GPremier no lleva garantes")
        if self.garantia == TipoGarantia.Garantes and not self.garantes:
            raise ValueError("la garantía 'Garantes' requiere al menos un garante")
        return self


class ContratoRead(BaseModel):
    """Fila de la colección. Reemplaza al objeto ORM que se serializaba crudo."""

    model_config = ConfigDict(from_attributes=True)

    contrato_id: str
    propiedad: int
    fecha_inicio: date
    fecha_fin: date
    importe_inicial: float
    deposito: float | None = None
    tipo_ajuste: TipoAjuste | None = None
    periodicidad: PeriodicidadContrato | None = None
    estado: EstadoContrato
    garantia: TipoGarantia
    direccion_garantia: str | None = None
    fecha_rescision: date | None = None
    fecha_entrega_llaves: date | None = None
    penalidad: float | None = None


class PropiedadContratoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    propiedad_id: int
    direccion: str


class ContratoDetalle(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    contrato_id: str
    propiedad: PropiedadContratoRead
    propietarios: list[PropietarioContratoRead] = []
    inquilinos: list[InquilinoRead] = []
    garantia: TipoGarantia
    direccion_garantia: str | None = None
    garantes: list[GaranteRead] = []
    fecha_inicio: date
    fecha_fin: date
    importe_inicial: float
    deposito: float | None = None
    tipo_ajuste: TipoAjuste | None = None
    periodicidad: PeriodicidadContrato | None = None
    estado: EstadoContrato
    fecha_rescision: date | None = None
    fecha_entrega_llaves: date | None = None
    penalidad: float | None = None


class RescisionCreate(BaseModel):
    """Mes en que se va el inquilino. El día es indistinto: paga el mes completo."""

    anio: int = Field(..., ge=2000, le=2100)
    mes: int = Field(..., ge=1, le=12)


class EntregaLlavesCreate(BaseModel):
    """Cierre de la rescisión: el día en que el inquilino devolvió las llaves.

    `importe_alquiler` solo hace falta cuando el mes de la entrega todavía no tiene
    su tramo en `valor_historico` —el ajuste del mes no se cargó—, porque ahí el
    sistema no tiene de dónde sacar el alquiler sobre el que se calcula la penalidad.
    """

    fecha_entrega: date
    importe_alquiler: Decimal | None = Field(None, gt=0, decimal_places=2)

    @model_validator(mode="after")
    def _entrega_no_futura(self):
        # Las llaves se entregan o no se entregan; no se agendan.
        if self.fecha_entrega > date.today():
            raise ValueError("la fecha de entrega de llaves no puede ser futura")
        return self


class RescisionCalculo(BaseModel):
    """Lo que cuesta rescindir. Sale igual del preview y de la confirmación."""

    contrato_id: str
    direccion: str
    # El plazo pactado, que no se pisa al rescindir: es contra esto que se contaron
    # los meses restantes.
    fecha_fin_original: date
    fecha_salida: date
    meses_restantes: int
    # False cuando el contrato llega a término: no hay penalidad que cobrar.
    anticipada: bool
    importe_vigente: float
    # Inicio del tramo de valor_historico del que salió el importe.
    importe_vigente_desde: date
    # True cuando ese tramo no llega a cubrir el mes de salida: el mes todavía no
    # se liquidó y el importe es el último conocido, así que la penalidad es una
    # estimación. Se resuelve al cerrar por entrega de llaves.
    importe_estimado: bool
    porcentaje_penalidad: float
    penalidad: float
