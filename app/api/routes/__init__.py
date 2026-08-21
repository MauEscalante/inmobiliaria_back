
from app.api.routes.contratos import router as contratos_router
from app.api.routes.cliente import router as inquilinos_router
from app.api.routes.propietarios import router as propietarios_router
from app.api.routes.recibos import router as recibos_router
from app.api.routes.propiedades import router as propiedades_router
from app.api.routes.libro_diario import router as libro_diario_router


__all__ = [
	"propiedades_router",
	"contratos_router",
	"inquilinos_router",
	"propietarios_router",
	"recibos_router",
	"libro_diario_router",
]
