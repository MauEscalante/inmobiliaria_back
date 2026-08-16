from fastapi import APIRouter
from app.api.controllers.contrato_controller import get_all_contratos, get_contratoDetail, create_contrato, delete_contrato

router = APIRouter(prefix="/contratos", tags=["contratos"])

@router.get("/")
async def get_contratos():
    return get_all_contratos()

@router.get("/{id}")
async def contratoDetails(id: int):
    return get_contratoDetail(id)

@router.post("/create-contrato")
async def createContrato(contrato_data: dict):
    return create_contrato(contrato_data)

@router.delete("/{id}")
async def deleteContrato(id: int):
    return delete_contrato(id)