"""Ajuste de alquileres: lo que la pantalla de Ajustes lista y aplica.

Es la mitad "plata" del ajuste. La otra —reescribir la planilla y marcar las
propiedades como impagas— vive en el trabajo de recibos y tiene sus propios
schemas en app/schemas/recibo.py.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class AjustePendiente(BaseModel):
    """Contrato al que le toca ajuste en el período, con lo que muestra la grilla."""

    model_config = ConfigDict(from_attributes=True)

    contrato_id: str
    propiedad: int
    direccion: str
    # "Ajuste" cuando al contrato le cierra el período este mes; "Re Ajuste" cuando
    # el mes pasado ajustó con un índice de IPC repetido y ahora se rehace con el real.
    tipo: str
    # Los co-inquilinos vienen concatenados: la grilla es una fila por contrato.
    # None cuando el contrato no tiene ninguno cargado.
    inquilino: str | None = None
    fecha_inicio: date
    fecha_fin: date
    periodicidad: str | None = None
    tipo_ajuste: str | None = None
    # El alquiler que rige hoy, del tramo de valor_historico, no el del alta.
    # None si el contrato no tiene ningún tramo: ese no se puede ajustar.
    importe_vigente: float | None = None
    importe_vigente_desde: date | None = None


class AjusteAplicar(BaseModel):
    """Período que se quiere ajustar."""

    mes: int = Field(..., ge=1, le=12)
    anio: int = Field(..., ge=2000, le=2100)


class AjusteAplicado(BaseModel):
    """Resultado de aplicar el ajuste."""

    mes: int
    anio: int
    # Cuántos contratos le cerraba el período este mes.
    contratos_pendientes: int
    # Cuántos se ajustaron ahora. Menos que los pendientes cuando alguno ya tenía
    # el tramo del período: repetir el ajuste no lo vuelve a aplicar.
    contratos_ajustados: int
    # Cuántos venían con un ajuste provisorio del mes pasado.
    reajustes_pendientes: int
    # Cuántos se rehicieron con el índice real. Menos que los pendientes si a alguno
    # todavía le falta el índice: ese espera al mes que viene.
    contratos_reajustados: int


class TramoHistorial(BaseModel):
    """Un tramo de alquiler del contrato. El historial es la lista de todos."""

    model_config = ConfigDict(from_attributes=True)

    fecha_inicio: date
    fecha_fin: date
    importe_inicial: float
    # El tramo se calculó con un índice repetido y el mes siguiente se rehizo.
    provisorio: bool = False
