from fastapi import APIRouter

from app.api.controllers.libro_diario_controller import (
    get_libro_diario,
    get_retiros_caja,
    get_estado_caja,
    get_historial,
    create_new_movimiento,
    eliminar_movimiento,
)

router = APIRouter(prefix="/libroDiario", tags=["libroDiario"])


# Las rutas fijas van antes que /{anio}/{mes} para que no se las coma el path param.
@router.get("/")
async def get_historial_mensual():
    return get_historial()


@router.get("/resumen/{anio}/{mes}")
async def get_resumen(anio: int, mes: int):
    return get_estado_caja(anio, mes)


@router.get("/retiros/{anio}/{mes}")
async def get_retiros_del_mes(anio: int, mes: int):
    return get_retiros_caja(anio, mes)


@router.get("/{anio}/{mes}")
async def get_movimientos_del_mes(anio: int, mes: int):
    return get_libro_diario(anio, mes)


@router.post("/")
async def create_movimiento(movimiento_data: dict):
    return create_new_movimiento(movimiento_data)


@router.delete("/{movimiento_id}")
async def delete_movimiento(movimiento_id: int):
    return eliminar_movimiento(movimiento_id)
