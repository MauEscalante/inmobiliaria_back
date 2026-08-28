"""Tests del contrato HTTP: el envelope de error y las validaciones de entrada.

Es la forma exacta que consume el front (`mensajeDeError` en
Uzquiza-front/src/services/api.ts lee `message` y `details[].field`).

Ninguno de estos tests toca MySQL: las validaciones cortan antes de que el
handler llame a un service, y el 404 lo resuelve el router.
"""

CAMPOS_DEL_ENVELOPE = {"error", "message", "details", "timestamp", "path"}


class TestHealth:
    def test_responde_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestEnvelopeDe404:
    """Starlette devolvería {"detail": "Not Found"}; el handler lo normaliza."""

    def test_ruta_inexistente_usa_el_envelope(self, client):
        response = client.get("/api/v1/ruta-que-no-existe")
        assert response.status_code == 404
        assert CAMPOS_DEL_ENVELOPE <= response.json().keys()

    def test_el_path_del_envelope_es_el_pedido(self, client):
        response = client.get("/api/v1/ruta-que-no-existe")
        assert response.json()["path"] == "/api/v1/ruta-que-no-existe"

    def test_sin_el_prefijo_de_version_no_hay_recurso(self, client):
        # Es el 404 que veía el front cuando pegaba a /propiedades/ sin /api/v1.
        assert client.get("/propiedades/").status_code == 404


class TestValidacionDeQuery:
    """`/recibos/pendientes` valida el período, que antes iba suelto en el path."""

    def test_mes_fuera_de_rango_da_422(self, client):
        response = client.get("/api/v1/recibos/pendientes?mes=99&anio=2026")
        assert response.status_code == 422

    def test_el_422_identifica_el_campo_que_fallo(self, client):
        cuerpo = client.get("/api/v1/recibos/pendientes?mes=99&anio=2026").json()
        assert cuerpo["error"] == "ValidationError"
        assert cuerpo["message"] == "Los datos enviados no son válidos"
        assert [d["field"] for d in cuerpo["details"]] == ["mes"]

    def test_falta_un_parametro_obligatorio(self, client):
        cuerpo = client.get("/api/v1/recibos/pendientes?mes=8").json()
        assert "anio" in [d["field"] for d in cuerpo["details"]]

    def test_page_size_por_encima_del_tope_da_422(self, client):
        cuerpo = client.get("/api/v1/propiedades?page_size=500").json()
        assert "page_size" in [d["field"] for d in cuerpo["details"]]


class TestValidacionDeBody:
    def test_body_vacio_da_422_con_detalle(self, client):
        response = client.post("/api/v1/propiedades", json={})
        assert response.status_code == 422
        assert response.json()["details"]

    def test_contrato_con_fechas_incoherentes_da_422(self, client):
        response = client.post("/api/v1/contratos", json={
            "propiedad": 1,
            "fecha_inicio": "2027-01-01",
            "fecha_fin": "2026-01-01",
            "importe_inicial": "500000.00",
            "inquilinos": [
                {"nombre": "Ana", "apellido": "Perez", "telefono": "1140000001", "dni": "30111222"},
            ],
        })
        assert response.status_code == 422

    def test_ajuste_con_mes_invalido_da_422(self, client):
        response = client.post("/api/v1/recibos/ajustes", json={"mes": 99, "anio": 1})
        assert response.status_code == 422
        assert {"mes", "anio"} <= {d["field"] for d in response.json()["details"]}


class TestMetodoNoPermitido:
    def test_clientes_no_acepta_post(self, client):
        # El alta de clientes se sacó a propósito: se crean solos.
        assert client.post("/api/v1/clientes", json={}).status_code == 405
