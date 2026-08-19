from sqlalchemy import Column, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship
from enum import Enum

from app.database.connection import Base


class ClienteTipo(str, Enum):
	Inquilino = "Inquilino"
	Propietario = "Propietario"


class Cliente(Base):
	__tablename__ = "cliente"

	cliente_num = Column(Integer, primary_key=True, index=True)
	nombre = Column(String(15), nullable=False)
	apellido = Column(String(15), nullable=False)
	dni = Column(String(9), nullable=False, unique=True, index=True)
	telefono = Column(String(15), nullable=False)
	email = Column(String(100), nullable=True, unique=True, index=True)
	direccion = Column(String(255), nullable=True)
	cuil = Column(String(15), nullable=True)
	nacionalidad = Column(String(50), nullable=True)
	tipo = Column(SQLEnum(ClienteTipo), nullable=True)

	propiedades = relationship("PropiedadPropietario", back_populates="cliente", cascade="all, delete-orphan")
	contratos = relationship("ContratoInquilino", back_populates="cliente", cascade="all, delete-orphan")
