"""Tramos de importe de un contrato.

Igual que evento_service, las funciones que reciben la sesión por parámetro no
commitean: el tramo inicial se escribe dentro de la misma transacción que el alta
del contrato, así nunca queda un contrato sin importe histórico.

Las dos que abren sesión propia —get_importe_vigente_del_mes y
aplicar_ajuste_del_periodo— lo dicen en su docstring: las llaman procesos que no
tienen ninguna transacción en curso.
"""

from datetime import date, timedelta
from decimal import ROUND_CEILING, Decimal

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
# El alquiler ajustado se lleva siempre al millar de arriba: es el número que se
# le cobra al inquilino, no el exacto que sale de multiplicar por el IPC.
MILLAR = Decimal("1000")


def redondear_alquiler(importe: Decimal) -> Decimal:
    """Lleva el importe al millar de arriba. Si ya cae en un millar, no lo mueve.

    ROUND_CEILING y no ROUND_UP para dejar dicho que es siempre hacia arriba; sobre
    importes positivos dan lo mismo.
    """
    return (importe / MILLAR).to_integral_value(rounding=ROUND_CEILING) * MILLAR


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


def confirmar_tramo(db, contrato_id: str, fecha_inicio: date) -> None:
    """Le saca lo provisorio al tramo: el índice que faltaba salió y no lo movió."""
    db.execute(
        text("""
            UPDATE valor_historico
            SET provisorio = 0
            WHERE contrato = :contrato_id AND fecha_inicio = :fecha_inicio
        """),
        {"contrato_id": contrato_id, "fecha_inicio": fecha_inicio},
    )


def abrir_tramo(
    db, contrato_id: str, importe, desde: date, hasta: date, provisorio: bool = False
) -> None:
    """Tramo nuevo con el importe ya ajustado, vigente hasta el fin del contrato.

    El próximo ajuste lo va a recortar, igual que este recortó al anterior.

    `provisorio` marca que el factor se armó repitiendo un índice de IPC que todavía
    no estaba publicado. Ese tramo se cobra igual, y al mes siguiente el re-ajuste
    abre el definitivo con el índice real.
    """
    db.execute(
        text("""
            INSERT INTO valor_historico
                   (contrato, importe_inicial, provisorio, fecha_inicio, fecha_fin)
            VALUES (:contrato_id, :importe_inicial, :provisorio, :fecha_inicio, :fecha_fin)
        """),
        {
            "contrato_id": contrato_id,
            "importe_inicial": importe,
            "provisorio": 1 if provisorio else 0,
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


def aplicar_ajuste_del_periodo(
    contratos: list[dict], desde: date, factores: dict
) -> tuple[dict, int]:
    """Abre el tramo del período para cada contrato que ajusta, en una transacción.

    `factores` trae {"factor", "provisorio"} por contrato_id: el multiplicador no es
    uno solo para todos porque depende de la periodicidad (ver
    recibo_service.factores_por_contrato). El contrato que no esté ahí se saltea.

    Devuelve ({contrato_id: importe vigente}, cuántos se ajustaron de verdad). El
    diccionario sirve para escribir el recibo con el mismo número que quedó en la
    base; sin esto el importe ajustado vivía solo en la planilla y la base no sabía
    cuánto se cobraba, que es justo lo que necesita el cálculo de una rescisión.

    Es idempotente: si el contrato ya tiene un tramo que arranca en `desde`, ese
    período ya se ajustó y se devuelve el importe que hay sin volver a aplicarlo,
    y ese contrato no cuenta como ajustado.
    """
    db = SessionLocal()
    try:
        importes = {}
        ajustados = 0

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

            calculo = factores.get(contrato_id)
            if calculo is None:
                continue

            nuevo = redondear_alquiler(vigente["importe_inicial"] * calculo["factor"])

            cerrar_tramo(db, contrato_id, vigente["fecha_inicio"], desde - timedelta(days=1))
            abrir_tramo(db, contrato_id, nuevo, desde, fecha_fin, calculo["provisorio"])
            importes[contrato_id] = nuevo
            ajustados += 1

        db.commit()
        return importes, ajustados
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def aplicar_reajustes(reajustes: list[dict], desde: date, factores: dict) -> int:
    """Reemplaza el ajuste provisorio del mes pasado por el definitivo.

    No pisa el tramo provisorio: ese importe ya se cobró. Lo cierra a fin del mes
    pasado y abre uno nuevo desde `desde` con el valor recalculado.

    El importe sale de `base` —lo que el inquilino pagaba antes del ajuste
    provisorio— y no del importe provisorio, que ya trae la aproximación adentro.

    Devuelve cuántos se re-ajustaron. El que siga sin tener publicado el índice que
    le falta se saltea y espera al mes que viene.
    """
    db = SessionLocal()
    try:
        reajustados = 0

        for contrato in reajustes:
            contrato_id = contrato["contrato_id"]
            calculo = factores.get(contrato_id)

            # Sigue faltando el índice: recalcular daría el mismo número.
            if calculo is None or calculo["provisorio"]:
                continue

            fecha_fin = date.fromisoformat(contrato["fecha_fin"])
            if fecha_fin < desde or _existe_tramo(db, contrato_id, desde):
                continue

            base = Decimal(str(contrato["base"]))
            nuevo = redondear_alquiler(base * calculo["factor"])
            provisorio_desde = date.fromisoformat(contrato["importe_vigente_desde"])

            # Con el redondeo al millar el definitivo puede caer en el mismo importe
            # que el provisorio. Abrir un tramo igual al anterior solo ensucia el
            # historial: alcanza con dar por confirmado el que ya está.
            if nuevo == Decimal(str(contrato["importe_vigente"])):
                confirmar_tramo(db, contrato_id, provisorio_desde)
            else:
                cerrar_tramo(db, contrato_id, provisorio_desde, desde - timedelta(days=1))
                abrir_tramo(db, contrato_id, nuevo, desde, fecha_fin)

            reajustados += 1

        db.commit()
        return reajustados
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
