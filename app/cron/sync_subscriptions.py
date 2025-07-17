# cron/sync_subscriptions.py

import asyncio
from fastapi import Request
from sqlalchemy.orm import Session
from starlette.datastructures import Headers
from app.core.database import SessionLocal
from app.services.billing_service import BillingService
from app.core.service_factory import ServiceFactory

class FakeRequest(Request):
    """Mock de Request para inicializar ServiceFactory sin un servidor HTTP."""
    def __init__(self):
        scope = {"type": "http", "headers": []}
        super().__init__(scope)

async def main():
    db: Session = SessionLocal()
    try:
        request = FakeRequest()
        factory = ServiceFactory(db=db, request=request)
        billing_service = factory.get_billing_service()

        billing_service.sync_subscriptions_from_stripe()
        print("✅ Sincronización de suscripciones completada.")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
