from app.api.services.evento_service import get_eventos


def get_all_eventos(dias: int, limit: int, offset: int):
    return get_eventos(dias, limit, offset)
