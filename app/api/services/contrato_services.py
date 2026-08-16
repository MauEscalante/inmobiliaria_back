from app.models.contrato import Contrato
from app.database.connection import SessionLocal
from sqlalchemy import text

def get_contratos():
    db = SessionLocal()
    try:
        contratos=db.query(Contrato).all()
        return contratos
    finally:
        db.close()

def get_contrato_by_id(id: int):
    db = SessionLocal()
    try:
        return db.query(Contrato).where(Contrato.contrato_id == id).first()
    finally:
        db.close()

def crear_contrato(contrato_data: dict):
    db = SessionLocal()
    try:
        contrato = Contrato(**contrato_data)
        db.add(contrato)
        db.commit()
        db.refresh(contrato)
        return contrato
    finally:
        db.close()

def eliminar_contrato(id: int):
    db = SessionLocal()
    try:
        contrato = db.query(Contrato).where(Contrato.contrato_id == id).first()
        db.delete(contrato)
        db.commit()
    finally:
        db.close()