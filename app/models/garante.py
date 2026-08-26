from sqlalchemy import Column, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.database.connection import Base


class Garante(Base):
	__tablename__ = "garante"

	garante_id = Column(Integer, primary_key=True, index=True)
	contrato_id = Column(
		"contrato", String(10), ForeignKey("contrato.contrato_id"),
		nullable=False, index=True,
	)
	nombre = Column(String(15), nullable=False)
	apellido = Column(String(15), nullable=False)
	telefono = Column(String(15), nullable=False)
	dni = Column(String(9), nullable=True)
	sueldo = Column(Numeric(12, 2), nullable=True)
	email = Column(String(100), nullable=True)

	contrato = relationship("Contrato", back_populates="garantes")
