-- =============================================================================
-- Inmobiliaria — esquema de base de datos
-- =============================================================================
-- Fuente de verdad del esquema. Está alineado con:
--   * los modelos SQLAlchemy de app/models/
--   * las queries SQL crudas de app/api/services/
--
-- Uso:
--   mysql -u root -p < sql/01_schema.sql
--   mysql -u root -p inmobiliaria_db < sql/02_seed.sql
--
-- ATENCIÓN: este script borra y recrea la base entera.
-- =============================================================================

DROP DATABASE IF EXISTS inmobiliaria_db;

CREATE DATABASE inmobiliaria_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE inmobiliaria_db;


-- -----------------------------------------------------------------------------
-- cliente
-- -----------------------------------------------------------------------------
-- Personas del sistema (propietarios e inquilinos), discriminadas por `tipo`.
-- Los garantes NO viven acá: tienen su propia tabla `garante`.
--
-- Nota: `dni` es UNIQUE porque find_or_create_cliente() (cliente_services.py)
-- lo usa como clave de deduplicación al dar de alta inquilinos desde un
-- contrato. Si el formulario llega sin DNI, ese servicio guarda cadena vacía;
-- el segundo caso así violará el UNIQUE. Es una limitación conocida del
-- backend, no del esquema.
-- -----------------------------------------------------------------------------
CREATE TABLE cliente (
    cliente_num  INT           NOT NULL AUTO_INCREMENT,
    nombre       VARCHAR(50)   NOT NULL,
    apellido     VARCHAR(50)   NOT NULL,
    dni          VARCHAR(15)   NOT NULL,
    telefono     VARCHAR(20)   NOT NULL,
    email        VARCHAR(100)  NULL,
    direccion    VARCHAR(255)  NULL,
    cuil         VARCHAR(20)   NULL,
    nacionalidad VARCHAR(50)   NULL,
    tipo         ENUM('Inquilino', 'Propietario') NULL,

    PRIMARY KEY (cliente_num),
    UNIQUE KEY uq_cliente_dni (dni),
    -- MySQL permite múltiples NULL bajo un índice UNIQUE, así que los clientes
    -- sin email conviven sin problema.
    UNIQUE KEY uq_cliente_email (email)
) ENGINE=InnoDB;


-- -----------------------------------------------------------------------------
-- propiedad
-- -----------------------------------------------------------------------------
-- `estado`          -> si la inmobiliaria administra hoy el inmueble.
-- `estado_alquiler` -> semáforo de cobranza del mes en curso.
-- -----------------------------------------------------------------------------
CREATE TABLE propiedad (
    propiedad_id    INT          NOT NULL AUTO_INCREMENT,
    direccion       VARCHAR(255) NOT NULL,
    ambientes       INT          NULL,
    estado          ENUM('Activa', 'Inactiva') NOT NULL DEFAULT 'Activa',
    estado_alquiler ENUM('Abono', 'Adeuda')    NOT NULL DEFAULT 'Adeuda',

    PRIMARY KEY (propiedad_id)
) ENGINE=InnoDB;


