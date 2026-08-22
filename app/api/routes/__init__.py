from app.api.routes.caja import router as caja_router
from app.api.routes.clientes import router as clientes_router
from app.api.routes.contratos import router as contratos_router
from app.api.routes.eventos import router as eventos_router
from app.api.routes.movimientos import router as movimientos_router
from app.api.routes.propiedades import router as propiedades_router
from app.api.routes.recibos import router as recibos_router

__all__ = [
    "caja_router",
    "clientes_router",
    "contratos_router",
    "eventos_router",
    "movimientos_router",
    "propiedades_router",
    "recibos_router",
]
