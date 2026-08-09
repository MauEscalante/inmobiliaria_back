from app.api.services.cliente_services import get_clientes, get_cliente_by_id, create_cliente, update_email,update_celular

def get_all_clientes():
    return get_clientes()

def get_cliente(id: int):
    return get_cliente_by_id(id)

def create_new_cliente(cliente_data: dict):
    return create_cliente(cliente_data)

def update_email(id: int, email: str):
    return update_email(id, email)

def update_telefono(id: int, telefono: str):
    return update_celular(id, telefono)

