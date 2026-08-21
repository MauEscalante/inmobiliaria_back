from app.api.errors import raise_not_found, raise_unprocessable
from app.api.services.contrato_services import (
    crear_contrato,
    eliminar_contrato,
    existe_contrato,
    get_contrato_detalle,
    get_contratos,
    get_garantes_de_contrato,
    get_inquilinos_de_contrato,
)
from app.api.services.propiedades_services import get_inmueble_by_id


def get_all_contratos(estado: str | None, propiedad_id: int | None, limit: int, offset: int):
    return get_contratos(estado, propiedad_id, limit, offset)


def get_contrato_detail(contrato_id: str):
    """Antes devolvía 200 null cuando el contrato no existía."""
    contrato = get_contrato_detalle(contrato_id)
    if not contrato:
        raise_not_found("Contrato", contrato_id)
    return contrato


def get_inquilinos(contrato_id: str):
    if not existe_contrato(contrato_id):
        raise_not_found("Contrato", contrato_id)
    return get_inquilinos_de_contrato(contrato_id)


def get_garantes(contrato_id: str):
    if not existe_contrato(contrato_id):
        raise_not_found("Contrato", contrato_id)
    return get_garantes_de_contrato(contrato_id)


def create_contrato(contrato_data: dict):
    # La propiedad referenciada tiene que existir: es un dato del body inválido,
    # o sea 422, no un 404 (la colección /contratos sí existe).
    if not get_inmueble_by_id(contrato_data.get("propiedad")):
        raise_unprocessable(
            f"No existe la propiedad {contrato_data.get('propiedad')}",
            field="propiedad",
            code="referencia_inexistente",
        )
    return crear_contrato(contrato_data)


def delete_contrato(contrato_id: str) -> None:
    """Antes db.delete(None) tiraba un 500 cuando el id no existía."""
    if not eliminar_contrato(contrato_id):
        raise_not_found("Contrato", contrato_id)
