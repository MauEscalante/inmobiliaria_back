"""Tests de los helpers puros: paginación y serialización de filas."""

from datetime import date, datetime
from decimal import Decimal

from app.schemas.common import Page
from app.utils.helpers import Paginacion, serializar_fila


class TestPageCrear:
    """El cálculo de `pages` es lo que decide cuántas vueltas da el cliente."""

    def test_division_no_exacta_redondea_hacia_arriba(self):
        page = Page.crear(items=[1, 2, 3], total=25, page=1, page_size=20)
        assert page.pages == 2

    def test_division_exacta_no_agrega_una_pagina_de_mas(self):
        page = Page.crear(items=[], total=40, page=1, page_size=20)
        assert page.pages == 2

    def test_coleccion_vacia_no_tiene_paginas(self):
        page = Page.crear(items=[], total=0, page=1, page_size=20)
        assert page.pages == 0
        assert page.items == []

    def test_page_size_cero_no_divide_por_cero(self):
        assert Page.crear(items=[], total=10, page=1, page_size=0).pages == 0

    def test_conserva_los_datos_que_recibe(self):
        page = Page.crear(items=["a", "b"], total=2, page=3, page_size=20)
        assert (page.items, page.total, page.page, page.page_size) == (["a", "b"], 2, 3, 20)


class TestPaginacion:
    def test_limit_es_el_page_size(self):
        assert Paginacion(page=1, page_size=20).limit == 20

    def test_primera_pagina_arranca_en_cero(self):
        assert Paginacion(page=1, page_size=20).offset == 0

    def test_offset_saltea_las_paginas_anteriores(self):
        assert Paginacion(page=3, page_size=20).offset == 40


class TestSerializarFila:
    """El cliente espera números y fechas ISO, no Decimal ni objetos date."""

    def test_decimal_pasa_a_float(self):
        fila = serializar_fila({"monto": Decimal("1234.56")})
        assert fila["monto"] == 1234.56
        assert isinstance(fila["monto"], float)

    def test_date_pasa_a_iso(self):
        assert serializar_fila({"fecha": date(2026, 8, 25)})["fecha"] == "2026-08-25"

    def test_datetime_pasa_a_iso(self):
        fila = serializar_fila({"creado_en": datetime(2026, 8, 25, 14, 30, 0)})
        assert fila["creado_en"] == "2026-08-25T14:30:00"

    def test_el_resto_de_los_tipos_queda_intacto(self):
        original = {"id": 7, "nombre": "Ana", "activo": True, "sin_dato": None}
        assert serializar_fila(original) == original
