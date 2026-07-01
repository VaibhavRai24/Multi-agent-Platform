from fastapi import APIRouter

from app.routers import auth, documents, chat, reports, users, health

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["User Profile"])
api_router.include_router(documents.router, prefix="/documents", tags=["Document Processing"])
api_router.include_router(chat.router, prefix="/chat", tags=["Multi-Agent Chat"])
api_router.include_router(reports.router, prefix="/reports", tags=["Report Generation & Download"])
