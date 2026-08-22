"""Router agregado de la API. main.py lo monta una sola vez bajo /api/v1."""

from fastapi import APIRouter

from app.api.routes import (
    caja_router,
    clientes_router,
    contratos_router,
    eventos_router,
    movimientos_router,
    propiedades_router,
    recibos_router,
)

api_router = APIRouter()

api_router.include_router(clientes_router)
api_router.include_router(propiedades_router)
api_router.include_router(contratos_router)
api_router.include_router(movimientos_router)
api_router.include_router(caja_router)
api_router.include_router(recibos_router)
api_router.include_router(eventos_router)

__all__ = ["api_router"]