-- -----------------------------------------------------------------------------
-- propiedad_propietario
-- -----------------------------------------------------------------------------
-- Relación N:N entre propiedades y sus propietarios.
--
-- `comision`   -> comisión que cobra ese propietario. Es la misma en todas sus
--                 propiedades; por eso propiedades_services.py la lee con
--                 MAX(pp.comision) en lugar de guardarla en `propiedad`.
-- `porcentaje` -> qué parte de esa comisión le corresponde cuando el inmueble
--                 tiene más de un propietario. Debe sumar 100 por propiedad.
--
-- La columna se llama `cliente` (no `cliente_num`) porque así la mapea el
-- modelo y así la consultan las queries crudas.
-- -----------------------------------------------------------------------------
CREATE TABLE propiedad_propietario (
    propiedad_id INT           NOT NULL,
    cliente      INT           NOT NULL,
    porcentaje   DECIMAL(5,2)  NOT NULL,
    comision     DECIMAL(12,2) NULL,

    PRIMARY KEY (propiedad_id, cliente),
    KEY fk_propiedad_propietario_cliente (cliente),
    CONSTRAINT fk_propiedad_propietario_propiedad
        FOREIGN KEY (propiedad_id) REFERENCES propiedad (propiedad_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_propiedad_propietario_cliente
        FOREIGN KEY (cliente) REFERENCES cliente (cliente_num)
        ON DELETE RESTRICT
) ENGINE=InnoDB;


-- -----------------------------------------------------------------------------
-- contrato
-- -----------------------------------------------------------------------------
-- `contrato_id` es VARCHAR pero su contenido es numérico con ceros a la
-- izquierda ('000001'): contrato_services._generar_contrato_id() hace
-- MAX(CAST(contrato_id AS UNSIGNED)) + 1 y luego zfill(6).
--
-- `periodicidad` va como ENUM de texto, no como cantidad de meses: la query de
-- recibo_service.get_propiedades_ajustar() la traduce con
-- CASE periodicidad WHEN 'Trimestral' THEN 3 ... END
--
-- `garantia` determina de forma explícita si el contrato tiene filas en
-- `garante`: GPremier (seguro de caución) nunca las tiene; 'Garantia
-- Propietaria' y 'Garantes' sí. 'Garantia Propietaria' además usa
-- `direccion_garantia` para el inmueble ofrecido en garantía.
-- -----------------------------------------------------------------------------
CREATE TABLE contrato (
    contrato_id        VARCHAR(10)   NOT NULL,
    propiedad          INT           NOT NULL,
    fecha_inicio       DATE          NOT NULL,
    fecha_fin          DATE          NOT NULL,
    tipo_ajuste        ENUM('IPC', 'ICL') NULL,
    periodicidad       ENUM('Trimestral', 'Cuatrimestral', 'Semestral') NULL,
    importe_inicial    DECIMAL(12,2) NOT NULL,
    deposito           DECIMAL(12,2) NULL,
    estado             ENUM('Activo', 'Inactivo') NOT NULL DEFAULT 'Activo',
    garantia           ENUM('GPremier', 'Garantia Propietaria', 'Garantes')
                       NOT NULL DEFAULT 'GPremier',
    direccion_garantia VARCHAR(255)  NULL,

    PRIMARY KEY (contrato_id),
    KEY fk_contrato_propiedad (propiedad),
    CONSTRAINT fk_contrato_propiedad
        FOREIGN KEY (propiedad) REFERENCES propiedad (propiedad_id)
        ON DELETE RESTRICT,
    CONSTRAINT ck_contrato_vigencia CHECK (fecha_fin >= fecha_inicio)
) ENGINE=InnoDB;


-- -----------------------------------------------------------------------------
-- contrato_inquilino
-- -----------------------------------------------------------------------------
-- Un contrato puede tener varios co-inquilinos, y una persona puede firmar
-- varios contratos a lo largo del tiempo.
-- -----------------------------------------------------------------------------
CREATE TABLE contrato_inquilino (
    contrato VARCHAR(10) NOT NULL,
    cliente  INT         NOT NULL,

    PRIMARY KEY (contrato, cliente),
    KEY fk_contrato_inquilino_cliente (cliente),
    CONSTRAINT fk_contrato_inquilino_contrato
        FOREIGN KEY (contrato) REFERENCES contrato (contrato_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_contrato_inquilino_cliente
        FOREIGN KEY (cliente) REFERENCES cliente (cliente_num)
        ON DELETE RESTRICT
) ENGINE=InnoDB;


-- -----------------------------------------------------------------------------
-- garante
-- -----------------------------------------------------------------------------
-- Garantes del contrato. Son personas que NO se dan de alta como clientes, por
-- eso viven en tabla propia y no en `cliente`.
--
-- El tipo de garante no se guarda acá: ya lo determina contrato.garantia.
-- Los garantes propietarios se cargan sin `sueldo`; los garantes por recibo de
-- sueldo sí lo llevan.
-- -----------------------------------------------------------------------------
CREATE TABLE garante (
    garante_id INT           NOT NULL AUTO_INCREMENT,
    contrato   VARCHAR(10)   NOT NULL,
    nombre     VARCHAR(50)   NOT NULL,
    apellido   VARCHAR(50)   NOT NULL,
    telefono   VARCHAR(20)   NOT NULL,
    dni        VARCHAR(15)   NULL,
    sueldo     DECIMAL(12,2) NULL,
    email      VARCHAR(100)  NULL,

    PRIMARY KEY (garante_id),
    KEY fk_garante_contrato (contrato),
    CONSTRAINT fk_garante_contrato
        FOREIGN KEY (contrato) REFERENCES contrato (contrato_id)
        ON DELETE CASCADE
) ENGINE=InnoDB;


-- -----------------------------------------------------------------------------
-- valor_historico
-- -----------------------------------------------------------------------------
-- Historial de importes del contrato: una fila por período de vigencia entre
-- ajustes. Alimenta la pantalla de Ajustes y el cálculo de re-ajustes (el
-- re-ajuste debe tomar el valor guardado acá, no el ya redondeado del recibo).
-- -----------------------------------------------------------------------------
CREATE TABLE valor_historico (
    contrato        VARCHAR(10)   NOT NULL,
    importe_inicial DECIMAL(12,2) NOT NULL,
    fecha_inicio    DATE          NOT NULL,
    fecha_fin       DATE          NOT NULL,

    PRIMARY KEY (contrato, fecha_inicio),
    CONSTRAINT fk_valor_historico_contrato
        FOREIGN KEY (contrato) REFERENCES contrato (contrato_id)
        ON DELETE CASCADE,
    CONSTRAINT ck_valor_historico_vigencia CHECK (fecha_fin >= fecha_inicio)
) ENGINE=InnoDB;


-- -----------------------------------------------------------------------------
-- libroDiario
-- -----------------------------------------------------------------------------
-- Ingresos y egresos de la inmobiliaria. Es lo que consumen la vista de Recibos
-- (historial mensual de ingresos por comisiones) y las métricas de resumen.
--
-- El nombre va en camelCase a propósito: el front pega a GET /libroDiario/.
-- En Windows MySQL normaliza el nombre a minúsculas (lower_case_table_names=1)
-- y lo resuelve sin distinguir mayúsculas, así que las queries funcionan igual.
-- -----------------------------------------------------------------------------
CREATE TABLE libroDiario (
    movimiento_id INT           NOT NULL AUTO_INCREMENT,
    fecha         DATE          NOT NULL,
    concepto      VARCHAR(150)  NOT NULL,
    monto         DECIMAL(12,2) NOT NULL,
    tipo          ENUM('INGRESO', 'EGRESO') NOT NULL,

    PRIMARY KEY (movimiento_id),
    KEY idx_librodiario_fecha (fecha)
) ENGINE=InnoDB;
