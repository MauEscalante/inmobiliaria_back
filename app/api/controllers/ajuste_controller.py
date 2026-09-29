"""Ajuste de los alquileres de un período.

Aplica el aumento sobre `valor_historico` y nada más. El trabajo de recibos
(recibo_controller.actualizar_recibos) hace esto mismo y además reescribe la
planilla y marca todas las propiedades como impagas; acá se quiere solo la parte
de la plata, que es rápida y no tiene efectos colaterales.
"""

from datetime import date

from app.api.errors import raise_conflict, raise_not_found
from app.api.services import ajuste_service
from app.api.services.contrato_services import existe_contrato
from app.api.services.recibo_service import (
    factores_por_contrato,
    get_ipc,
    get_pendientes_de_ajuste,
    get_propiedades_ajustar,
    get_reajustes_pendientes,
    get_tramos_del_contrato,
)
from app.api.services.valor_historico_service import aplicar_ajuste_del_periodo, aplicar_reajustes


def listar_pendientes_de_ajuste(mes: int, anio: int) -> list:
    return get_pendientes_de_ajuste(mes, anio)


def get_historial_de_alquileres(contrato_id: str) -> list:
    if not existe_contrato(contrato_id):
        raise_not_found("Contrato", contrato_id)
    return get_tramos_del_contrato(contrato_id)


def ajustar_alquileres(mes: int, anio: int) -> dict:
    """Aplica al período lo que le toca a cada contrato: ajuste o re-ajuste.

    Son dos cosas distintas que caen en la misma corrida:

      Ajuste    -> al contrato le cierra el período este mes. Se acumula el IPC de
                   los meses del período; si falta el del último (se publica a
                   mediados del siguiente) se repite el anterior y el tramo queda
                   provisorio.
      Re Ajuste -> el mes pasado ajustó con un índice repetido. Ahora se rehace el
                   mismo período desde el mismo importe base, con el índice real, y
                   se abre el tramo definitivo. El provisorio no se toca: ya se cobró.

    Es idempotente por los dos lados: el ajuste saltea al contrato que ya tiene el
    tramo del período, y el re-ajuste deja de encontrar al que ya tiene el suyo.
    """
    if ajuste_service.hay_activo():
        # El trabajo de recibos ajusta los mismos contratos. Si corren a la vez,
        # los dos pasan el chequeo de "¿ya existe el tramo?" y uno revienta contra
        # la PK (contrato, fecha_inicio). Mismo candado que usa solicitar_ajuste().
        raise_conflict(
            "Hay un ajuste de recibos en curso. Esperá a que termine.",
            code="ajuste_en_curso",
        )

    contratos = get_propiedades_ajustar(mes, anio)
    reajustes = get_reajustes_pendientes(mes, anio)

    # Sin nada que hacer no se le pega al servicio externo de IPC al pedo.
    if not contratos and not reajustes:
        return {
            "mes": mes,
            "anio": anio,
            "contratos_pendientes": 0,
            "contratos_ajustados": 0,
            "reajustes_pendientes": 0,
            "contratos_reajustados": 0,
        }

    ipc = get_ipc()
    desde = date(anio, mes, 1)

    _, ajustados = aplicar_ajuste_del_periodo(
        contratos, desde, factores_por_contrato(contratos, ipc, anio, mes)
    )

    # El re-ajuste rehace el período del mes PASADO, así que su factor se pide
    # contra ese mes: son los mismos meses de IPC, ahora completos.
    mes_provisorio = (anio - 1, 12) if mes == 1 else (anio, mes - 1)
    reajustados = aplicar_reajustes(
        reajustes, desde, factores_por_contrato(reajustes, ipc, *mes_provisorio)
    )

    return {
        "mes": mes,
        "anio": anio,
        "contratos_pendientes": len(contratos),
        "contratos_ajustados": ajustados,
        "reajustes_pendientes": len(reajustes),
        "contratos_reajustados": reajustados,
    }
