"""Tramos de importe de un contrato a lo largo del tiempo.

Cada ajuste abre un tramo nuevo, así que el importe que regía en una fecha dada
se lee de acá y no de `contrato.importe_inicial`, que es el valor del alta y
nunca cambia. La rescisión anticipada calcula la penalidad sobre el importe del
mes en que el inquilino se va, no sobre el original.
"""

from sqlalchemy import Column, Date, ForeignKey, Numeric, String
from sqlalchemy.orm import relationship

from app.database.connection import Base


class ValorHistorico(Base):
	__tablename__ = "valor_historico"

	# La columna se llama `contrato` en la tabla, igual que en contrato_inquilino;
	# el atributo va con otro nombre para no chocar con la relación.
	contrato_id = Column(
		"contrato", String(10), ForeignKey("contrato.contrato_id"), primary_key=True
	)
	# La PK es compuesta (contrato, fecha_inicio): un contrato tiene un tramo por ajuste.
	fecha_inicio = Column(Date, primary_key=True)
	fecha_fin = Column(Date, nullable=False)
	# Mismo nombre que en la tabla contrato aunque acá no sea "inicial" de nada:
	# es el importe vigente durante el tramo.
	importe_inicial = Column(Numeric(12, 2), nullable=False)

	contrato_obj = relationship("Contrato", back_populates="valores_historicos")
