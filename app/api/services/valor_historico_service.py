"""Tramos de importe de un contrato.

Igual que evento_service, estas funciones reciben la sesión por parámetro y no
commitean: el tramo inicial se escribe dentro de la misma transacción que el alta
del contrato, así nunca queda un contrato sin importe histórico.
"""

from datetime import date

from sqlalchemy import text

from app.database.connection import SessionLocal

# Las consultas van en SQL crudo, pero importar el modelo acá lo registra en el
# mapper: Contrato lo referencia por nombre y falla si nadie lo cargó todavía.
from app.models.valor_historico import ValorHistorico  # noqa: F401

# Último tramo que arrancó a más tardar al cierre del mes buscado.
#
# Con un solo ORDER BY se resuelven los tres casos: el tramo que cubre el mes, el
# que abre a mitad de mes (gana el más nuevo, que es con el que el inquilino se
# va) y el mes todavía no liquidado, que cae en el último tramo conocido. Los
# tramos se escriben mes a mes al liquidar, así que el mes que viene nunca tiene
# el suyo propio y sin este arrastre no se podría rescindir por adelantado.
IMPORTE_DEL_MES_SELECT = """
    SELECT importe_inicial, fecha_inicio
    FROM valor_historico
    WHERE contrato = :contrato_id
      AND fecha_inicio <= :fin_mes
    ORDER BY fecha_inicio DESC
    LIMIT 1
"""


def get_importe_del_mes(db, contrato_id: str, fin_mes: date):
    """Importe que rige en ese mes, con la fecha del tramo del que salió.

    Devuelve None si el contrato no tiene ningún tramo anterior al mes pedido.
    """
    return db.execute(
        text(IMPORTE_DEL_MES_SELECT),
        {"contrato_id": contrato_id, "fin_mes": fin_mes},
    ).mappings().first()


def sembrar_tramo_inicial(db, contrato) -> None:
    """Primer tramo de un contrato recién creado: el importe del alta por todo el plazo.

    Los ajustes posteriores van a recortar este tramo y abrir los siguientes; hasta
    entonces el importe vigente en cualquier mes del contrato es el inicial.
    """
    db.execute(
        text("""
            INSERT INTO valor_historico (contrato, importe_inicial, fecha_inicio, fecha_fin)
            VALUES (:contrato_id, :importe_inicial, :fecha_inicio, :fecha_fin)
        """),
        {
            "contrato_id": contrato.contrato_id,
            "importe_inicial": contrato.importe_inicial,
            "fecha_inicio": contrato.fecha_inicio,
            "fecha_fin": contrato.fecha_fin,
        },
    )


def get_importe_vigente_del_mes(contrato_id: str, fin_mes: date):
    """Igual que get_importe_del_mes, pero con sesión propia.

    La usa el controller de rescisión, que consulta fuera de cualquier transacción
    en curso.
    """
    db = SessionLocal()
    try:
        return get_importe_del_mes(db, contrato_id, fin_mes)
    finally:
        db.close()
