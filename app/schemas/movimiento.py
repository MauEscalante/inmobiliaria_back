"""Schemas del recurso movimiento (las filas del libro diario) y de los reportes de caja."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.libro_diario import CuentaTransferencia, TipoMovimiento

# Ingresos y depósitos son plata de una propiedad, por eso hay que indicar cuál.
TIPOS_CON_PROPIEDAD = (TipoMovimiento.INGRESO, TipoMovimiento.DEPOSITO)


class MovimientoCreate(BaseModel):
    fecha: date
    tipo: TipoMovimiento
    monto: Decimal = Field(..., gt=0, decimal_places=2)
    propiedad_id: int | None = None
    piso: str | None = Field(None, max_length=10)
    depto: str | None = Field(None, max_length=10)
    concepto: str | None = Field(
        None, max_length=150,
        description="Solo para egresos y retiros; en ingresos y depósitos lo arma el backend",
    )
    cuenta: CuentaTransferencia | None = None

    @model_validator(mode="after")
    def _coherencia_por_tipo(self):
        if self.tipo in TIPOS_CON_PROPIEDAD:
            if not self.propiedad_id:
                raise ValueError(f"un movimiento de tipo {self.tipo.value} necesita propiedad_id")
        else:
            # Los egresos y retiros no tienen propiedad: el concepto lo escribe el usuario.
            if not (self.concepto or "").strip():
                raise ValueError(f"un movimiento de tipo {self.tipo.value} necesita concepto")

        # En un depósito la cuenta dice a dónde se transfirió la plata.
        if self.tipo == TipoMovimiento.DEPOSITO and not self.cuenta:
            raise ValueError("un depósito necesita indicar la cuenta")
        return self


class MovimientoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    movimiento_id: int
    fecha: date
    concepto: str
    propiedad_id: int | None = None
    direccion: str | None = Field(
        None, description="Dirección actual de la propiedad; puede diferir del concepto"
    )
    piso: str | None = None
    depto: str | None = None
    monto: float
    tipo: TipoMovimiento
    cuenta: CuentaTransferencia | None = None


class ResumenCaja(BaseModel):
    """Estado de la caja del mes. Solo el efectivo entra en total_caja."""

    total_efectivo: float
    total_transferencias: float
    total_egresos: float
    total_retiros: float
    total_caja: float = Field(..., description="efectivo - egresos - retiros")


class IngresoMensual(BaseModel):
    """Fila del historial de ingresos por mes."""

    id: str = Field(..., description='Período en formato "YYYY-MM"')
    mes: str = Field(..., description="Nombre del mes en español")
    anio: str
    total: float
