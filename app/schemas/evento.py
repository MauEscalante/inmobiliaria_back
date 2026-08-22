"""Schema del recurso evento: la bitácora que alimenta la actividad reciente."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EventoRead(BaseModel):
    """Fila de la bitácora. `descripcion` ya viene lista para mostrar."""

    model_config = ConfigDict(from_attributes=True)

    evento_id: int
    tipo: str = Field(..., description="contrato_creado, propiedad_creada, propietario_creado...")
    descripcion: str
    # A qué recurso apunta el evento. Quedan en null en los eventos que no
    # refieren a una entidad puntual.
    entidad_tipo: str | None = None
    entidad_id: str | None = None
    creado_en: datetime
