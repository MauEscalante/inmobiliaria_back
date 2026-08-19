from app.models.cliente import Cliente, ClienteTipo
from app.database.connection import SessionLocal
from sqlalchemy import text

def find_or_create_cliente(db, cliente_data: dict, tipo: ClienteTipo) -> Cliente:
    """Busca un cliente por DNI dentro de la sesión dada; si no existe, lo crea con el tipo indicado."""
    dni = (cliente_data.get("dni") or "").strip()

    cliente = None
    if dni:
        cliente = db.query(Cliente).filter(Cliente.dni == dni).first()

    if cliente:
        return cliente

    cliente = Cliente(
        nombre=cliente_data.get("nombre", ""),
        apellido=cliente_data.get("apellido", ""),
        dni=dni,
        telefono=cliente_data.get("telefono", ""),
        email=cliente_data.get("email") or None,
        direccion=cliente_data.get("direccion") or None,
        cuil=cliente_data.get("cuil") or None,
        nacionalidad=cliente_data.get("nacionalidad") or None,
        tipo=tipo,
    )
    db.add(cliente)
    db.flush()
    return cliente

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