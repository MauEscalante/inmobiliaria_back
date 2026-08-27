import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import api_router
from app.api.services.ajuste_service import limpiar_interrumpidos
from app.config import settings
from app.schemas.common import ErrorResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cierra los ajustes de recibos que quedaron a medias.

    El ajuste corre en segundo plano, así que un corte del proceso lo deja en
    'en_proceso' para siempre. Como solo se admite un ajuste a la vez, esa fila
    huérfana bloquearía todos los siguientes. Con --reload esto pasa seguido.
    """
    interrumpidos = limpiar_interrumpidos()
    if interrumpidos:
        logger.warning("Se cerraron %s ajustes interrumpidos por un reinicio", interrumpidos)
    yield


app = FastAPI(
    lifespan=lifespan,
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description=(
        "API de administración inmobiliaria: propiedades, contratos, clientes, "
        "libro diario y recibos."
    ),
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Sin esto el navegador no puede leer el Location que devuelven los POST ni el
    # Content-Disposition con el que el front nombra la planilla que descarga.
    expose_headers=["Location", "Content-Disposition"],
)


def _envelope(
    request: Request,
    status_code: int,
    error: str,
    message: str,
    details: list | None = None,
) -> JSONResponse:
    """Toda respuesta de error sale con esta misma forma."""
    cuerpo = ErrorResponse(
        error=error,
        message=message,
        details=details,
        timestamp=datetime.now(UTC).isoformat(),
        path=request.url.path,
    )
    return JSONResponse(status_code=status_code, content=cuerpo.model_dump())


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Los helpers de app/api/errors.py mandan un dict con message y details.

    Se sigue aceptando el detail string suelto para lo que levante Starlette.
    """
    if isinstance(exc.detail, dict):
        message = exc.detail.get("message", "Error")
        details = exc.detail.get("details")
    else:
        message = str(exc.detail)
        details = None

    return _envelope(
        request,
        exc.status_code,
        error=_NOMBRES_POR_CODIGO.get(exc.status_code, "HTTPError"),
        message=message,
        details=details,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """422 con el campo que falló, en vez del formato suelto de FastAPI."""
    details = []
    for error in exc.errors():
        # loc viene como ("body", "email"); el primer tramo es de dónde salió.
        ubicacion = ([str(parte) for parte in error["loc"][1:]]
                     or [str(parte) for parte in error["loc"]])
        details.append({
            "field": ".".join(ubicacion),
            "message": error["msg"],
            "code": error["type"],
        })

    return _envelope(
        request,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        error="ValidationError",
        message="Los datos enviados no son válidos",
        details=details,
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Choque contra una restricción de la base: es un conflicto, no un 500."""
    return _envelope(
        request,
        status.HTTP_409_CONFLICT,
        error="Conflict",
        message="La operación choca con un dato ya existente",
        details=[{
            "field": None,
            "message": "Violación de una restricción de unicidad o clave foránea",
            "code": "integrity_error",
        }],
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    # El texto de la excepción trae SQL y rutas internas: no se devuelve al cliente.
    return _envelope(
        request,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        error="DatabaseError",
        message="Error al acceder a la base de datos",
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return _envelope(
        request,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        error="InternalServerError",
        message="Error interno del servidor",
    )


_NOMBRES_POR_CODIGO = {
    400: "BadRequest",
    401: "Unauthorized",
    403: "Forbidden",
    404: "NotFound",
    405: "MethodNotAllowed",
    409: "Conflict",
    422: "ValidationError",
    500: "InternalServerError",
}


app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/health", tags=["health"], summary="Estado del servicio")
def health():
    return {
        "status": "ok",
        "version": settings.API_VERSION,
        "timestamp": datetime.now(UTC).isoformat(),
    }
