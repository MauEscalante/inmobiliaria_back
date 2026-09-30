from datetime import date
from decimal import Decimal

import requests
from openpyxl import load_workbook
from openpyxl.workbook.workbook import Workbook
from sqlalchemy import text

from app.config import settings
from app.models.contrato import MESES_POR_PERIODICIDAD
from app.database.connection import SessionLocal
from app.utils.helpers import serializar_fila

# Meses de IPC que se traen. Alcanza para el período más largo (Semestral, 6)
# con margen para que el chequeo de abajo pueda avisar si el servicio trae menos.
MESES_IPC = 12

# Los dos tipos de fila de la pantalla de Ajustes.
TIPO_AJUSTE = "Ajuste"
TIPO_REAJUSTE = "Re Ajuste"

MESES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}

# A qué contrato le toca ajuste en el período. Vive suelta porque la usan las dos
# consultas de abajo: la magra que alimenta el proceso y la del listado de pantalla.
# Que se separen sería mostrar una lista y ajustar otra.
#
# El CASE traduce la periodicidad a meses acá porque la decisión se toma en SQL;
# la versión Python de ese mapa es contrato.MESES_POR_PERIODICIDAD, que usa el
# cálculo de rescisión. Si se agrega una periodicidad hay que tocar las dos.
#
# PERIOD_DIFF y no TIMESTAMPDIFF(MONTH, ...): el aumento cae en el mes de inicio
# más la periodicidad, se haya firmado el 1 o el 30. TIMESTAMPDIFF cuenta meses
# COMPLETOS mirando el día, así que del 22/04 al 01/08 le daba 3 y no 4, y el
# ajuste se corría un mes entero. Como casi ningún contrato arranca un día 1, eso
# afectaba a todos. PERIOD_DIFF compara períodos AAAAMM y el día no entra.
#
# Ojo con "simplificarlo" a (YEAR(a)-YEAR(b))*12 + (MONTH(a)-MONTH(b)): MONTH()
# devuelve UNSIGNED y la resta desborda con "BIGINT UNSIGNED value is out of range"
# cuando el mes de inicio es mayor que el de liquidación.
#
# Solo IPC: los contratos de ICL no los ajusta nadie todavía.
CONDICION_AJUSTE = """
    c.tipo_ajuste = 'IPC'
      AND c.estado = 'Activo'
      AND PERIOD_DIFF(EXTRACT(YEAR_MONTH FROM :fecha_liquidacion),
                      EXTRACT(YEAR_MONTH FROM c.fecha_inicio)) > 0
      AND MOD(
              PERIOD_DIFF(EXTRACT(YEAR_MONTH FROM :fecha_liquidacion),
                          EXTRACT(YEAR_MONTH FROM c.fecha_inicio)),
              CASE c.periodicidad
                  WHEN 'Trimestral' THEN 3
                  WHEN 'Cuatrimestral' THEN 4
                  WHEN 'Semestral' THEN 6
              END
          ) = 0
"""

# Solo las columnas que el recurso expone, en vez del SELECT * que devolvía la
# tabla entera de contratos sin contrato de datos.
CONTRATOS_A_AJUSTAR_SELECT = f"""
    SELECT c.contrato_id, c.propiedad, c.fecha_inicio, c.fecha_fin,
           c.importe_inicial, c.periodicidad, c.tipo_ajuste
    FROM contrato c
    WHERE {CONDICION_AJUSTE}
    ORDER BY c.contrato_id
"""

