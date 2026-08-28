from sqlalchemy.exc import IntegrityError

from app.api.errors import raise_conflict, raise_not_found
from app.api.services.cliente_services import (
    buscar_duplicado,
    get_cliente_by_id,
    get_clientes,
    patch_cliente,
    update_cliente,
)


def get_all_clientes(tipo: str | None, q: str | None, limit: int, offset: int):
    return get_clientes(tipo, q, limit, offset)


def get_cliente(cliente_num: int):
    cliente = get_cliente_by_id(cliente_num)
    if not cliente:
        raise_not_found("Cliente", cliente_num)
    return cliente


def _validar_duplicado(cliente_num: int, dni: str | None, email: str | None):
    duplicado = buscar_duplicado(
        cliente_num, (dni or "").strip(), (email or "").strip()
    )
    if duplicado:
        raise_conflict(
            f"Ya existe otro cliente con ese {duplicado}",
            field=duplicado,
            code="duplicado",
        )


def update_cliente_completo(cliente_num: int, cliente_data: dict):
    """PUT: reemplazo total. Los campos obligatorios ya los garantiza el schema."""
    if not get_cliente_by_id(cliente_num):
        raise_not_found("Cliente", cliente_num)

    _validar_duplicado(cliente_num, cliente_data.get("dni"), cliente_data.get("email"))

    try:
        return update_cliente(cliente_num, cliente_data)
    except IntegrityError:
        raise_conflict("Ya existe otro cliente con ese DNI o email", code="duplicado")


def patch_cliente_parcial(cliente_num: int, campos: dict):
    """PATCH: solo toca lo que vino en el body.

    Reemplaza a los viejos PUT /clientes/email/{id} y /clientes/telefono/{id}, que
    además de mandar el valor por query string no chequeaban que el cliente
    existiera y devolvían 200 null sobre un id inexistente.
    """
    if not get_cliente_by_id(cliente_num):
        raise_not_found("Cliente", cliente_num)

    if "dni" in campos or "email" in campos:
        _validar_duplicado(cliente_num, campos.get("dni"), campos.get("email"))

    try:
        return patch_cliente(cliente_num, campos)
    except IntegrityError:
        raise_conflict("Ya existe otro cliente con ese DNI o email", code="duplicado")
