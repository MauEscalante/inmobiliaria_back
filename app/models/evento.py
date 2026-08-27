"""Bitácora de altas del sistema, para el panel de actividad reciente.

Ni `contrato` ni `cliente` guardan fecha de creación, así que sin esta tabla solo
se puede saber en qué orden se cargaron las cosas, nunca cuándo. Cada fila queda
escrita en la misma transacción que el alta que la origina.
"""

from enum import StrEnum

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.database.connection import Base


class TipoEvento(StrEnum):
    contrato_creado = "contrato_creado"
    contrato_rescindido = "contrato_rescindido"
    propiedad_creada = "propiedad_creada"
    propietario_creado = "propietario_creado"
    # Todavía no lo emite nadie: la recepción de llaves no existe como
    # funcionalidad. Queda declarado para que agregarla no toque esta tabla.
    llaves_recibidas = "llaves_recibidas"


class Evento(Base):
    __tablename__ = "evento"

    evento_id = Column(Integer, primary_key=True, index=True)
    # varchar y no SQLEnum: sumar un tipo de evento no debe requerir un ALTER TABLE.
    tipo = Column(String(30), nullable=False)
    # Texto ya armado, igual que librodiario.concepto: se escribe al guardar y no
    # cambia después, así que renombrar una propiedad no reescribe la historia.
    descripcion = Column(String(255), nullable=False)
    # A qué recurso apunta, para poder linkearlo más adelante. Sin FK a propósito:
    # el evento tiene que sobrevivir al borrado de la entidad.
    entidad_tipo = Column(String(20), nullable=True)
    entidad_id = Column(String(20), nullable=True)
    creado_en = Column(DateTime, nullable=False, server_default=func.now(), index=True)
