from app.api.services.propiedades_services import get_inmuebles, get_inmueble_by_id, create_inmueble, update_estado_by_id,update_direccion_by_id

def get_all_propiedades():
    return get_inmuebles()

def get_propiedad_by_id(id: int):
    print(f"Fetching property with ID: {id}")  # Debugging statement
    return get_inmueble_by_id(id)       

def create_new_propiedad(propiedad_data: dict):
    return create_inmueble(propiedad_data)

def update_direccion(id: int, direccion: str):
    return update_direccion_by_id(id, direccion)

def update_estado(id: int, estado: str):
    return update_estado_by_id(id, estado)    
