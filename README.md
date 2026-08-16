PARA CREAR LA DB:
DROP DATABASE inmobiliaria_db;

CREATE DATABASE inmobiliaria_db;

USE inmobiliaria_db;


CREATE TABLE  propiedad  (
   propiedad_id  int NOT NULL AUTO_increment,
   direccion  varchar(25) NOT NULL,
   ambientes int ,
  PRIMARY KEY ( propiedad_id )
);

create table libroDiario(
	movimiento_id INT NOT NULL AUTO_INCREMENT,
    fecha DATE NOT NULL,
    concepto VARCHAR(150) NOT NULL,
    monto DECIMAL(12,2) NOT NULL,
    tipo ENUM('INGRESO', 'EGRESO') NOT NULL,

    PRIMARY KEY (movimiento_id)
    
);

CREATE TABLE cliente (
  cliente_num int NOT NULL AUTO_INCREMENT,
   nombre  varchar(15) NOT NULL,
   apellido  varchar(15) NOT NULL,
   dni  varchar(9) NOT NULL,
   telefono  varchar(10) NOT NULL,
  PRIMARY KEY ( cliente_num )
);
ALTER TABLE propiedad
ADD COLUMN estado varchar(8);

CREATE TABLE  contrato  (
   contrato_id  varchar(10) NOT NULL ,
   propiedad  int DEFAULT NULL,
   fecha_inicio  date DEFAULT NULL,
   fecha_fin  date DEFAULT NULL,
   tipo_ajuste  varchar(3) DEFAULT NULL, #deberia ser un enum con IPC ICL
   periodicidad  int DEFAULT NULL,
   importe_inicial  decimal(12,2) NOT NULL,
  PRIMARY KEY ( contrato_id ),
  KEY  propiedad  ( propiedad ),
  CONSTRAINT  contrato_ibfk_1  FOREIGN KEY ( propiedad ) REFERENCES  propiedad  ( propiedad_id )
);

CREATE TABLE valor_historico(
	contrato varchar(10) NOT NULL,
    importe_inicial  decimal(12,2) NOT NULL,
    fecha_inicio date not null,
    fecha_fin date not null,
    PRIMARY KEY (contrato,fecha_inicio),
    foreign key (contrato) REFERENCES contrato(contrato_id)
);

CREATE TABLE  contrato_inquilino  (
   contrato  varchar(10) NOT NULL,
   cliente  int NOT NULL,
  PRIMARY KEY ( contrato , cliente ),
  KEY  fk_contrato_inquilino_cliente  ( cliente ),
  CONSTRAINT  contrato_inquilino_ibfk_1  FOREIGN KEY ( contrato ) REFERENCES  contrato  ( contrato_id ),
  CONSTRAINT  fk_contrato_inquilino_cliente  FOREIGN KEY ( cliente ) REFERENCES  cliente  ( cliente_num )
) ;

CREATE TABLE  propiedad_propietario  (
   propiedad_id  int NOT NULL AUTO_INCREMENT,
   cliente  int NOT NULL,
   porcentaje  decimal(5,2) NOT NULL,
   comision  int NOT NULL,
  PRIMARY KEY ( propiedad_id , cliente ),
  KEY  fk_propiedad_propietario_cliente  ( cliente ),
  CONSTRAINT  fk_propiedad_propietario_cliente  FOREIGN KEY ( cliente ) REFERENCES  cliente  ( cliente_num ),
  CONSTRAINT  propiedad_propietario_ibfk_2  FOREIGN KEY ( propiedad_id ) REFERENCES  propiedad  ( propiedad_id )
); 


INSERT DE PRUEBA 


INSERT INTO cliente (nombre, apellido, dni, telefono) VALUES
('Juan','Perez','30111222','1122334455'),
('Maria','Gomez','27888999','1133445566'),
('Carlos','Lopez','32555111','1144556677'),
('Lucia','Fernandez','33444555','1155667788'),
('Pedro','Martinez','28999111','1166778899'),
('Ana','Suarez','35666777','1177889900'),
('Diego','Romero','31222333','1188990011'),
('Sofia','Diaz','29888777','1199001122'),
('Martin','Castro','34111555','1111223344'),
('Carla','Ruiz','36777888','1122446688'),
('Nicolas','Alvarez','31888444','1133557799'),
('Valeria','Molina','29999555','1144668800');

INSERT INTO propiedad (direccion) VALUES
('Av. Mitre 100'),
('Belgrano 250'),
('Rivadavia 330'),
('Sarmiento 120'),
('San Martin 450'),
('Italia 890');

INSERT INTO propiedad_propietario
(propiedad_id, cliente, porcentaje, comision)
VALUES
(1,1,100,6),
(2,2,100,6),
(3,3,100,6),
(4,4,100,6),
(5,5,100,6),
(6,6,100,6);

INSERT INTO contrato
(contrato_id, propiedad, fecha_inicio, fecha_fin, tipo_ajuste, periodicidad, importe_inicial)
VALUES

