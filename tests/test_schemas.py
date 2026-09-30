"""Tests de las reglas de negocio que viven en los validadores de los schemas.

Es la lógica más densa del backend que no depende de la base de datos.
"""

import pytest
from pydantic import ValidationError

from app.models.contrato import TipoGarantia
from app.models.libro_diario import CuentaTransferencia, TipoMovimiento
from app.schemas.cliente import ClienteUpdate
from app.schemas.contrato import ContratoCreate
from app.schemas.movimiento import MovimientoCreate
from app.schemas.propiedad import PropiedadCreate
from app.schemas.recibo import AjusteCreate

UN_INQUILINO = [{
    "nombre": "Ana", "apellido": "Perez", "telefono": "1140000001", "dni": "30111222",
    "email": "ana@test.com",
}]
UN_GARANTE = [{
    "nombre": "Luis", "apellido": "Gomez", "telefono": "1140000002", "email": "luis@test.com",
}]
# Un garante de garantía propietaria: respalda con su inmueble, no tiene email.
UN_GARANTE_SIN_EMAIL = [{"nombre": "Luis", "apellido": "Gomez", "telefono": "1140000002"}]


def contrato(**overrides):
    """Contrato válido mínimo; cada test pisa solo el campo que le interesa."""
    datos = {
        "propiedad": 1,
        "fecha_inicio": "2026-01-01",
        "fecha_fin": "2027-01-01",
        "importe_inicial": "500000.00",
        "inquilinos": UN_INQUILINO,
    }
    datos.update(overrides)
    return datos


class TestContratoFechas:
    def test_acepta_fecha_fin_posterior(self):
        assert ContratoCreate(**contrato()).fecha_fin.year == 2027

    def test_rechaza_fecha_fin_anterior_al_inicio(self):
        with pytest.raises(ValidationError, match="posterior a fecha_inicio"):
            ContratoCreate(**contrato(fecha_fin="2025-01-01"))

    def test_rechaza_fechas_iguales(self):
        with pytest.raises(ValidationError, match="posterior a fecha_inicio"):
            ContratoCreate(**contrato(fecha_inicio="2026-01-01", fecha_fin="2026-01-01"))


class TestContratoGarantia:
    """GPremier nunca lleva garantes; la garantía 'Garantes' exige al menos uno."""

    def test_gpremier_sin_garantes_es_valido(self):
        creado = ContratoCreate(**contrato(garantia=TipoGarantia.GPremier))
        assert creado.garantes == []

    def test_gpremier_con_garantes_falla(self):
        with pytest.raises(ValidationError, match="GPremier no lleva garantes"):
            ContratoCreate(**contrato(garantia=TipoGarantia.GPremier, garantes=UN_GARANTE))

    def test_garantia_garantes_sin_ninguno_falla(self):
        with pytest.raises(ValidationError, match="requiere al menos un garante"):
            ContratoCreate(**contrato(garantia=TipoGarantia.Garantes, garantes=[]))

    def test_garantia_garantes_con_uno_es_valido(self):
        creado = ContratoCreate(**contrato(garantia=TipoGarantia.Garantes, garantes=UN_GARANTE))
        assert len(creado.garantes) == 1

    def test_garantia_propietaria_acepta_no_llevar_garantes(self):
        creado = ContratoCreate(**contrato(garantia=TipoGarantia.GarantiaPropietaria))
        assert creado.garantes == []

    def test_garantia_garantes_exige_email_en_cada_garante(self):
        with pytest.raises(ValidationError, match="cada garante necesita email"):
            ContratoCreate(**contrato(
                garantia=TipoGarantia.Garantes, garantes=UN_GARANTE_SIN_EMAIL,
            ))

    def test_garantia_propietaria_no_pide_email_al_garante(self):
        creado = ContratoCreate(**contrato(
            garantia=TipoGarantia.GarantiaPropietaria, garantes=UN_GARANTE_SIN_EMAIL,
        ))
        assert creado.garantes[0].email is None


class TestContratoInquilinos:
    def test_inquilino_sin_email_falla(self):
        sin_email = [{k: v for k, v in UN_INQUILINO[0].items() if k != "email"}]
        with pytest.raises(ValidationError, match="email"):
            ContratoCreate(**contrato(inquilinos=sin_email))

    def test_inquilino_con_email_vacio_falla(self):
        with pytest.raises(ValidationError, match="email"):
            ContratoCreate(**contrato(inquilinos=[{**UN_INQUILINO[0], "email": ""}]))


class TestContratoImportes:
    def test_importe_inicial_debe_ser_positivo(self):
        with pytest.raises(ValidationError):
            ContratoCreate(**contrato(importe_inicial="0"))

    def test_necesita_al_menos_un_inquilino(self):
        with pytest.raises(ValidationError):
            ContratoCreate(**contrato(inquilinos=[]))


