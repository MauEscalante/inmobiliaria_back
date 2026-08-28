-- =============================================================================
-- Inmobiliaria — datos de prueba
-- =============================================================================
-- Requiere haber corrido sql/01_schema.sql antes.
--
--   mysql -u root -p inmobiliaria_db < sql/02_seed.sql
--
-- El escenario está armado con agosto de 2026 como "mes actual", de modo que:
--   * GET /recibos/ajustar/8/2026 devuelve exactamente 3 contratos
--     ('000001', '000002', '000003').
--   * Hay un contrato ICL que la query de IPC debe descartar ('000005').
--   * Hay un contrato recién firmado que todavía no ajusta ('000006').
--   * La propiedad 3 tiene dos propietarios y dos co-inquilinos.
--   * La propiedad 7 no tiene contratos, así que se puede eliminar.
-- =============================================================================

USE inmobiliaria_db;

SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE libroDiario;
TRUNCATE TABLE valor_historico;
TRUNCATE TABLE garante;
TRUNCATE TABLE contrato_inquilino;
TRUNCATE TABLE contrato;
TRUNCATE TABLE propiedad_propietario;
TRUNCATE TABLE propiedad;
TRUNCATE TABLE cliente;
SET FOREIGN_KEY_CHECKS = 1;


-- -----------------------------------------------------------------------------
-- Clientes: 1-6 propietarios, 7-13 inquilinos
-- -----------------------------------------------------------------------------
INSERT INTO cliente
    (cliente_num, nombre, apellido, dni, telefono, email, direccion, cuil, nacionalidad, tipo)
VALUES
    ( 1, 'Juan',    'Perez',     '30111222', '1122334455', 'juan.perez@mail.com',      'Av. Colon 1200',   '20-30111222-5', 'Argentina', 'Propietario'),
    ( 2, 'Maria',   'Gomez',     '27888999', '1133445566', 'maria.gomez@mail.com',     'Alberdi 340',      '27-27888999-4', 'Argentina', 'Propietario'),
    ( 3, 'Carlos',  'Lopez',     '32555111', '1144556677', 'carlos.lopez@mail.com',    'Urquiza 880',      '20-32555111-3', 'Argentina', 'Propietario'),
    ( 4, 'Lucia',   'Fernandez', '33444555', '1155667788', 'lucia.fernandez@mail.com', 'Moreno 1420',      '27-33444555-1', 'Argentina', 'Propietario'),
    ( 5, 'Pedro',   'Martinez',  '28999111', '1166778899', 'pedro.martinez@mail.com',  'Las Heras 210',    '20-28999111-7', 'Argentina', 'Propietario'),
    ( 6, 'Ana',     'Suarez',    '35666777', '1177889900', 'ana.suarez@mail.com',      'Rioja 95',         '27-35666777-2', 'Argentina', 'Propietario'),

    ( 7, 'Diego',   'Romero',    '31222333', '1188990011', 'diego.romero@mail.com',    'Av. Mitre 100',    '20-31222333-9', 'Argentina', 'Inquilino'),
    ( 8, 'Sofia',   'Diaz',      '29888777', '1199001122', 'sofia.diaz@mail.com',      'Belgrano 250',     '27-29888777-6', 'Argentina', 'Inquilino'),
    ( 9, 'Martin',  'Castro',    '34111555', '1111223344', 'martin.castro@mail.com',   'Rivadavia 330',    '20-34111555-8', 'Argentina', 'Inquilino'),
    (10, 'Carla',   'Ruiz',      '36777888', '1122446688', 'carla.ruiz@mail.com',      'Rivadavia 330',    '27-36777888-0', 'Argentina', 'Inquilino'),
    (11, 'Nicolas', 'Alvarez',   '31888444', '1133557799', 'nicolas.alvarez@mail.com', 'Sarmiento 120',    '20-31888444-4', 'Argentina', 'Inquilino'),
    (12, 'Valeria', 'Molina',    '29999555', '1144668800', 'valeria.molina@mail.com',  'San Martin 450',   '27-29999555-3', 'Uruguaya',  'Inquilino'),
    (13, 'Tomas',   'Herrera',   '37222999', '1155779911', 'tomas.herrera@mail.com',   'Italia 890',       '20-37222999-1', 'Argentina', 'Inquilino');


-- -----------------------------------------------------------------------------
-- Propiedades
-- La 7 queda sin contrato a propósito, para poder probar el DELETE.
-- -----------------------------------------------------------------------------
INSERT INTO propiedad
    (propiedad_id, direccion, ambientes, estado, estado_alquiler)
VALUES
    (1, 'Av. Mitre 100',  3, 'Activa',   'Abono'),
    (2, 'Belgrano 250',   2, 'Activa',   'Abono'),
    (3, 'Rivadavia 330',  4, 'Activa',   'Adeuda'),
    (4, 'Sarmiento 120',  2, 'Activa',   'Abono'),
    (5, 'San Martin 450', 3, 'Activa',   'Adeuda'),
    (6, 'Italia 890',     5, 'Activa',   'Abono'),
    (7, 'Alsina 55',      1, 'Inactiva', 'Adeuda');


