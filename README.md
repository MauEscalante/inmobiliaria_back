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
| `libroDiario` | Ingresos, egresos, depósitos y retiros de la inmobiliaria. |
| `evento` | Bitácora de altas para el panel de actividad reciente. |
| `ajuste_recibo` | Trabajos de ajuste de recibos: estado y resultado de cada corrida. |

Varias de estas tablas se consultan por SQL crudo desde `app/api/services/`
aunque tengan modelo en `app/models/`.

### Verificar que el DDL y los modelos coincidan

El `import app.models` es lo que registra los modelos en el metadata: si se
importa solo alguno, las tablas que falten no se chequean y el drift pasa
desapercibido.

```bash
python -c "
from sqlalchemy import inspect
from app.database.connection import Base, engine
import app.models
insp = inspect(engine)
vivas = {t.lower() for t in insp.get_table_names()}
for t in Base.metadata.sorted_tables:
    if t.name.lower() not in vivas:
        print(t.name, 'AUSENTE en la base')
        continue
    reales = {c['name'] for c in insp.get_columns(t.name)}
    faltan = {c.name for c in t.columns} - reales
    sobran = reales - {c.name for c in t.columns}
    detalle = 'faltan=%s sobran=%s' % (sorted(faltan), sorted(sobran))
    print(t.name, 'OK' if not (faltan or sobran) else detalle)
"
```

Si aparece algo `AUSENTE`, la base viene de una versión anterior: correr
`sql/03_migracion.sql` (ver más abajo).

### Migrar una base ya existente

Si la base viene de una versión anterior y no se puede recrear, `sql/03_migracion.sql`
la pone al día sin borrar datos: estado de alquiler, columnas nuevas de
`libroDiario`, `evento` y `ajuste_recibo`. No hace falta si se corre `01_schema.sql`.

Cada paso se aplica solo si falta, así que es seguro correrlo siempre: sobre una
base ya migrada no hace nada, y una que quedó a mitad de camino se completa.

```bash
mysql -u root -p inmobiliaria_db < sql/03_migracion.sql
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
