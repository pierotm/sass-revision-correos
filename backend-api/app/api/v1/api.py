from fastapi import APIRouter
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.companies import router as companies_router
from app.api.v1.endpoints.credentials import router as credentials_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(companies_router, prefix="/companies", tags=["companies"])
api_router.include_router(credentials_router, prefix="/companies", tags=["credentials"])