-- -----------------------------------------------------------------------------
-- Propietarios de cada propiedad
-- `comision` es del propietario: se repite igual en todas sus propiedades.
-- `porcentaje` reparte esa comisión y suma 100 por propiedad.
-- La propiedad 3 es la de reparto compartido (60/40).
-- -----------------------------------------------------------------------------
INSERT INTO propiedad_propietario
    (propiedad_id, cliente, porcentaje, comision)
VALUES
    (1, 1, 100.00, 6.00),
    (2, 2, 100.00, 5.00),
    (3, 3,  60.00, 6.00),
    (3, 4,  40.00, 6.00),
    (4, 4, 100.00, 6.00),
    (5, 5, 100.00, 7.00),
    (6, 6, 100.00, 6.00),
    (7, 6, 100.00, 6.00);


-- -----------------------------------------------------------------------------
-- Contratos
-- Escenario de ajustes tomando agosto de 2026 como mes de liquidación:
--
--   000001  IPC  Cuatrimestral  inicio 2026-04-01  ->  4 meses, ajusta AHORA
--   000002  IPC  Trimestral     inicio 2026-05-01  ->  3 meses, ajusta AHORA
--   000003  IPC  Cuatrimestral  inicio 2025-12-01  ->  8 meses, ajusta AHORA
--   000004  IPC  Cuatrimestral  inicio 2026-03-01  ->  5 meses, ya ajustó en julio
--   000005  ICL  Semestral      inicio 2026-02-01  ->  descartado por tipo_ajuste
--   000006  IPC  Cuatrimestral  inicio 2026-07-10  ->  contrato nuevo, no ajusta
--
-- El depósito se carga igual al importe inicial, que es lo que hace el
-- formulario de alta de contrato por defecto.
-- -----------------------------------------------------------------------------
INSERT INTO contrato
    (contrato_id, propiedad, fecha_inicio, fecha_fin, tipo_ajuste, periodicidad,
     importe_inicial, deposito, estado, garantia, direccion_garantia)
VALUES
    ('000001', 1, '2026-04-01', '2028-03-31', 'IPC', 'Cuatrimestral', 500000.00, 500000.00, 'Activo', 'GPremier',             NULL),
    ('000002', 2, '2026-05-01', '2028-04-30', 'IPC', 'Trimestral',    620000.00, 620000.00, 'Activo', 'Garantes',             NULL),
    ('000003', 3, '2025-12-01', '2027-11-30', 'IPC', 'Cuatrimestral', 710000.00, 710000.00, 'Activo', 'Garantia Propietaria', 'Moreno 1420'),
    ('000004', 4, '2026-03-01', '2028-02-28', 'IPC', 'Cuatrimestral', 580000.00, 580000.00, 'Activo', 'GPremier',             NULL),
    ('000005', 5, '2026-02-01', '2028-01-31', 'ICL', 'Semestral',     640000.00, 640000.00, 'Activo', 'Garantes',             NULL),
    ('000006', 6, '2026-07-10', '2028-07-09', 'IPC', 'Cuatrimestral', 760000.00, 760000.00, 'Activo', 'GPremier',             NULL);


-- -----------------------------------------------------------------------------
-- Inquilinos de cada contrato
-- El 000003 tiene dos co-inquilinos.
-- -----------------------------------------------------------------------------
INSERT INTO contrato_inquilino
    (contrato, cliente)
VALUES
    ('000001',  7),
    ('000002',  8),
    ('000003',  9),
    ('000003', 10),
    ('000004', 11),
    ('000005', 12),
    ('000006', 13);


-- -----------------------------------------------------------------------------
-- Garantes
-- Solo tienen filas los contratos con garantia 'Garantes' o
-- 'Garantia Propietaria'. Los de garantía propietaria van sin sueldo.
-- -----------------------------------------------------------------------------
INSERT INTO garante
    (contrato, nombre, apellido, telefono, dni, sueldo, email)
VALUES
    -- 000002: garantía por recibo de sueldo
    ('000002', 'Roberto', 'Sosa',    '1160001111', '25111333', 1450000.00, 'roberto.sosa@mail.com'),
    ('000002', 'Elena',   'Vega',    '1160002222', '26222444', 1280000.00, 'elena.vega@mail.com'),
    ('000002', 'Hugo',    'Ibarra',  '1160003333', '24333555', 1610000.00, 'hugo.ibarra@mail.com'),

    -- 000003: garantía propietaria (inmueble en Moreno 1420)
    ('000003', 'Lucia',   'Fernandez', '1155667788', '33444555', NULL, 'lucia.fernandez@mail.com'),
    ('000003', 'Ramon',   'Quiroga',   '1160004444', '22555777', NULL, NULL),

    -- 000005: garantía por recibo de sueldo
    ('000005', 'Silvia',  'Paz',     '1160005555', '30666888', 1320000.00, 'silvia.paz@mail.com'),
    ('000005', 'Andres',  'Miranda', '1160006666', '31777999', 1540000.00, 'andres.miranda@mail.com');


