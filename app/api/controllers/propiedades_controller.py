from fastapi import HTTPException

from app.api.services.propiedades_services import (
    get_inmuebles,
    get_inmueble_by_id,
    create_inmueble,
    update_inmueble,
    delete_inmueble,
    update_estado_by_id,
    update_direccion_by_id,
    PropietarioInexistenteError,
)

# Los porcentajes se guardan como DECIMAL(5,2), así que se compara la suma con
# una tolerancia en lugar de exigir igualdad exacta.
TOLERANCIA_PORCENTAJE = 0.01


def _validar_propietarios(propiedad_data: dict) -> list:
    """Valida los propietarios del alta y devuelve la lista con el porcentaje resuelto.

    Con un solo propietario el porcentaje es opcional y se asume 100; con varios
    hay que indicarlo y la suma debe dar 100.
    """
    propietarios = propiedad_data.get("propietarios") or []

    if not propietarios:
        raise HTTPException(status_code=400, detail="La propiedad necesita al menos un propietario")

    try:
        comision = float(propiedad_data.get("comision"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="La comisión debe ser un número")

    if comision < 0:
        raise HTTPException(status_code=400, detail="La comisión no puede ser negativa")

    resueltos = []

    for propietario in propietarios:
        if not propietario.get("cliente_num"):
            faltantes = [campo for campo in ("nombre", "apellido", "dni") if not propietario.get(campo)]
            if faltantes:
                raise HTTPException(
                    status_code=400,
                    detail=f"Al propietario nuevo le faltan datos: {', '.join(faltantes)}",
                )

        if len(propietarios) == 1:
            porcentaje = 100.0
        else:
            try:
                porcentaje = float(propietario.get("porcentaje"))
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=400,
                    detail="Cuando hay varios propietarios cada uno necesita su porcentaje",
                )

            if porcentaje <= 0:
                raise HTTPException(status_code=400, detail="Los porcentajes deben ser mayores a 0")

        resueltos.append({**propietario, "porcentaje": porcentaje})

    suma = sum(propietario["porcentaje"] for propietario in resueltos)

    if abs(suma - 100) > TOLERANCIA_PORCENTAJE:
        raise HTTPException(
            status_code=400,
            detail=f"Los porcentajes deben sumar 100%. Actualmente suman {suma:g}%",
        )

    return resueltos

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

    propietarios = _validar_propietarios(propiedad_data)

    try:
        return create_inmueble({**propiedad_data, "propietarios": propietarios})
    except PropietarioInexistenteError as error:
        raise HTTPException(status_code=404, detail=str(error))

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
