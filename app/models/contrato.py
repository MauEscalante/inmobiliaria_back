from enum import StrEnum

from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.database.connection import Base


class TipoAjuste(StrEnum):
	IPC="IPC"
	ICL="ICL"
 
class EstadoContrato(StrEnum):
	Activo="Activo"
	Inactivo="Inactivo"
	# Cortado antes de fecha_fin. Entra en el varchar(10) de la columna sin ALTER.
	Rescindido="Rescindido"

class TipoGarantia(StrEnum):
	GPremier="GPremier"
	GarantiaPropietaria="Garantia Propietaria"
	Garantes="Garantes"

class PeriodicidadContrato(StrEnum):
	Trimestral="Trimestral"
	Cuatrimestral="Cuatrimestral"
	Semestral="Semestral"


# Cada cuántos meses le toca ajuste a un contrato según su periodicidad.
#
# La query de recibo_service.CONTRATOS_A_AJUSTAR_SELECT hace la misma traducción
# con un CASE, porque decide en SQL; si acá se agrega una periodicidad, hay que
# tocar las dos.
MESES_POR_PERIODICIDAD = {
	PeriodicidadContrato.Trimestral.value: 3,
	PeriodicidadContrato.Cuatrimestral.value: 4,
	PeriodicidadContrato.Semestral.value: 6,
}


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
	garantia = Column(
		SQLEnum(TipoGarantia, values_callable=lambda enum_cls: [m.value for m in enum_cls]),
		nullable=False,
		default=TipoGarantia.GPremier,
	)
	direccion_garantia = Column(String(255), nullable=True)
	# Rescisión en dos tiempos. `fecha_rescision` es el cierre del mes que el
	# inquilino avisó que se va: se carga con el aviso y el contrato sigue Activo,
	# porque ese mes lo paga y se ajusta como cualquier otro.
	fecha_rescision = Column(Date, nullable=True)
	# El día real en que entregó las llaves. Recién ahí se conoce el alquiler con
	# el que se calcula la penalidad, así que las dos se llenan juntas.
	#
	# La columna se llama `fecha_salida` en la tabla; el atributo va con el nombre
	# que expone la API, igual que en ValorHistorico.contrato_id. Además deja el
	# nombre `fecha_salida` libre para lo que significa en RescisionCalculo, que es
	# otra cosa: el último día del mes elegido.
	fecha_entrega_llaves = Column("fecha_salida", Date, nullable=True)
	# Definitiva, no estimada: se escribe junto con fecha_entrega_llaves.
	# `fecha_fin` conserva el plazo pactado para poder auditar el cálculo.
	penalidad = Column(Numeric(12, 2), nullable=True)

	propiedad_obj = relationship("Propiedad", back_populates="contratos")
	inquilinos = relationship(
		"ContratoInquilino", back_populates="contrato", cascade="all, delete-orphan"
	)
	garantes = relationship("Garante", back_populates="contrato", cascade="all, delete-orphan")
	valores_historicos = relationship(
		"ValorHistorico", back_populates="contrato_obj", cascade="all, delete-orphan"
	)


class ContratoInquilino(Base):
	__tablename__ = "contrato_inquilino"

	contrato_id = Column(
		"contrato", String(10), ForeignKey("contrato.contrato_id"), primary_key=True
	)
	cliente_num = Column("cliente", Integer, ForeignKey("cliente.cliente_num"), primary_key=True)

	contrato = relationship("Contrato", back_populates="inquilinos")
	cliente = relationship("Cliente", back_populates="contratos")

