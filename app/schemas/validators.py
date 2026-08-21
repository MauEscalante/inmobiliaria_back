"""Validaciones reutilizables por los schemas.

Se usa un patrón de regex en vez de pydantic.EmailStr porque `email-validator`
no está instalado y agregarlo solo para esto rompería el entorno existente.
"""

# Suficiente para rechazar los errores de tipeo habituales sin pretender
# implementar RFC 5322.
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
