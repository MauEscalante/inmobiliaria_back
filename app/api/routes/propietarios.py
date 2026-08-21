from fastapi import APIRouter
from app.api.controllers.propietarios_controller import get_all_propietarios


router = APIRouter(prefix="/propietarios", tags=["propietarios"])


@router.get("/")
async def get_propietarios():
    return get_all_propietarios()
