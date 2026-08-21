from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, String
from enum import Enum
from sqlalchemy import Enum as SQLEnum

from app.database.connection import Base


class TipoMovimiento (str, Enum):
	INGRESO="INGRESO"
	DEPOSITO="DEPOSITO"
	EGRESO="EGRESO"
	RETIRO="RETIRO"


class CuentaTransferencia (str, Enum):
	Kike="Kike"
	Dai="Dai"


class LibroDiario(Base):
	# La tabla se creó en camelCase, hay que declararla tal cual.
	__tablename__ = "libroDiario"

	movimiento_id = Column(Integer, primary_key=True, index=True)
	fecha = Column(Date, nullable=False)
	# Solo los ingresos y depósitos apuntan a una propiedad; los egresos y retiros no.
	propiedad_id = Column(Integer, ForeignKey("propiedad.propiedad_id"), nullable=True)
	# Piso y depto son del movimiento, no de la propiedad: aclaran a qué unidad
	# corresponde el pago cuando la dirección sola no alcanza.
	piso = Column(String(10), nullable=True)
	depto = Column(String(10), nullable=True)
	# Se guarda desnormalizado ("Cotagaita 786 3° B") para que la fila siga siendo
	# legible aunque la propiedad cambie de dirección más adelante.
	concepto = Column(String(150), nullable=False)
	monto = Column(Numeric(12, 2), nullable=False)
	tipo = Column(SQLEnum(TipoMovimiento), nullable=False)
	# A qué cuenta se transfirió. Obligatoria en los depósitos, opcional en el resto.
	cuenta = Column(SQLEnum(CuentaTransferencia), nullable=True)
