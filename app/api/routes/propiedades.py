from fastapi import APIRouter
from app.api.controllers.propiedades_controller import get_all_propiedades, get_propiedad_by_id, create_new_propiedad, update_direccion, update_estado

router = APIRouter(prefix="/propiedades", tags=["propiedades"])

@router.get("/")
async def get_propiedades():
    return get_all_propiedades()

@router.get("/{id}")
async def get_propiedad(id: int):
    print(f"Received request for property ID: {id}")  # Debugging statement
    return get_propiedad_by_id(id)

@router.post("/register")
async def create_propiedad(propiedad_data: dict):   
    return create_new_propiedad(propiedad_data)

@router.put("/update/direccion/{id}")
async def update_propiedad_direccion(id: int, direccion: str):
    return update_direccion(id, direccion)

@router.put("/update/estado/{id}")
async def update_propiedad_estado(id: int, estado: str):
    return update_estado(id, estado)
