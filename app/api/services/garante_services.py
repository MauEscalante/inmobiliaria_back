from app.models.garante import Garante


def crear_garante(db, garante_data: dict, contrato_id: str) -> Garante:
    """Crea una fila de garante asociada al contrato, dentro de la sesión/transacción activa.
    El tipo (Garantia Propietaria / Garantes) ya queda determinado por contrato.garantia."""
    garante = Garante(
        contrato_id=contrato_id,
        nombre=garante_data.get("nombre", ""),
        apellido=garante_data.get("apellido", ""),
        telefono=garante_data.get("telefono", ""),
        dni=garante_data.get("dni") or None,
        sueldo=garante_data.get("sueldo") or None,
        email=garante_data.get("email") or None,
    )
    db.add(garante)
    db.flush()
    return garante
