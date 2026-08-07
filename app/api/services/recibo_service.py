from pydantic import json

from app.models.contrato import Contrato
from app.database.connection import SessionLocal
from sqlalchemy import text
from datetime import date
from openpyxl import load_workbook
from copy import copy
import requests


def get_propiedades_ajustar(mes_liquidacion: int, año_liquidacion: int) -> list:
    db = SessionLocal()
    try:
        fecha_liquidacion = date(año_liquidacion, mes_liquidacion, 1)
        query = text("""
        SELECT *
        FROM contrato
        WHERE tipo_ajuste ="IPC"
        AND TIMESTAMPDIFF(
                MONTH,
                fecha_inicio,
                :fecha_liquidacion
            ) > 0
        AND MOD(
                TIMESTAMPDIFF(
                    MONTH,
                    fecha_inicio,
                    :fecha_liquidacion
                ),
                periodicidad
            ) = 0
        """)

        contratos = db.execute(
            query,
            {"fecha_liquidacion": fecha_liquidacion}
        ).fetchall()

        return [dict(fila._mapping) for fila in contratos]
    
    except Exception as e:
        raise e
    finally:
        db.close()

def actualizar_fechas(recibo: str, mes_liquidacion: int, año_liquidacion: int, wb: load_workbook) -> None:
    meses = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
    }  
    #recorre todas las hojas del excel
    ws = wb[recibo]
    #cambia la fecha del recibo y el mes
    ws["I13"].value = mes_liquidacion
    ws["C22"].value = meses[mes_liquidacion]
    ws["J13"].value = año_liquidacion

def actualizar_ipc(recibo: str, wb: load_workbook, valores_ipc: list) -> None:
    ws = wb[recibo]
    for i in valores_ipc:
        #El valor a actualizar en re-ajuste debe ser sacado de la db ya que el del recibo ya tiene una aproximacion hecha y no es el valor a tomar para el re-ajuste
        ws["E22"].value = float(ws["E22"].value)*i["valor"]
    
    

    
def get_ipc() -> list:
    response =requests.get("https://api.argly.com.ar/v1/ipc?historico=true")
    data = response.json().get("data", [])
    ultimos_4 = data[-4:]
    return ultimos_4