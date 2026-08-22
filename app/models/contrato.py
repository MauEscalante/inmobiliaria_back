from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship
from enum import Enum
from sqlalchemy import Enum as SQLEnum
from app.database.connection import Base

class TipoAjuste (str, Enum):
	IPC="IPC"
	ICL="ICL"
 
class EstadoContrato (str, Enum):
	Activo="Activo"
	Inactivo="Inactivo"
	# Cortado antes de fecha_fin. Entra en el varchar(10) de la columna sin ALTER.
	Rescindido="Rescindido"

class TipoGarantia (str, Enum):
	GPremier="GPremier"
	GarantiaPropietaria="Garantia Propietaria"
	Garantes="Garantes"

class PeriodicidadContrato (str, Enum):
	Trimestral="Trimestral"
	Cuatrimestral="Cuatrimestral"
	Semestral="Semestral"


class Contrato(Base):
	__tablename__ = "contrato"

	contrato_id = Column(String(10), primary_key=True, index=True)
	propiedad = Column(Integer, ForeignKey("propiedad.propiedad_id"), nullable=False, index=True)
	fecha_inicio = Column(Date, nullable=False)
	fecha_fin = Column(Date, nullable=False)
	tipo_ajuste = Column(SQLEnum(TipoAjuste), nullable=True)
	periodicidad = Column(SQLEnum(PeriodicidadContrato), nullable=True)
	importe_inicial = Column(Numeric(12, 2), nullable=False)
	deposito = Column(Numeric(12, 2), nullable=True)
	estado = Column(SQLEnum(EstadoContrato), nullable=False)
	# El tipo de garantía ya determina, de forma explícita, si el contrato tiene filas
	# en `garante`: GPremier nunca las tiene; Garantia Propietaria y Garantes sí.
	garantia = Column(SQLEnum(TipoGarantia, values_callable=lambda enum_cls: [m.value for m in enum_cls]), nullable=False, default=TipoGarantia.GPremier)
	direccion_garantia = Column(String(255), nullable=True)
	# Rescisión: último día del mes en que se fue el inquilino y la penalidad
	# calculada. `fecha_fin` conserva el plazo pactado para poder auditar el cálculo.
	fecha_rescision = Column(Date, nullable=True)
	penalidad = Column(Numeric(12, 2), nullable=True)

	propiedad_obj = relationship("Propiedad", back_populates="contratos")
	inquilinos = relationship("ContratoInquilino", back_populates="contrato", cascade="all, delete-orphan")
	garantes = relationship("Garante", back_populates="contrato", cascade="all, delete-orphan")
	valores_historicos = relationship("ValorHistorico", back_populates="contrato_obj", cascade="all, delete-orphan")


class ContratoInquilino(Base):
	__tablename__ = "contrato_inquilino"

	contrato_id = Column("contrato", String(10), ForeignKey("contrato.contrato_id"), primary_key=True)
	cliente_num = Column("cliente", Integer, ForeignKey("cliente.cliente_num"), primary_key=True)

	contrato = relationship("Contrato", back_populates="inquilinos")
	cliente = relationship("Cliente", back_populates="contratos")