class TestMovimientoCoherencia:
    """Ingresos y depósitos son plata de una propiedad; egresos y retiros llevan concepto."""

    def test_ingreso_sin_propiedad_falla(self):
        with pytest.raises(ValidationError, match="necesita propiedad_id"):
            MovimientoCreate(fecha="2026-08-01", tipo=TipoMovimiento.INGRESO, monto="1000.00")

    def test_ingreso_con_propiedad_es_valido(self):
        movimiento = MovimientoCreate(
            fecha="2026-08-01", tipo=TipoMovimiento.INGRESO, monto="1000.00", propiedad_id=5,
        )
        assert movimiento.propiedad_id == 5

    def test_egreso_sin_concepto_falla(self):
        with pytest.raises(ValidationError, match="necesita concepto"):
            MovimientoCreate(fecha="2026-08-01", tipo=TipoMovimiento.EGRESO, monto="1000.00")

    def test_egreso_con_concepto_en_blanco_falla(self):
        with pytest.raises(ValidationError, match="necesita concepto"):
            MovimientoCreate(
                fecha="2026-08-01", tipo=TipoMovimiento.EGRESO, monto="1000.00", concepto="   ",
            )

    def test_retiro_con_concepto_es_valido(self):
        movimiento = MovimientoCreate(
            fecha="2026-08-01", tipo=TipoMovimiento.RETIRO, monto="1000.00", concepto="Retiro Kike",
        )
        assert movimiento.concepto == "Retiro Kike"

    def test_deposito_sin_cuenta_falla(self):
        with pytest.raises(ValidationError, match="necesita indicar la cuenta"):
            MovimientoCreate(
                fecha="2026-08-01", tipo=TipoMovimiento.DEPOSITO, monto="1000.00", propiedad_id=5,
            )

    def test_deposito_con_cuenta_es_valido(self):
        movimiento = MovimientoCreate(
            fecha="2026-08-01",
            tipo=TipoMovimiento.DEPOSITO,
            monto="1000.00",
            propiedad_id=5,
            cuenta=CuentaTransferencia.Kike,
        )
        assert movimiento.cuenta == CuentaTransferencia.Kike

    def test_monto_debe_ser_positivo(self):
        with pytest.raises(ValidationError):
            MovimientoCreate(
                fecha="2026-08-01", tipo=TipoMovimiento.INGRESO, monto="0", propiedad_id=5,
            )


class TestAjusteCreate:
    """El período dejó de ser un identificador en la URL y ahora se valida."""

    def test_periodo_valido(self):
        assert AjusteCreate(mes=8, anio=2026).mes == 8

    @pytest.mark.parametrize("mes", [0, 13, 99])
    def test_mes_fuera_de_rango_falla(self, mes):
        with pytest.raises(ValidationError):
            AjusteCreate(mes=mes, anio=2026)

    @pytest.mark.parametrize("anio", [1899, 2101])
    def test_anio_fuera_de_rango_falla(self, anio):
        with pytest.raises(ValidationError):
            AjusteCreate(mes=8, anio=anio)


class TestClienteUpdate:
    def cliente(self, **overrides):
        datos = {"nombre": "Ana", "apellido": "Perez", "dni": "30111222", "telefono": "1140000001"}
        datos.update(overrides)
        return datos

    def test_email_valido_pasa(self):
        assert ClienteUpdate(**self.cliente(email="ana@test.com")).email == "ana@test.com"

    @pytest.mark.parametrize("email", ["sin-arroba", "ana@sinpunto", "ana @test.com"])
    def test_email_invalido_falla(self, email):
        with pytest.raises(ValidationError):
            ClienteUpdate(**self.cliente(email=email))

    def test_email_es_obligatorio(self):
        with pytest.raises(ValidationError, match="email"):
            ClienteUpdate(**self.cliente())

    @pytest.mark.parametrize("email", ["", "   "])
    def test_email_vacio_falla(self, email):
        with pytest.raises(ValidationError, match="email"):
            ClienteUpdate(**self.cliente(email=email))

    def test_nombre_mas_largo_que_la_columna_falla(self):
        # La columna es varchar(15).
        with pytest.raises(ValidationError):
            ClienteUpdate(**self.cliente(nombre="A" * 16))

    def test_nombre_vacio_falla(self):
        with pytest.raises(ValidationError):
            ClienteUpdate(**self.cliente(nombre=""))


class TestPropiedadCreate:
    """El propietario nuevo se da de alta como cliente en el mismo POST, así que
    necesita DNI y email; el existente viaja solo con su cliente_num."""

    NUEVO = {
        "porcentaje": 100, "nombre": "Juan", "apellido": "Garcia", "dni": "30123456",
        "telefono": "1155253547", "email": "juan@test.com",
    }

    def propiedad(self, **overrides):
        datos = {
            "direccion": "Av. Siempre Viva 742", "comision": "6.5", "propietarios": [self.NUEVO],
        }
        datos.update(overrides)
        return datos

    def test_propietario_nuevo_completo_pasa(self):
        creada = PropiedadCreate(**self.propiedad())
        assert creada.propietarios[0].email == "juan@test.com"

    def test_propietario_nuevo_sin_email_falla(self):
        sin_email = {k: v for k, v in self.NUEVO.items() if k != "email"}
        with pytest.raises(ValidationError, match="un propietario nuevo necesita email"):
            PropiedadCreate(**self.propiedad(propietarios=[sin_email]))

    def test_propietario_nuevo_con_email_vacio_falla(self):
        # Es lo que mandaba el front cuando el campo quedaba en blanco.
        with pytest.raises(ValidationError, match="email"):
            PropiedadCreate(**self.propiedad(propietarios=[{**self.NUEVO, "email": ""}]))

    def test_propietario_nuevo_sin_dni_falla(self):
        sin_dni = {k: v for k, v in self.NUEVO.items() if k != "dni"}
        with pytest.raises(ValidationError, match="un propietario nuevo necesita DNI"):
            PropiedadCreate(**self.propiedad(propietarios=[sin_dni]))

    def test_propietario_existente_no_necesita_email(self):
        existente = {"cliente_num": 7, "porcentaje": 100}
        creada = PropiedadCreate(**self.propiedad(propietarios=[existente]))
        assert creada.propietarios[0].email is None

    def test_porcentajes_deben_sumar_100(self):
        with pytest.raises(ValidationError, match="deben sumar 100%"):
            PropiedadCreate(**self.propiedad(propietarios=[
                {"cliente_num": 7, "porcentaje": 60},
                {"cliente_num": 8, "porcentaje": 30},
            ]))