# Lo mismo, pero con lo que la pantalla necesita mostrar.
#
# El importe sale del tramo vigente de valor_historico y no de c.importe_inicial,
# que es el del alta y quedó viejo apenas hubo un ajuste. El subquery toma el
# último tramo que arrancó a más tardar en el período, igual que
# valor_historico_service.IMPORTE_DEL_MES_SELECT.
#
# Los inquilinos se concatenan porque un contrato puede tener varios co-inquilinos
# y la grilla muestra una fila por contrato, no por persona.
PENDIENTES_DE_AJUSTE_SELECT = f"""
    SELECT c.contrato_id,
           c.propiedad,
           p.direccion,
           c.fecha_inicio,
           c.fecha_fin,
           c.periodicidad,
           c.tipo_ajuste,
           v.importe_inicial AS importe_vigente,
           v.fecha_inicio    AS importe_vigente_desde,
           (SELECT GROUP_CONCAT(CONCAT(cl.nombre, ' ', cl.apellido) SEPARATOR ', ')
              FROM contrato_inquilino ci
              JOIN cliente cl ON cl.cliente_num = ci.cliente
             WHERE ci.contrato = c.contrato_id) AS inquilino
      FROM contrato c
      JOIN propiedad p ON p.propiedad_id = c.propiedad
      LEFT JOIN valor_historico v
             ON v.contrato = c.contrato_id
            AND v.fecha_inicio = (SELECT MAX(v2.fecha_inicio)
                                    FROM valor_historico v2
                                   WHERE v2.contrato = c.contrato_id
                                     AND v2.fecha_inicio <= :fecha_liquidacion)
     WHERE {CONDICION_AJUSTE}
     ORDER BY p.direccion
"""


def get_propiedades_ajustar(mes_liquidacion: int, anio_liquidacion: int) -> list:
    """Contratos a los que les toca ajuste por IPC en el período pedido."""
    db = SessionLocal()
    try:
        fecha_liquidacion = date(anio_liquidacion, mes_liquidacion, 1)
        filas = db.execute(
            text(CONTRATOS_A_AJUSTAR_SELECT),
            {"fecha_liquidacion": fecha_liquidacion},
        ).mappings().all()
        return [serializar_fila(fila) for fila in filas]
    finally:
        db.close()


def get_pendientes_de_ajuste(mes_liquidacion: int, anio_liquidacion: int) -> list:
    """Todo lo que le toca al período, con lo que muestra la pantalla.

    Son dos cosas distintas y por eso va la columna `tipo`:

      Ajuste    -> al contrato le cierra el período este mes.
      Re Ajuste -> ajustó el mes pasado con un índice repetido y ahora se rehace
                   con el índice real.

    Un contrato no puede ser las dos a la vez: entre un ajuste y el siguiente pasan
    como mínimo tres meses.
    """
    db = SessionLocal()
    try:
        fecha_liquidacion = date(anio_liquidacion, mes_liquidacion, 1)
        filas = db.execute(
            text(PENDIENTES_DE_AJUSTE_SELECT),
            {"fecha_liquidacion": fecha_liquidacion},
        ).mappings().all()
        ajustes = [{**serializar_fila(fila), "tipo": TIPO_AJUSTE} for fila in filas]
    finally:
        db.close()

    reajustes = [
        {**fila, "tipo": TIPO_REAJUSTE}
        for fila in get_reajustes_pendientes(mes_liquidacion, anio_liquidacion)
    ]

    return ajustes + reajustes


