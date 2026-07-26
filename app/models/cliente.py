from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.database.connection import Base


class Cliente(Base):
	__tablename__ = "cliente"

	cliente_num = Column(Integer, primary_key=True, index=True)
	nombre = Column(String(15), nullable=False)
	apellido = Column(String(15), nullable=False)
	dni = Column(String(9), nullable=False, unique=True, index=True)
	telefono = Column(String(15), nullable=True)

	propiedades = relationship("PropiedadPropietario", back_populates="cliente", cascade="all, delete-orphan")
	contratos = relationship("ContratoInquilino", back_populates="cliente", cascade="all, delete-orphan")