-- -----------------------------------------------------------------------------
-- Historial de importes
-- Una fila por período de vigencia entre ajustes. Los contratos que deben
-- ajustar ahora (000001, 000002, 000003) tienen su último período cerrado el
-- 31/07/2026 y todavía no tienen el período que arranca en agosto.
-- -----------------------------------------------------------------------------
INSERT INTO valor_historico
    (contrato, importe_inicial, fecha_inicio, fecha_fin)
VALUES
    ('000001', 500000.00, '2026-04-01', '2026-07-31'),

    ('000002', 620000.00, '2026-05-01', '2026-07-31'),

    ('000003', 710000.00, '2025-12-01', '2026-03-31'),
    ('000003', 781000.00, '2026-04-01', '2026-07-31'),

    -- ya ajustado en julio
    ('000004', 580000.00, '2026-03-01', '2026-06-30'),
    ('000004', 638000.00, '2026-07-01', '2026-10-31'),

    -- ya ajustado en agosto (semestral)
    ('000005', 640000.00, '2026-02-01', '2026-07-31'),
    ('000005', 742400.00, '2026-08-01', '2027-01-31'),

    -- contrato nuevo, primer período
    ('000006', 760000.00, '2026-07-10', '2026-11-09');


-- -----------------------------------------------------------------------------
-- Libro diario: movimientos de junio a octubre de 2026
-- -----------------------------------------------------------------------------
INSERT INTO libroDiario
    (fecha, concepto, monto, tipo)
VALUES
    -- Junio 2026
    ('2026-06-02', 'Comisión alquiler - Av. Mitre 100',  85000.00,  'INGRESO'),
    ('2026-06-05', 'Comisión alquiler - Belgrano 250',   65000.00,  'INGRESO'),
    ('2026-06-10', 'Monotributo',                        180000.00, 'EGRESO'),
    ('2026-06-15', 'Luz oficina',                        35000.00,  'EGRESO'),
    ('2026-06-20', 'Comisión alquiler - Rivadavia 330',  95000.00,  'INGRESO'),

    -- Julio 2026
    ('2026-07-01', 'Comisión alquiler - Av. Mitre 100',  85000.00,  'INGRESO'),
    ('2026-07-04', 'Comisión alquiler - Belgrano 250',   70000.00,  'INGRESO'),
    ('2026-07-08', 'Monotributo',                        180000.00, 'EGRESO'),
    ('2026-07-12', 'Internet oficina',                   28000.00,  'EGRESO'),
    ('2026-07-18', 'Comisión alquiler - Rivadavia 330',  100000.00, 'INGRESO'),
    ('2026-07-25', 'Compra artículos de oficina',        45000.00,  'EGRESO'),

    -- Agosto 2026
    ('2026-08-03', 'Comisión alquiler - Av. Mitre 100',  90000.00,  'INGRESO'),
    ('2026-08-07', 'Comisión alquiler - Belgrano 250',   75000.00,  'INGRESO'),
    ('2026-08-10', 'Comisión alquiler - Sarmiento 120',  30000.00,  'INGRESO'),
    ('2026-08-11', 'Monotributo',                        180000.00, 'EGRESO'),
    ('2026-08-15', 'Comisión alquiler - Rivadavia 330',  105000.00, 'INGRESO'),
    ('2026-08-20', 'Luz oficina',                        40000.00,  'EGRESO'),
    ('2026-08-25', 'Mantenimiento oficina',              55000.00,  'EGRESO'),

    -- Septiembre 2026
    ('2026-09-02', 'Comisión alquiler - Av. Mitre 100',  90000.00,  'INGRESO'),
    ('2026-09-05', 'Comisión alquiler - Belgrano 250',   75000.00,  'INGRESO'),
    ('2026-09-10', 'Monotributo',                        185000.00, 'EGRESO'),
    ('2026-09-14', 'Internet oficina',                   30000.00,  'EGRESO'),
    ('2026-09-20', 'Comisión alquiler - Rivadavia 330',  105000.00, 'INGRESO'),
    ('2026-09-28', 'Publicidad',                         60000.00,  'EGRESO'),

    -- Octubre 2026
    ('2026-10-01', 'Comisión alquiler - Av. Mitre 100',  95000.00,  'INGRESO'),
    ('2026-10-06', 'Comisión alquiler - Belgrano 250',   80000.00,  'INGRESO'),
    ('2026-10-10', 'Monotributo',                        185000.00, 'EGRESO'),
    ('2026-10-15', 'Comisión alquiler - Rivadavia 330',  110000.00, 'INGRESO'),
    ('2026-10-20', 'Luz oficina',                        42000.00,  'EGRESO'),
    ('2026-10-25', 'Compra artículos de oficina',        35000.00,  'EGRESO');
