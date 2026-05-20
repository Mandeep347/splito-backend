from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.groups import router as group_router
from app.api.v1.endpoints.expenses import router as expense_router
from app.api.v1.endpoints.balances import router as balance_router

api_router = APIRouter()

api_router.include_router(auth_router, tags=["Auth & Users"])
api_router.include_router(group_router)
api_router.include_router(expense_router)
api_router.include_router(balance_router)
