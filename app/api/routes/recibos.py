from fastapi import APIRouter, HTTPException
from app.api.controllers.recibo_controller import get_recibos_ajustar, actualizar_recibos

router = APIRouter(prefix="/recibos", tags=["recibos"])



@router.get("/")
def get_recibos() -> dict:
    ws=wb.sheetnames
    return{
        "cantidad_hojas": len(ws),
        "hojas": ws
    }

@router.post("/re-ajuste/{mes_liquidacion}/{anio_liquidacion}")
def actualizar_fecha(mes_liquidacion: int, anio_liquidacion: int):
    actualizar_recibos(mes_liquidacion, anio_liquidacion)
        


@router.get("/ajustar/{mes_liquidacion}/{anio_liquidacion}")
def ajustar_recibos(mes_liquidacion: int, anio_liquidacion: int) -> list:
    try:
        recibos_ajustar = get_recibos_ajustar(mes_liquidacion, anio_liquidacion)
        return recibos_ajustar
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))