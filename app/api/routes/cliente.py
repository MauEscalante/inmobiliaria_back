from fastapi import APIRouter
from app.api.controllers.cliente_controller import get_all_clientes, get_cliente, create_new_cliente, update_email, update_telefono


router = APIRouter(prefix="/inquilinos", tags=["inquilinos"])

@router.get("/")
async def get_inquilinos():
    return get_all_clientes()

@router.get("/{id}")
async def get_inquilino(id: int):
    return get_cliente(id)

@router.post("/register")
async def create_inquilino(cliente_data: dict):
    return create_new_cliente(cliente_data)

@router.put("/email/{id}")
async def update_inquilino_email(id: int, email: str):
    return update_email(id, email)

@router.put("/telefono/{id}")
async def update_inquilino_telefono(id: int, telefono: str):
    return update_telefono(id, telefono)