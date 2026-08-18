from app.api.services.contrato_services import get_contratos, get_contrato_by_id, crear_contrato, eliminar_contrato

def get_all_contratos():
    return get_contratos()

def get_contratoDetail(id: int):
    return get_contrato_by_id(id)

def create_contrato(contrato_data: dict):
    return crear_contrato(contrato_data)

def delete_contrato(id: int):
    return eliminar_contrato(id, )