# Contratos cuyo último tramo quedó provisorio el mes pasado y toca re-ajustar.
#
# `NOT EXISTS` sobre un tramo posterior es lo que lo hace idempotente: en cuanto el
# re-ajuste abre el tramo del mes, el contrato deja de aparecer acá.
#
# `base` es lo que pagaba ANTES del ajuste provisorio: el re-ajuste recalcula el
# mismo período desde ahí, no desde el importe aproximado que se cobró.
REAJUSTES_PENDIENTES_SELECT = """
    SELECT c.contrato_id,
           c.propiedad,
           p.direccion,
           c.fecha_inicio,
           c.fecha_fin,
           c.periodicidad,
           c.tipo_ajuste,
           v.importe_inicial AS importe_vigente,
           v.fecha_inicio    AS importe_vigente_desde,
           prev.importe_inicial AS base,
           (SELECT GROUP_CONCAT(CONCAT(cl.nombre, ' ', cl.apellido) SEPARATOR ', ')
              FROM contrato_inquilino ci
              JOIN cliente cl ON cl.cliente_num = ci.cliente
             WHERE ci.contrato = c.contrato_id) AS inquilino
      FROM contrato c
      JOIN propiedad p ON p.propiedad_id = c.propiedad
      JOIN valor_historico v
        ON v.contrato = c.contrato_id
       AND v.fecha_inicio = :mes_provisorio
       AND v.provisorio = 1
      JOIN valor_historico prev
        ON prev.contrato = c.contrato_id
       AND prev.fecha_inicio = (SELECT MAX(v2.fecha_inicio)
                                  FROM valor_historico v2
                                 WHERE v2.contrato = c.contrato_id
                                   AND v2.fecha_inicio < v.fecha_inicio)
     WHERE c.estado = 'Activo'
       AND NOT EXISTS (SELECT 1 FROM valor_historico v3
                        WHERE v3.contrato = c.contrato_id
                          AND v3.fecha_inicio > v.fecha_inicio)
     ORDER BY p.direccion
"""


def _primero_del_mes_anterior(anio: int, mes: int) -> date:
    return date(anio - 1, 12, 1) if mes == 1 else date(anio, mes - 1, 1)


def get_reajustes_pendientes(mes_liquidacion: int, anio_liquidacion: int) -> list:
    """Contratos que ajustaron el mes pasado con un índice repetido.

    Les toca el re-ajuste: recalcular el mismo período ahora que salió el índice
    que faltaba.
    """
    db = SessionLocal()
    try:
        filas = db.execute(
            text(REAJUSTES_PENDIENTES_SELECT),
            {"mes_provisorio": _primero_del_mes_anterior(anio_liquidacion, mes_liquidacion)},
        ).mappings().all()
        return [serializar_fila(fila) for fila in filas]
    finally:
        db.close()


def get_tramos_del_contrato(contrato_id: str) -> list:
    """Historial de alquileres del contrato: un tramo por ajuste, del más viejo al más nuevo."""
    db = SessionLocal()
    try:
        filas = db.execute(
            text("""
                SELECT fecha_inicio, fecha_fin, importe_inicial, provisorio
                FROM valor_historico
                WHERE contrato = :contrato_id
                ORDER BY fecha_inicio
            """),
            {"contrato_id": contrato_id},
        ).mappings().all()
        return [serializar_fila(fila) for fila in filas]
    finally:
        db.close()


def cargar_planilla() -> Workbook:
    """Planilla completa, en modo lectura/escritura. Es cara: ~40s con 120 hojas.

    Usar solo cuando haya que modificar y guardar; para leer metadatos está
    nombres_de_hojas().
    """
    return load_workbook(settings.RECIBOS_TEMPLATE)


def nombres_de_hojas() -> list[str]:
    """Nombres de las hojas de la planilla.

    Se abre en read_only porque el workbook completo parsea todas las celdas y
    tarda ~40 segundos; en modo lectura son décimas de segundo.
    """
    wb = load_workbook(settings.RECIBOS_TEMPLATE, read_only=True)
    try:
        return list(wb.sheetnames)
    finally:
        wb.close()


def actualizar_fechas(
    recibo: str, mes_liquidacion: int, anio_liquidacion: int, wb: Workbook
) -> None:
    ws = wb[recibo]
    # cambia la fecha del recibo y el mes
    ws["I13"].value = mes_liquidacion
    ws["C22"].value = MESES[mes_liquidacion]
    ws["J13"].value = anio_liquidacion


def _indice_mes(anio: int, mes: int) -> int:
    """Mes como número corrido, para recorrer un período sin pelear con el calendario."""
    return anio * 12 + (mes - 1)


