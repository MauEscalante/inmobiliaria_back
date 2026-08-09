from app.models.cliente import Cliente
from app.database.connection import SessionLocal
from sqlalchemy import text

def get_clientes() -> list:
    try:
        db= SessionLocal()
        cliente= db.query(Cliente).all()
        return cliente
    except Exception as e:
        raise e

def get_cliente_by_id(cliente_id: int) -> Cliente:
    try:
        db= SessionLocal()
        query= text("""SELECT * FROM cliente WHERE cliente_num = :cliente_id""")
        cliente= db.execute(query, {"cliente_id": cliente_id}).mappings().first()
        return dict(cliente) if cliente else None
    except Exception as e:
        raise e
    
def create_cliente(cliente_data: dict) -> Cliente:
    try:
        db= SessionLocal()
        nuevo_cliente= Cliente(**cliente_data)
        db.add(nuevo_cliente)
        db.commit()
        db.refresh(nuevo_cliente)
        return nuevo_cliente
    except Exception as e:
        raise e
    
def update_email(cliente_id: int, email: str) -> Cliente:
    try:
        db= SessionLocal()
        query=text("""
        UPDATE cliente
        SET email= :email
        WHERE id= :cliente_id
        """)
        db.execute(query, {"email": email, "cliente_id": cliente_id})
        db.commit()
    except Exception as e:
        raise e
    
def update_celular(cliente_id: int, telefono: str) -> Cliente:
    try:
        db= SessionLocal()
        query=text("""
        UPDATE cliente
        SET telefono= :telefono
        WHERE cliente_num= :cliente_id
        """)
        db.execute(query, {"telefono": telefono, "cliente_id": cliente_id})
        db.commit()
    except Exception as e:
        raise e