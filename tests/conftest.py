"""Fixtures compartidas por la suite.

Toda la suite corre **sin MySQL**. Eso es posible porque `create_engine()` es
lazy (importar la app no abre ninguna conexión) y porque las validaciones de
Pydantic y de Query cortan antes de que el handler llame a un service.
"""

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client() -> TestClient:
    """Cliente HTTP contra la app, sin levantar el lifespan.

    Ojo: NO usar `with TestClient(app) as client`. El lifespan de main.py llama a
    limpiar_interrumpidos(), que sí pega contra MySQL. Instanciando el cliente sin
    entrar al contexto, el lifespan no corre y los tests no necesitan base.
    """
    return TestClient(app)
