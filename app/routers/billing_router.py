# app/routers/billing_router.py

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
from app.core.service_factory import ServiceFactory
from app.schemas.billing_schema import BillingSessionCreate
from app.core.database import get_db
from sqlalchemy.orm import Session
import stripe
from app.core.config import settings

router = APIRouter(
    prefix="/billing",
    tags=["💳 Billing"],
    responses={404: {"description": "Not found"}},
)

def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db=db, request=request)

# 🚀 Iniciar sesión de pago en Stripe
@router.post("/checkout", summary="Start Stripe Checkout Session")
def start_checkout(
    data: BillingSessionCreate,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Crea una sesión de Stripe Checkout para iniciar una suscripción al plan seleccionado.
    Retorna una URL de redirección para el pago.
    """
    billing = factory.get_billing_service()
    url = billing.create_checkout_session(data)
    return {"checkout_url": url}

# 📬 Webhook para escuchar eventos de Stripe
@router.post("/webhook", summary="Listen to Stripe Events")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Endpoint para recibir eventos de Stripe como:
    - checkout.session.completed
    - invoice.paid
    - invoice.payment_failed
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # 🔌 Procesamos el evento a través del servicio
    factory = ServiceFactory(db=db, request=request)
    billing = factory.get_billing_service()
    billing.handle_webhook_event(event)

    return {"status": "success"}
