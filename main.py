from fastapi import FastAPI

from app.api.routes.contratos import router as contratos_router
from app.api.routes.cliente import router as inquilinos_router
from app.api.routes.propietarios import router as propietarios_router
from app.api.routes.recibos import router as recibos_router
from app.api.routes.propiedades  import router as propiedades_router

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Inmobiliaria API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(contratos_router)
app.include_router(inquilinos_router)
app.include_router(propiedades_router)
app.include_router(propietarios_router)
app.include_router(recibos_router)


@app.get("/")
def root() -> str:
	return "Inmobiliaria API"
