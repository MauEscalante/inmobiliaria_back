from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.database.connection import Base


class Contrato(Base):
	__tablename__ = "contrato"

	contrato_id = Column(Integer, primary_key=True, index=True)
	propiedad = Column(Integer, ForeignKey("propiedad.propiedad_id"), nullable=False, index=True)
	fecha_inicio = Column(Date, nullable=False)
	fecha_fin = Column(Date, nullable=False)
	tipo_ajuste = Column(String(50), nullable=True)
	periodicidad = Column(Integer, nullable=True)
	importe_inicial = Column(Numeric(12, 2), nullable=False)

	propiedad_obj = relationship("Propiedad", back_populates="contratos")
	inquilinos = relationship("ContratoInquilino", back_populates="contrato", cascade="all, delete-orphan")


class ContratoInquilino(Base):
	__tablename__ = "contrato_inquilino"

	contrato_id = Column("contrato", Integer, ForeignKey("contrato.contrato_id"), primary_key=True)
	cliente_num = Column("cliente", Integer, ForeignKey("cliente.cliente_num"), primary_key=True)

	contrato = relationship("Contrato", back_populates="inquilinos")
	cliente = relationship("Cliente", back_populates="contratos")

