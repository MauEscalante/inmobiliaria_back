-- =============================================================================
-- Inmobiliaria — migración de una base ya existente
-- =============================================================================
-- Pone al día una base creada con una versión anterior del esquema, sin borrar
-- datos. Es seguro correrlo siempre: cada paso se aplica solo si falta, así que
-- sirve tanto para una base vieja como para una a medio migrar o ya al día.
--
-- No hace falta si la base se recrea con sql/01_schema.sql: ahí ya está todo.
--
-- Uso:
--   mysql -u root -p inmobiliaria_db < sql/03_migracion.sql
--
-- Sobre las guardas: MySQL 8 no tiene ADD COLUMN IF NOT EXISTS (eso es MariaDB),
-- y DELIMITER es una directiva del cliente CLI que no funciona vía driver. Por
-- eso cada cambio no repetible se consulta contra information_schema y se
-- ejecuta con PREPARE/EXECUTE, que anda igual por CLI que desde Python.
-- =============================================================================

USE inmobiliaria_db;


-- -----------------------------------------------------------------------------
-- 1) Estado de la propiedad
-- -----------------------------------------------------------------------------
-- Normalizar antes de pasar la columna a NOT NULL. Repetirlo no cambia nada.
UPDATE propiedad
   SET estado = 'Activa'
 WHERE estado IS NULL OR estado NOT IN ('Activa', 'Inactiva');

-- MODIFY al mismo tipo es un no-op, no necesita guarda.
ALTER TABLE propiedad
  MODIFY COLUMN estado ENUM('Activa','Inactiva') NOT NULL DEFAULT 'Activa';

SET @sql := IF(
  (SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'propiedad' AND COLUMN_NAME = 'estado_alquiler') = 0,
  'ALTER TABLE propiedad ADD COLUMN estado_alquiler ENUM(''Abono'',''Adeuda'') NOT NULL DEFAULT ''Adeuda'' AFTER ambientes',
  'DO 0'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;


-- -----------------------------------------------------------------------------
-- 2) Libro diario: depósitos y retiros de caja, propiedad del movimiento y
--    cuenta destino
-- -----------------------------------------------------------------------------
-- Una guarda por columna y no un solo ALTER con todo: si la base quedó a mitad
-- de camino, así se completa lo que falte en vez de abortar en la primera que ya
-- estaba.
ALTER TABLE libroDiario
  MODIFY COLUMN tipo ENUM('INGRESO','DEPOSITO','EGRESO','RETIRO') NOT NULL;

SET @sql := IF(
  (SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'libroDiario' AND COLUMN_NAME = 'propiedad_id') = 0,
  'ALTER TABLE libroDiario ADD COLUMN propiedad_id INT NULL AFTER fecha',
  'DO 0'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := IF(
  (SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'libroDiario' AND COLUMN_NAME = 'piso') = 0,
  'ALTER TABLE libroDiario ADD COLUMN piso VARCHAR(10) NULL AFTER propiedad_id',
  'DO 0'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := IF(
  (SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'libroDiario' AND COLUMN_NAME = 'depto') = 0,
  'ALTER TABLE libroDiario ADD COLUMN depto VARCHAR(10) NULL AFTER piso',
  'DO 0'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := IF(
  (SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'libroDiario' AND COLUMN_NAME = 'cuenta') = 0,
  'ALTER TABLE libroDiario ADD COLUMN cuenta ENUM(''Kike'',''Dai'') NULL AFTER tipo',
  'DO 0'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := IF(
  (SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'libroDiario'
      AND CONSTRAINT_NAME = 'fk_librodiario_propiedad') = 0,
  'ALTER TABLE libroDiario ADD CONSTRAINT fk_librodiario_propiedad FOREIGN KEY (propiedad_id) REFERENCES propiedad (propiedad_id)',
  'DO 0'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := IF(
  (SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'libroDiario'
      AND INDEX_NAME = 'idx_librodiario_fecha') = 0,
  'CREATE INDEX idx_librodiario_fecha ON libroDiario (fecha)',
  'DO 0'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;


-- -----------------------------------------------------------------------------
-- 3) Bitácora de altas del panel de actividad reciente
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS evento (
    evento_id    INT          NOT NULL AUTO_INCREMENT,
    tipo         VARCHAR(30)  NOT NULL,
    descripcion  VARCHAR(255) NOT NULL,
    entidad_tipo VARCHAR(20)  NULL,
    entidad_id   VARCHAR(20)  NULL,
    creado_en    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (evento_id),
    KEY idx_evento_creado_en (creado_en)
) ENGINE=InnoDB;


-- -----------------------------------------------------------------------------
-- 4) Trabajos de ajuste de recibos
-- -----------------------------------------------------------------------------
-- Sin esta tabla la API ni siquiera arranca: el lifespan de main.py llama a
-- limpiar_interrumpidos(), que la actualiza.
CREATE TABLE IF NOT EXISTS ajuste_recibo (
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

-- -----------------------------------------------------------------------------
-- 5) Rescisión de contratos
-- -----------------------------------------------------------------------------
-- El aviso y el cierre son dos momentos distintos: entre uno y otro el contrato
-- sigue Activo con `fecha_rescision` cargada y `penalidad` en NULL, porque el
-- alquiler del mes de salida todavía no se conoce.
SET @sql := IF(
  (SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'contrato' AND COLUMN_NAME = 'fecha_rescision') = 0,
  'ALTER TABLE contrato ADD COLUMN fecha_rescision DATE NULL AFTER direccion_garantia',
  'DO 0'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := IF(
  (SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'contrato' AND COLUMN_NAME = 'fecha_entrega_llaves') = 0,
  'ALTER TABLE contrato ADD COLUMN fecha_entrega_llaves DATE NULL AFTER fecha_rescision',
  'DO 0'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := IF(
  (SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'contrato' AND COLUMN_NAME = 'penalidad') = 0,
  'ALTER TABLE contrato ADD COLUMN penalidad DECIMAL(12,2) NULL AFTER fecha_entrega_llaves',
  'DO 0'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- El estado suma 'Rescindido'. En las bases donde la columna quedó como VARCHAR
-- esto la normaliza al ENUM. Donde ya es ENUM, le agrega el valor que faltaba.
ALTER TABLE contrato
  MODIFY COLUMN estado ENUM('Activo','Inactivo','Rescindido') NOT NULL DEFAULT 'Activo';
