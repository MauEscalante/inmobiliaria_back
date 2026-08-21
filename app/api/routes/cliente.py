from fastapi import APIRouter
from app.api.controllers.cliente_controller import (
    get_all_clientes,
    get_cliente,
    update_cliente_completo,
    update_email,
    update_telefono,
)


# No hay alta de clientes: se crean solos al registrar un contrato (inquilino)
# o una propiedad (propietario).
router = APIRouter(prefix="/clientes", tags=["clientes"])

@router.get("/")
async def get_inquilinos():
    return get_all_clientes()

@router.get("/{id}")
async def get_inquilino(id: int):
    return get_cliente(id)

@router.put("/email/{id}")
async def update_inquilino_email(id: int, email: str):
    return update_email(id, email)

@router.put("/telefono/{id}")
async def update_inquilino_telefono(id: int, telefono: str):
    return update_telefono(id, telefono)

@router.put("/{id}")
async def update_inquilino(id: int, cliente_data: dict):
    return update_cliente_completo(id, cliente_data)
