from api.services.cliente_services import get_usuarios, get_usuario_by_id, create_usuario, update_email, delete_usuario

def get_all_usuarios():
    return get_usuarios()

def get_usuario(id: int):
    return get_usuario_by_id(id)

def create_new_usuario(usuario_data: dict):
    return create_usuario(usuario_data)

def update_email(id: int, email: str):
    return update_email(id, email)

def update_telefono(id: int, telefono: str):
    return update_telefono(id, telefono)

def delete_existing_usuario(id: int):
    return delete_usuario(id)