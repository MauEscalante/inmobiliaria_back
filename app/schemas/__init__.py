"""Schemas Pydantic: el contrato de entrada y salida de la API."""

from app.schemas.common import ErrorDetail, ErrorResponse, Page, error_responses

__all__ = ["ErrorDetail", "ErrorResponse", "Page", "error_responses"]
