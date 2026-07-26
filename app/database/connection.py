import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:Escalante1218@localhost/inmobiliaria_db"
)

engine = create_engine(
    DATABASE_URL,
    echo=True,          # Muestra el SQL en consola (útil en desarrollo)
    pool_pre_ping=True  # Verifica que la conexión siga viva
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

Base = declarative_base()