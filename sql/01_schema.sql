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
    estado             ENUM('Activo', 'Inactivo', 'Rescindido') NOT NULL DEFAULT 'Activo',
    garantia           ENUM('GPremier', 'Garantia Propietaria', 'Garantes')
                       NOT NULL DEFAULT 'GPremier',
    direccion_garantia VARCHAR(255)  NULL,
    -- Rescisión en dos pasos. Al registrarse el aviso solo se carga
    -- `fecha_rescision` (cierre del mes de salida) y el contrato sigue Activo:
    -- ese mes lo paga, así que todavía liquida y ajusta. Al entregarse las
    -- llaves pasa a Rescindido con la penalidad ya calculada sobre el alquiler
    -- real del mes. `fecha_fin` conserva el plazo pactado para poder auditarlo.
    fecha_rescision      DATE          NULL,
    fecha_entrega_llaves DATE          NULL,
    penalidad            DECIMAL(12,2) NULL,

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
--
-- `propiedad_id`, `piso` y `depto` son del movimiento, no de la propiedad:
-- aclaran a qué unidad corresponde el pago. Solo los ingresos y depósitos
-- apuntan a una propiedad. `concepto` va desnormalizado ("Cotagaita 786 3° B")
-- para que la fila siga siendo legible aunque la propiedad cambie de dirección.
-- `cuenta` indica a qué cuenta se transfirió: es obligatoria en los DEPOSITO.
-- -----------------------------------------------------------------------------
CREATE TABLE libroDiario (
    movimiento_id INT           NOT NULL AUTO_INCREMENT,
    fecha         DATE          NOT NULL,
    propiedad_id  INT           NULL,
    piso          VARCHAR(10)   NULL,
    depto         VARCHAR(10)   NULL,
    concepto      VARCHAR(150)  NOT NULL,
    monto         DECIMAL(12,2) NOT NULL,
    tipo          ENUM('INGRESO', 'DEPOSITO', 'EGRESO', 'RETIRO') NOT NULL,
    cuenta        ENUM('Kike', 'Dai') NULL,

    PRIMARY KEY (movimiento_id),
    KEY idx_librodiario_fecha (fecha),
    CONSTRAINT fk_librodiario_propiedad
        FOREIGN KEY (propiedad_id) REFERENCES propiedad (propiedad_id)
) ENGINE=InnoDB;


-- -----------------------------------------------------------------------------
-- evento
-- -----------------------------------------------------------------------------
-- Bitácora de altas, para el panel de actividad reciente. Ni `contrato` ni
-- `cliente` guardan fecha de creación, así que sin esta tabla solo se sabe en
-- qué orden se cargaron las cosas, nunca cuándo. Cada fila se escribe en la
-- misma transacción que el alta que la origina (evento_service.registrar).
--
-- `tipo` es VARCHAR y no ENUM a propósito: sumar un tipo de evento no debe
-- requerir un ALTER TABLE. `entidad_tipo`/`entidad_id` apuntan al recurso sin
-- FK, para que el evento sobreviva al borrado de la entidad.
-- -----------------------------------------------------------------------------
CREATE TABLE evento (
    evento_id   INT          NOT NULL AUTO_INCREMENT,
    tipo        VARCHAR(30)  NOT NULL,
    descripcion VARCHAR(255) NOT NULL,
    entidad_tipo VARCHAR(20) NULL,
    entidad_id   VARCHAR(20) NULL,
    creado_en   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (evento_id),
    KEY idx_evento_creado_en (creado_en)
) ENGINE=InnoDB;


-- -----------------------------------------------------------------------------
-- ajuste_recibo
-- -----------------------------------------------------------------------------
-- Trabajos de ajuste de recibos. Ajustar la planilla tarda más de un minuto, así
-- que el POST no lo resuelve dentro del request: encola el pedido y el cliente
-- consulta esta fila para saber cómo viene. Mientras haya uno en 'pendiente' o
-- 'en_proceso' no se acepta otro, porque la planilla es un archivo compartido y
-- dos ejecuciones simultáneas la corromperían.
-- -----------------------------------------------------------------------------
CREATE TABLE ajuste_recibo (
    ajuste_id                   INT      NOT NULL AUTO_INCREMENT,
    mes                         SMALLINT NOT NULL,
    anio                        SMALLINT NOT NULL,
    estado                      ENUM('pendiente', 'en_proceso', 'completado', 'fallido')
                                    NOT NULL DEFAULT 'pendiente',
    contratos_ajustados         INT      NULL,
    propiedades_marcadas_adeuda INT      NULL,
    error                       VARCHAR(500) NULL,
    creado_en                   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finalizado_en               DATETIME NULL,

    PRIMARY KEY (ajuste_id),
    KEY idx_ajuste_estado (estado)
) ENGINE=InnoDB;
