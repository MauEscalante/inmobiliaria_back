# Inmobiliaria — Backend

API de administración de alquileres. FastAPI + SQLAlchemy sobre MySQL.

## Base de datos

El esquema vive en `sql/`. **Es la única fuente de verdad**: si cambiás un modelo
en `app/models/`, actualizá también el DDL.

```
sql/01_schema.sql   estructura (borra y recrea inmobiliaria_db)
sql/02_seed.sql     datos de prueba
```

### Crear la base desde cero

```bash
mysql -u root -p < sql/01_schema.sql
mysql -u root -p inmobiliaria_db < sql/02_seed.sql
```

`01_schema.sql` arranca con `DROP DATABASE IF EXISTS inmobiliaria_db`, así que
borra todo lo que haya. `02_seed.sql` trunca las tablas antes de insertar, por
lo que se puede volver a correr solo para dejar los datos de prueba como estaban.

### Tablas

| Tabla | Para qué |
|---|---|
| `cliente` | Propietarios e inquilinos, discriminados por `tipo`. Los garantes no van acá. |
| `propiedad` | Inmuebles administrados, con estado y semáforo de cobranza. |
| `propiedad_propietario` | N:N propiedad ↔ propietarios, con `comision` y `porcentaje` de reparto. |
| `contrato` | Contrato de alquiler: vigencia, importe, tipo de ajuste, periodicidad y garantía. |
| `contrato_inquilino` | N:N contrato ↔ inquilinos (admite co-inquilinos). |
| `garante` | Garantes del contrato. El tipo lo determina `contrato.garantia`. |
| `valor_historico` | Historial de importes: una fila por período entre ajustes. |
| `libroDiario` | Ingresos y egresos de la inmobiliaria. |

Las tablas `valor_historico` y `libroDiario` todavía no tienen modelo en
`app/models/`; se consultan por SQL crudo.

### Verificar que el DDL y los modelos coincidan

```bash
python -c "
from app.database.base import Base
from app.models.garante import Garante
from app.database.connection import engine
from sqlalchemy import inspect
insp = inspect(engine)
for t in Base.metadata.sorted_tables:
    faltan = {c.name for c in t.columns} - {c['name'] for c in insp.get_columns(t.name)}
    print(t.name, 'OK' if not faltan else f'FALTAN: {faltan}')
"
```

### Datos de prueba

El seed usa **agosto de 2026** como mes de referencia:

- `GET /recibos/ajustar/8/2026` devuelve 3 contratos (`000001`, `000002`, `000003`).
- `000005` es ICL, así que la query de IPC lo descarta.
- `000006` es un contrato nuevo que todavía no ajusta.
- La propiedad 3 tiene dos propietarios (60/40) y dos co-inquilinos.
- La propiedad 7 no tiene contratos, sirve para probar el `DELETE`.

## Configuración

La conexión sale de `DATABASE_URL` en `.env`:

```
DATABASE_URL=mysql+pymysql://usuario:password@localhost/inmobiliaria_db
```

## Correr la API

```bash
uvicorn main:app --reload
```

Queda en `http://127.0.0.1:8000`, que es adonde apunta el front. Documentación
interactiva en `/docs`.
