from app.models.propiedad import Propiedad
from app.database.connection import SessionLocal
from sqlalchemy import text

def get_inmuebles() -> list:
    try:
        db= SessionLocal()
        propiedad= db.query(Propiedad).all()
        return propiedad
    except Exception as e:
        raise e

def get_inmueble_by_id(propiedad_id: int) -> Propiedad:
    try:
        db= SessionLocal()
        query= text("""SELECT * FROM propiedad WHERE propiedad_id = :propiedad_id""")
        propiedad= db.execute(query, {"propiedad_id": propiedad_id}).mappings().first()
        return dict(propiedad) if propiedad else None
    except Exception as e:
        raise e

def create_inmueble(propiedad_data: dict) -> Propiedad:
    try:
        db= SessionLocal()
        nueva_propiedad= Propiedad(**propiedad_data)
        db.add(nueva_propiedad)
        db.commit()
        db.refresh(nueva_propiedad)
        return nueva_propiedad
    except Exception as e:
        raise e

def update_direccion_by_id(propiedad_id: int, direccion: str) -> Propiedad:
    try:
        db= SessionLocal()
        query=text("""
        UPDATE propiedad
        SET direccion= :direccion
        WHERE propiedad_id= :propiedad_id
        """)
        db.execute(query, {"direccion": direccion, "propiedad_id": propiedad_id})
        db.commit()
    except Exception as e:
        raise e

def update_estado_by_id(propiedad_id: int, estado: str) -> Propiedad:
    try:
        db= SessionLocal()
        query=text("""
        UPDATE propiedad
        SET estado= :estado
        WHERE propiedad_id= :propiedad_id
        """)
        db.execute(query, {"estado": estado, "propiedad_id": propiedad_id})
        db.commit()
    except Exception as e:
        raise e
    