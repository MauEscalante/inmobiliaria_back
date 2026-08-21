"""Schemas del recurso recibo.

El ajuste de recibos es un trabajo en segundo plano: el POST lo encola y devuelve
el trabajo, y el cliente consulta su estado hasta que termina.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.ajuste_recibo import EstadoAjuste


class ContratoAAjustar(BaseModel):
    """Contrato al que le toca ajuste en el período pedido."""

    model_config = ConfigDict(from_attributes=True)

    contrato_id: str
    propiedad: int
    fecha_inicio: date
    fecha_fin: date
    importe_inicial: float
    periodicidad: str | None = None
    tipo_ajuste: str | None = None


class AjusteCreate(BaseModel):
    mes: int = Field(..., ge=1, le=12)
    anio: int = Field(..., ge=1900, le=2100)


class AjusteRead(BaseModel):
    """Un trabajo de ajuste y en qué estado está.

    El ajuste tarda más de un minuto, así que el POST no devuelve el resultado
    sino el trabajo recién encolado; los contadores se llenan al completarse.
    """

    model_config = ConfigDict(from_attributes=True)

    ajuste_id: int
    mes: int
    anio: int
    estado: EstadoAjuste
    contratos_ajustados: int | None = None
    propiedades_marcadas_adeuda: int | None = None
    error: str | None = Field(None, description="Motivo del fallo, si el estado es 'fallido'")
    creado_en: datetime
    finalizado_en: datetime | None = None


class PlanillaResumen(BaseModel):
    """Estado de la planilla de recibos que se guarda en el servidor."""

    cantidad_hojas: int
    hojas: list[str]
