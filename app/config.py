"""Configuración de la app, leída del entorno.

Se usa os.getenv en vez de pydantic-settings para no sumar una dependencia que
no está instalada en el entorno del proyecto.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def _bool(nombre: str, por_defecto: bool = False) -> bool:
    valor = os.getenv(nombre)
    if valor is None:
        return por_defecto
    return valor.strip().lower() in ("1", "true", "yes", "on")


def _lista(nombre: str, por_defecto: list[str]) -> list[str]:
    valor = os.getenv(nombre)
    if not valor:
        return por_defecto
    return [item.strip() for item in valor.split(",") if item.strip()]


class Settings:
    # Prefijo de versión. Todo endpoint de negocio cuelga de acá.
    API_PREFIX: str = "/api/v1"
    API_VERSION: str = "1.0.0"
    API_TITLE: str = "Inmobiliaria API"

    # OJO: el default sigue trayendo la credencial de root hardcodeada, tal como
    # estaba en connection.py, para no romper el entorno local. Lo correcto es
    # definir DATABASE_URL en el .env y dejar este default sin password.
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "mysql+pymysql://root:Escalante1218@localhost/inmobiliaria_db"
    )
    # El log de SQL imprime los parámetros (DNI, email, importes): fuera de
    # desarrollo conviene dejarlo apagado.
    SQL_ECHO: bool = _bool("SQL_ECHO", False)

    CORS_ORIGINS: list[str] = _lista(
        "CORS_ORIGINS", ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # Planilla de recibos. Ruta relativa al proceso salvo que se configure absoluta.
    RECIBOS_TEMPLATE: str = os.getenv(
        "RECIBOS_TEMPLATE", "templates/RECIBO INMOBILIARIO.xlsx"
    )
    IPC_API_URL: str = os.getenv(
        "IPC_API_URL", "https://api.argly.com.ar/v1/ipc?historico=true"
    )
    IPC_TIMEOUT: float = float(os.getenv("IPC_TIMEOUT", "10"))


settings = Settings()
