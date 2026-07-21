from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.groups import router as group_router
from app.api.v1.endpoints.expenses import router as expense_router
from app.api.v1.endpoints.balances import router as balance_router
from app.api.v1.endpoints.notifications import router as notification_router
from app.api.v1.endpoints.analytics import router as analytics_router
from app.api.v1.endpoints.email_redirects import router as redirect_router

api_router = APIRouter()

api_router.include_router(auth_router, tags=["Auth & Users"])
api_router.include_router(group_router)
api_router.include_router(expense_router)
api_router.include_router(balance_router)
api_router.include_router(notification_router)
api_router.include_router(analytics_router)
api_router.include_router(redirect_router)
