from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.api.services.cliente_services import (
    buscar_duplicado,
    get_clientes,
    get_cliente_by_id,
    update_cliente,
    update_email as update_email_service,
    update_celular,
)

# Datos mínimos para que un cliente sea identificable.
CAMPOS_OBLIGATORIOS = ("nombre", "apellido", "dni", "telefono")


def get_all_clientes():
    return get_clientes()


def get_cliente(id: int):
    cliente = get_cliente_by_id(id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return cliente


def update_cliente_completo(id: int, cliente_data: dict):
    if not get_cliente_by_id(id):
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    faltantes = [campo for campo in CAMPOS_OBLIGATORIOS if not (cliente_data.get(campo) or "").strip()]
    if faltantes:
        raise HTTPException(status_code=400, detail=f"Faltan datos obligatorios: {', '.join(faltantes)}")

    duplicado = buscar_duplicado(id, (cliente_data.get("dni") or "").strip(), (cliente_data.get("email") or "").strip())
    if duplicado:
        raise HTTPException(status_code=409, detail=f"Ya existe otro cliente con ese {duplicado}")

    try:
        return update_cliente(id, cliente_data)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Ya existe otro cliente con ese DNI o email")


def update_email(id: int, email: str):
    return update_email_service(id, email)


def update_telefono(id: int, telefono: str):
    return update_celular(id, telefono)
