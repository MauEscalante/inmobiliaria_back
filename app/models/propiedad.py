from sqlalchemy import Column, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship
from enum import Enum
from sqlalchemy import Enum as SQLEnum

from app.database.connection import Base


class EstadoPropiedad (str, Enum):
	Activa="Activa"
	Inactiva="Inactiva"


class EstadoAlquiler (str, Enum):
	Abono="Abono"
	Adeuda="Adeuda"


class Propiedad(Base):
	__tablename__ = "propiedad"

	propiedad_id = Column(Integer, primary_key=True, index=True)
	direccion = Column(String(255), nullable=False)
	ambientes = Column(Integer, nullable=True)
	estado = Column(SQLEnum(EstadoPropiedad), nullable=False, server_default=EstadoPropiedad.Activa.value)
	estado_alquiler = Column(SQLEnum(EstadoAlquiler), nullable=False, server_default=EstadoAlquiler.Adeuda.value)

	propietarios = relationship("PropiedadPropietario", back_populates="propiedad", cascade="all, delete-orphan")
	contratos = relationship("Contrato", back_populates="propiedad_obj", cascade="all, delete-orphan")


class PropiedadPropietario(Base):
	__tablename__ = "propiedad_propietario"

	propiedad_id = Column(Integer, ForeignKey("propiedad.propiedad_id"), primary_key=True)
	cliente_num = Column("cliente", Integer, ForeignKey("cliente.cliente_num"), primary_key=True)
	# `porcentaje` es la parte de la comisión que le corresponde a este propietario;
	# `comision` es la comisión del propietario, igual en todas sus propiedades.
	porcentaje = Column(Numeric(5, 2), nullable=False)
	comision = Column(Numeric(12, 2), nullable=True)

	propiedad = relationship("Propiedad", back_populates="propietarios")
	cliente = relationship("Cliente", back_populates="propiedades")
