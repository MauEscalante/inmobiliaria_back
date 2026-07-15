from fastapi import FastAPI

from app.api.routes.ajustes import router as ajustes_router
from app.api.routes.contratos import router as contratos_router
from app.api.routes.inquilinos import router as inquilinos_router
from app.api.routes.propietarios import router as propietarios_router
from app.api.routes.recibos import router as recibos_router


app = FastAPI(title="Inmobiliaria API")

app.include_router(ajustes_router)
app.include_router(contratos_router)
app.include_router(inquilinos_router)
app.include_router(propietarios_router)
app.include_router(recibos_router)


@app.get("/")
def root() -> str:
	return "Inmobiliaria API"
