from sqlalchemy import Column, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.database.connection import Base


class Propiedad(Base):
	__tablename__ = "propiedad"

	propiedad_id = Column(Integer, primary_key=True, index=True)
	direccion = Column(String(255), nullable=False)

	propietarios = relationship("PropiedadPropietario", back_populates="propiedad", cascade="all, delete-orphan")
	contratos = relationship("Contrato", back_populates="propiedad", cascade="all, delete-orphan")


class PropiedadPropietario(Base):
	__tablename__ = "propiedad_propietario"

	propiedad_id = Column(Integer, ForeignKey("propiedad.propiedad_id"), primary_key=True)
	cliente_num = Column("cliente", Integer, ForeignKey("cliente.cliente_num"), primary_key=True)
	porcentaje = Column(Numeric(5, 2), nullable=False)
	comision = Column(Numeric(12, 2), nullable=True)

	propiedad = relationship("Propiedad", back_populates="propietarios")
	cliente = relationship("Cliente", back_populates="propiedades")
