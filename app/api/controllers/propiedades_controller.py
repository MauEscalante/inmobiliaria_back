from app.api.errors import raise_conflict, raise_not_found
from app.api.services.propiedades_services import (
    create_inmueble,
    delete_inmueble,
    get_inmueble_by_id,
    get_inmuebles,
    get_propietarios_de_propiedad,
    patch_inmueble,
    update_inmueble,
)


def get_all_propiedades(
    estado: str | None, estado_alquiler: str | None, q: str | None, limit: int, offset: int
):
    return get_inmuebles(estado, estado_alquiler, q, limit, offset)


def get_propiedad_by_id(propiedad_id: int):
    propiedad = get_inmueble_by_id(propiedad_id)
    if not propiedad:
        raise_not_found("Propiedad", propiedad_id, femenino=True)
    return propiedad


def get_propietarios(propiedad_id: int):
    """Sub-recurso: la asociación propiedad-propietario, con su porcentaje."""
    if not get_inmueble_by_id(propiedad_id):
        raise_not_found("Propiedad", propiedad_id, femenino=True)
    return get_propietarios_de_propiedad(propiedad_id)


def create_new_propiedad(propiedad_data: dict):
    """La dirección obligatoria, el mínimo de propietarios y la suma de porcentajes
    ya los valida PropiedadCreate, así que acá no se repiten."""
    return create_inmueble(propiedad_data)


def update_propiedad(propiedad_id: int, propiedad_data: dict):
    if not get_inmueble_by_id(propiedad_id):
        raise_not_found("Propiedad", propiedad_id, femenino=True)
    return update_inmueble(propiedad_id, propiedad_data)


def patch_propiedad(propiedad_id: int, campos: dict):
    """Reemplaza a /update/direccion/{id} y /update/estado/{id}, que mandaban el
    valor por query string y no verificaban que la propiedad existiera."""
    if not get_inmueble_by_id(propiedad_id):
        raise_not_found("Propiedad", propiedad_id, femenino=True)
    return patch_inmueble(propiedad_id, campos)


def delete_propiedad(propiedad_id: int) -> None:
    if not get_inmueble_by_id(propiedad_id):
        raise_not_found("Propiedad", propiedad_id, femenino=True)
    if not delete_inmueble(propiedad_id):
        raise_conflict(
            "No se puede eliminar: la propiedad tiene contratos asociados",
            code="tiene_contratos",
        )
