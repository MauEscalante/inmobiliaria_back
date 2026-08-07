from fastapi import APIRouter
from api.controllers.cliente_controller import get_all_usuarios, get_usuario, create_new_usuario, update_email, update_telefono, delete_existing_usuario


router = APIRouter(prefix="/inquilinos", tags=["inquilinos"])

@router.get("/")
async def get_inquilinos():
    return get_all_usuarios()

@router.get("/{id}")
async def get_inquilino(id: int):
    return get_usuario(id)

@router.post("/register")
async def create_inquilino(usuario_data: dict):
    return create_new_usuario(usuario_data)

@router.put("/email/{id}")
async def update_inquilino_email(id: int, email: str):
    return update_email(id, email)

@router.put("/telefono/{id}")
async def update_inquilino_telefono(id: int, telefono: str):
    return update_telefono(id, telefono)