from fastapi import HTTPException

from app.api.services.propiedades_services import (
    get_inmuebles,
    get_inmueble_by_id,
    create_inmueble,
    update_inmueble,
    delete_inmueble,
    update_estado_by_id,
    update_direccion_by_id,
)

def get_all_propiedades():
    return get_inmuebles()

def get_propiedad_by_id(id: int):
    propiedad = get_inmueble_by_id(id)
    if not propiedad:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")
    return propiedad

def create_new_propiedad(propiedad_data: dict):
    if not propiedad_data.get("direccion"):
        raise HTTPException(status_code=400, detail="La dirección es obligatoria")
    return create_inmueble(propiedad_data)

def update_propiedad(id: int, propiedad_data: dict):
    if not get_inmueble_by_id(id):
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")
    if not propiedad_data.get("direccion"):
        raise HTTPException(status_code=400, detail="La dirección es obligatoria")
    return update_inmueble(id, propiedad_data)

def delete_propiedad(id: int):
    if not get_inmueble_by_id(id):
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")
    if not delete_inmueble(id):
        raise HTTPException(status_code=409, detail="No se puede eliminar: la propiedad tiene contratos asociados")
    return {"propiedad_id": id}

def update_direccion(id: int, direccion: str):
    return update_direccion_by_id(id, direccion)

def update_estado(id: int, estado: str):
    return update_estado_by_id(id, estado)
