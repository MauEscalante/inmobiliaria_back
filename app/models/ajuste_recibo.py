from enum import StrEnum

from sqlalchemy import Column, DateTime, Integer, SmallInteger, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.sql import func

from app.database.connection import Base


class EstadoAjuste(StrEnum):
    pendiente = "pendiente"
    en_proceso = "en_proceso"
    completado = "completado"
    fallido = "fallido"


# Estados desde los que un trabajo todavia puede avanzar. Mientras haya uno asi,
# no se acepta otro ajuste: la planilla es un archivo compartido y dos ejecuciones
# simultaneas la corromperian.
ESTADOS_ACTIVOS = (EstadoAjuste.pendiente, EstadoAjuste.en_proceso)


class AjusteRecibo(Base):
    """Un pedido de ajuste de recibos y como termino.

    El trabajo tarda mas de un minuto, asi que no se resuelve dentro del request:
    esta fila es lo que el cliente consulta para saber como viene.
    """

    __tablename__ = "ajuste_recibo"

    ajuste_id = Column(Integer, primary_key=True, index=True)
    mes = Column(SmallInteger, nullable=False)
    anio = Column(SmallInteger, nullable=False)
    estado = Column(
        SQLEnum(EstadoAjuste),
        nullable=False,
        server_default=EstadoAjuste.pendiente.value,
        index=True,
    )
    # Se llenan al terminar bien; quedan en NULL si el trabajo falla.
    contratos_ajustados = Column(Integer, nullable=True)
    propiedades_marcadas_adeuda = Column(Integer, nullable=True)
    # Motivo del fallo, recortado para entrar en la columna.
    error = Column(String(500), nullable=True)
    creado_en = Column(DateTime, nullable=False, server_default=func.now())
    finalizado_en = Column(DateTime, nullable=True)