def _mes_de_indice(indice: int) -> tuple[int, int]:
    return (indice // 12, indice % 12 + 1)


def factor_del_periodo(
    valores_ipc: list, anio: int, mes: int, meses: int
) -> tuple[Decimal, bool]:
    """Factor de los `meses` meses anteriores a `mes`/`anio`, y si quedó provisorio.

    El período que se le liquida a un contrato son los meses previos al del ajuste:
    un cuatrimestral que arrancó en mayo ajusta en septiembre con mayo, junio, julio
    y agosto.

    Pero el IPC de un mes se publica a mediados del siguiente, así que al ajustar en
    septiembre el de agosto todavía no está. Ese hueco se tapa repitiendo el último
    índice publicado —julio, en el ejemplo— y el tramo sale marcado como provisorio:
    al mes siguiente se re-ajusta el mismo período con el agosto real.

    Los valores que publica el servicio son porcentajes mensuales (2.6 = 2,6%), así
    que cada uno entra como 1 + valor/100. Antes se multiplicaba el alquiler por el
    porcentaje crudo: cuatro meses daban un factor de 21,79 en vez de 1,09.
    """
    publicados = {(v["anio"], v["mes"]): Decimal(str(v["valor"])) for v in valores_ipc}
    # La serie viene del mes más viejo al más nuevo.
    ultimo = Decimal(str(valores_ipc[-1]["valor"])) if valores_ipc else Decimal("0")

    hasta = _indice_mes(anio, mes)
    factor = Decimal("1")
    provisorio = False

    for indice in range(hasta - meses, hasta):
        valor = publicados.get(_mes_de_indice(indice))
        if valor is None:
            valor = ultimo
            provisorio = True
        factor *= Decimal("1") + valor / Decimal("100")

    return factor, provisorio


def factores_por_contrato(contratos: list, valores_ipc: list, anio: int, mes: int) -> dict:
    """Factor de ajuste de cada contrato para el período que se liquida.

    Un contrato Trimestral acumula 3 meses de IPC, uno Cuatrimestral 4 y uno
    Semestral 6. Antes se aplicaba el mismo factor de 4 meses a todos, de más a los
    trimestrales y de menos a los semestrales.

    Devuelve {contrato_id: {"factor": Decimal, "provisorio": bool}}.
    """
    factores = {}
    for contrato in contratos:
        meses = MESES_POR_PERIODICIDAD.get(contrato.get("periodicidad"))
        # Sin periodicidad no hay período que acumular. No debería pasar: la
        # condición de ajuste hace MOD contra ella, y con NULL nunca da 0.
        if not meses:
            continue

        factor, provisorio = factor_del_periodo(valores_ipc, anio, mes, meses)
        factores[contrato["contrato_id"]] = {"factor": factor, "provisorio": provisorio}
    return factores


def actualizar_importe(recibo: str, wb: Workbook, importe) -> None:
    """Escribe en el recibo el alquiler que quedó guardado en valor_historico.

    Antes se multiplicaba la celda por sí misma, y como el recibo ya trae una
    aproximación hecha el valor se iba separando del de la base ajuste tras ajuste.
    La base manda: es de donde sale el importe del próximo re-ajuste y el de la
    penalidad por rescisión.
    """
    ws = wb[recibo]
    ws["E22"].value = float(importe)


def get_ipc() -> list:
    """Serie de IPC mensual, del mes más viejo al más nuevo.

    Devuelve los últimos MESES_IPC meses y no los 4 de antes: un contrato semestral
    necesita 6 para acumular su período. Quien la usa se queda con la cola que le
    corresponde (ver factores_por_contrato).

    La llamada lleva timeout y verificación de status: sin eso, una caída del
    servicio externo dejaba el request colgado.
    """
    response = requests.get(settings.IPC_API_URL, timeout=settings.IPC_TIMEOUT)
    response.raise_for_status()
    data = response.json().get("data", [])
    return data[-MESES_IPC:]
