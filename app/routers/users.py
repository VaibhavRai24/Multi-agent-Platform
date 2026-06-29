from fastapi import APIRouter
from app.schemas.schemas import UserResponse
from datetime import datetime

router = APIRouter()

@router.get("/me", response_model=UserResponse)
def get_current_user_profile():
    # TODO: Implement dependency injection to get current requested user from token
    return {
        "id": 1,
        "email": "admin@example.com",
        "role": "admin",
        "is_active": True,
        "created_at": datetime.utcnow()
    }
