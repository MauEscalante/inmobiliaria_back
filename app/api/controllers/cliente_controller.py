from fastapi import HTTPException

from app.api.services.cliente_services import get_clientes, get_cliente_by_id, create_cliente, update_email,update_celular
from app.api.services.contrato_services import get_valores_historicos_por_cliente

def get_all_clientes():
    return get_clientes()

def get_cliente(id: int):
    return get_cliente_by_id(id)

def get_historial_cliente(id: int):
    # Sin el chequeo, un id inexistente devolvería una lista vacía y se leería como
    # "este cliente no tiene ajustes" en vez de "este cliente no existe".
    if not get_cliente_by_id(id):
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return get_valores_historicos_por_cliente(id)

def create_new_cliente(cliente_data: dict):
    return create_cliente(cliente_data)

def update_email(id: int, email: str):
    return update_email(id, email)

def update_telefono(id: int, telefono: str):
    return update_celular(id, telefono)