-- Deben actualizarse AHORA (agosto 2026)
('000001',1,'2026-04-01','2028-03-31','IPC',4,500000),
('000002',2,'2026-04-15','2028-04-14','IPC',4,620000),
('000003',3,'2026-04-25','2028-04-24','IPC',4,710000),

-- Ya tuvieron ajuste el mes pasado (julio)
('000004',4,'2026-03-01','2028-02-28','IPC',4,580000),
('000005',5,'2026-03-15','2028-03-14','IPC',4,640000),

-- Contrato nuevo (todavía no ajusta)
('000006',6,'2026-07-10','2028-07-09','IPC',4,760000);

INSERT INTO contrato_inquilino
(contrato, cliente)
VALUES
('000001',7),
('000002',8),
('000003',9),
('000004',10),
('000005',11),
('000006',12);

INSERT INTO valor_historico
(contrato, importe_inicial, fecha_inicio, fecha_fin)
VALUES

-- ===============================
-- YA SE AJUSTARON EN JULIO
-- (vigencia julio-octubre)
-- ===============================


('000004',450000.00,'2026-08-01','2026-10-30'),

-- ===============================
-- DEBEN AJUSTARSE AHORA
-- (vigencia mayo-agosto)

-- ===============================

('000001',500000.00,'2026-05-01','2026-08-31'),
('000002',620000.00,'2026-05-01','2026-08-31'),
('000003',710000.00,'2026-05-01','2026-08-31'),


-- ===============================
-- YA SE AJUSTARON EN JUNIO
-- (vigencia junio-septiembre)
-- ===============================

('000005',560000.00,'2026-02-01','2026-05-31'),
('000005',590000.00,'2026-06-01','2026-09-30'),

-- ===============================
-- CONTRATO NUEVO
-- Primer ajuste en diciembre
-- ===============================

('000006',760000.00,'2026-08-01','2026-11-30');



INSERT INTO libroDiario (fecha, concepto, monto, tipo)
VALUES
-- Junio 2026
('2026-06-02', 'Comisión alquiler - Propiedad 101', 85000, 'INGRESO'),
('2026-06-05', 'Comisión alquiler - Propiedad 205', 65000, 'INGRESO'),
('2026-06-10', 'Monotributo', 180000, 'EGRESO'),
('2026-06-15', 'Luz oficina', 35000, 'EGRESO'),
('2026-06-20', 'Comisión alquiler - Propiedad 310', 95000, 'INGRESO'),

-- Julio 2026
('2026-07-01', 'Comisión alquiler - Propiedad 101', 85000, 'INGRESO'),
('2026-07-04', 'Comisión alquiler - Propiedad 205', 70000, 'INGRESO'),
('2026-07-08', 'Monotributo', 180000, 'EGRESO'),
('2026-07-12', 'Internet oficina', 28000, 'EGRESO'),
('2026-07-18', 'Comisión alquiler - Propiedad 310', 100000, 'INGRESO'),
('2026-07-25', 'Compra artículos de oficina', 45000, 'EGRESO'),

-- Agosto 2026
('2026-08-03', 'Comisión alquiler - Propiedad 101', 90000, 'INGRESO'),
('2026-08-07', 'Comisión alquiler - Propiedad 205', 75000, 'INGRESO'),
('2026-08-10', 'Cotagaita 786', 30000, 'INGRESO'),
('2026-08-11', 'Monotributo', 180000, 'EGRESO'),
('2026-08-15', 'Comisión alquiler - Propiedad 310', 105000, 'INGRESO'),
('2026-08-20', 'Luz oficina', 40000, 'EGRESO'),
('2026-08-25', 'Mantenimiento oficina', 55000, 'EGRESO'),

-- Septiembre 2026
('2026-09-02', 'Comisión alquiler - Propiedad 101', 90000, 'INGRESO'),
('2026-09-05', 'Comisión alquiler - Propiedad 205', 75000, 'INGRESO'),
('2026-09-10', 'Monotributo', 185000, 'EGRESO'),
('2026-09-14', 'Internet oficina', 30000, 'EGRESO'),
('2026-09-20', 'Comisión alquiler - Propiedad 310', 105000, 'INGRESO'),
('2026-09-28', 'Publicidad', 60000, 'EGRESO'),

-- Octubre 2026
('2026-10-01', 'Comisión alquiler - Propiedad 101', 95000, 'INGRESO'),
('2026-10-06', 'Comisión alquiler - Propiedad 205', 80000, 'INGRESO'),
('2026-10-10', 'Monotributo', 185000, 'EGRESO'),
('2026-10-15', 'Comisión alquiler - Propiedad 310', 110000, 'INGRESO'),
('2026-10-20', 'Luz oficina', 42000, 'EGRESO'),
('2026-10-25', 'Compra artículos de oficina', 35000, 'EGRESO');

use inmobiliaria_db;
drop table IPC
