from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.hr import router as hr_router
from app.api.v1.workflow import router as workflow_router
from app.api.v1.leave import router as leave_router
from app.api.v1.overtime import router as overtime_router
from app.api.v1.travel import router as travel_router
from app.api.v1.payment import router as payment_router
from app.api.v1.seal_contract import router as seal_contract_router
from app.api.v1.attendance import router as attendance_router

api_v1_router = APIRouter()
api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(hr_router)
api_v1_router.include_router(workflow_router)
api_v1_router.include_router(leave_router)
api_v1_router.include_router(overtime_router)
api_v1_router.include_router(travel_router)
api_v1_router.include_router(payment_router)
api_v1_router.include_router(seal_contract_router)
api_v1_router.include_router(attendance_router)
