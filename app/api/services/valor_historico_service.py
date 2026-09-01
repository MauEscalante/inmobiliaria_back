"""Tramos de importe de un contrato.

Igual que evento_service, las funciones que reciben la sesión por parámetro no
commitean: el tramo inicial se escribe dentro de la misma transacción que el alta
del contrato, así nunca queda un contrato sin importe histórico.

Las dos que abren sesión propia —get_importe_vigente_del_mes y
aplicar_ajuste_del_periodo— lo dicen en su docstring: las llaman procesos que no
tienen ninguna transacción en curso.
"""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

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


def cerrar_tramo(db, contrato_id: str, fecha_inicio: date, hasta: date) -> None:
    """Le pone fin al tramo que arranca en `fecha_inicio`, porque empieza otro."""
    db.execute(
        text("""
            UPDATE valor_historico
            SET fecha_fin = :hasta
            WHERE contrato = :contrato_id AND fecha_inicio = :fecha_inicio
        """),
        {"contrato_id": contrato_id, "fecha_inicio": fecha_inicio, "hasta": hasta},
    )


def abrir_tramo(db, contrato_id: str, importe, desde: date, hasta: date) -> None:
    """Tramo nuevo con el importe ya ajustado, vigente hasta el fin del contrato.

    El próximo ajuste lo va a recortar, igual que este recortó al anterior.
    """
    db.execute(
        text("""
            INSERT INTO valor_historico (contrato, importe_inicial, fecha_inicio, fecha_fin)
            VALUES (:contrato_id, :importe_inicial, :fecha_inicio, :fecha_fin)
        """),
        {
            "contrato_id": contrato_id,
            "importe_inicial": importe,
            "fecha_inicio": desde,
            "fecha_fin": hasta,
        },
    )


def _existe_tramo(db, contrato_id: str, desde: date) -> bool:
    fila = db.execute(
        text(
            "SELECT 1 FROM valor_historico"
            " WHERE contrato = :contrato_id AND fecha_inicio = :desde LIMIT 1"
        ),
        {"contrato_id": contrato_id, "desde": desde},
    ).first()
    return fila is not None


def aplicar_ajuste_del_periodo(contratos: list[dict], desde: date, factor: Decimal) -> dict:
    """Abre el tramo del período para cada contrato que ajusta, en una transacción.

    Devuelve {contrato_id: importe vigente} para que el recibo se escriba con el
    mismo número que quedó en la base. Sin esto el importe ajustado vivía solo en la
    planilla y la base no sabía cuánto se cobraba, que es justo lo que necesita el
    cálculo de una rescisión.

    Es idempotente: si el contrato ya tiene un tramo que arranca en `desde`, ese
    período ya se ajustó y se devuelve el importe que hay, sin volver a aplicarlo.
    """
    db = SessionLocal()
    try:
        importes = {}

        for contrato in contratos:
            contrato_id = contrato["contrato_id"]
            # serializar_fila deja las fechas como ISO y los Decimal como float.
            fecha_fin = date.fromisoformat(contrato["fecha_fin"])

            # El contrato ya terminó: abrir un tramo que arranca después de su fin
            # violaría ck_valor_historico_vigencia.
            if fecha_fin < desde:
                continue

            vigente = get_importe_del_mes(db, contrato_id, desde)
            if vigente is None:
                # Sin tramo previo no hay base sobre la cual ajustar. No debería
                # pasar: el alta siembra el inicial.
                continue

            if _existe_tramo(db, contrato_id, desde):
                importes[contrato_id] = vigente["importe_inicial"]
                continue

            nuevo = (vigente["importe_inicial"] * factor).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            cerrar_tramo(db, contrato_id, vigente["fecha_inicio"], desde - timedelta(days=1))
            abrir_tramo(db, contrato_id, nuevo, desde, fecha_fin)
            importes[contrato_id] = nuevo

        db.commit()
        return importes
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
