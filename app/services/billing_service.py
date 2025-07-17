# app/services/billing_service.py

import stripe
import logging
from fastapi import HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.config import settings
from app.models.plan_model import Plan
from app.models.subscription_model import Subscription
from app.schemas.billing_schema import BillingSessionCreate

logger = logging.getLogger(__name__)

class BillingService:
    def __init__(self, factory):
        self.db: Session = factory.db
        self.user = factory.user
        stripe.api_key = settings.STRIPE_SECRET_KEY
        logger.info(f"💳 BillingService inicializado para usuario {self.user.email}")

    def create_checkout_session(self, session_data: BillingSessionCreate):
        logger.info("🧾 Creando sesión de pago Stripe...")

        plan = self.db.query(Plan).filter_by(id=session_data.plan_id, is_active=True).first()
        if not plan:
            logger.warning(f"❌ Plan ID {session_data.plan_id} no encontrado o inactivo")
            raise HTTPException(status_code=404, detail="Plan not found")

        try:
            session = stripe.checkout.Session.create(
                customer_email=self.user.email,
                payment_method_types=["card"],
                line_items=[{
                    "price": plan.stripe_price_id,
                    "quantity": 1,
                }],
                mode="subscription",
                success_url=session_data.success_url,
                cancel_url=session_data.cancel_url,
                metadata={"user_id": self.user.id, "plan_id": plan.id}
            )
            logger.info(f"✅ Sesión Stripe creada: {session.id}")
            return session.url
        except Exception as e:
            logger.error(f"❌ Error creando sesión Stripe: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    def handle_checkout_completed(self, session):
        user_id = int(session["metadata"]["user_id"])
        plan_id = int(session["metadata"]["plan_id"])
        stripe_subscription_id = session["subscription"]

        logger.info(f"🎉 Activando suscripción para user_id={user_id}, plan_id={plan_id}")

        subscription = Subscription(
            user_id=user_id,
            plan_id=plan_id,
            stripe_subscription_id=stripe_subscription_id,
            status="active",
            started_at=datetime.utcnow(),
        )
        self.db.add(subscription)
        self.db.commit()
        logger.info(f"✅ Suscripción guardada en DB para usuario {user_id}")

    def cancel_subscription(self):
        logger.info(f"🛑 Cancelando suscripción de usuario {self.user.id}")
        sub = self.db.query(Subscription).filter_by(user_id=self.user.id, status="active").first()
        if not sub:
            logger.warning("⚠️ No se encontró suscripción activa")
            raise HTTPException(status_code=404, detail="No active subscription found")

        try:
            stripe.Subscription.delete(sub.stripe_subscription_id)
            sub.status = "cancelled"
            sub.ended_at = datetime.utcnow()
            self.db.commit()
            logger.info(f"✅ Suscripción cancelada en Stripe y en la base de datos")
        except Exception as e:
            logger.error(f"❌ Error cancelando suscripción: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    def change_plan(self, new_plan_id: int):
        logger.info(f"🔁 Cambiando plan para user {self.user.id} a plan {new_plan_id}")
        sub = self.db.query(Subscription).filter_by(user_id=self.user.id, status="active").first()
        new_plan = self.db.query(Plan).filter_by(id=new_plan_id, is_active=True).first()

        if not sub or not new_plan:
            logger.warning("⚠️ Suscripción o nuevo plan no encontrado")
            raise HTTPException(status_code=404, detail="Subscription or plan not found")

        try:
            stripe.Subscription.modify(
                sub.stripe_subscription_id,
                items=[{
                    'id': stripe.Subscription.retrieve(sub.stripe_subscription_id)['items']['data'][0]['id'],
                    'price': new_plan.stripe_price_id,
                }],
                proration_behavior='create_prorations'
            )

            sub.plan_id = new_plan.id
            self.db.commit()
            logger.info("✅ Plan cambiado correctamente")
        except Exception as e:
            logger.error(f"❌ Error cambiando plan: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    def sync_subscriptions_from_stripe(self):
        """
        Cronjob recomendado: sincroniza el estado real de las suscripciones desde Stripe.
        """
        logger.info("🔄 Sincronizando suscripciones desde Stripe...")

        subs = self.db.query(Subscription).all()
        for sub in subs:
            try:
                stripe_sub = stripe.Subscription.retrieve(sub.stripe_subscription_id)
                old_status = sub.status
                sub.status = stripe_sub.status
                if stripe_sub.status == "canceled" and not sub.ended_at:
                    sub.ended_at = datetime.utcnow()
                if old_status != sub.status:
                    logger.info(f"🔁 Suscripción {sub.id} cambió de {old_status} a {sub.status}")
            except Exception as e:
                logger.warning(f"⚠️ No se pudo sincronizar suscripción {sub.id}: {e}")

        self.db.commit()
        logger.info("✅ Sincronización completa")

    def handle_webhook_event(self, event: dict):
        event_type = event["type"]
        logger.info(f"📬 Stripe webhook recibido: {event_type}")

        if event_type == "checkout.session.completed":
            session = event["data"]["object"]
            user_id = int(session["metadata"]["user_id"])
            plan_id = int(session["metadata"]["plan_id"])
            customer_id = session.get("customer")
            subscription_id = session.get("subscription")

            logger.info(f"🎟️ Checkout completado - user_id={user_id}, plan_id={plan_id}")

            existing = self.db.query(Subscription).filter_by(user_id=user_id).first()
            if existing:
                logger.info("🔁 Actualizando suscripción existente")
                existing.stripe_subscription_id = subscription_id
                existing.stripe_customer_id = customer_id
                existing.plan_id = plan_id
                existing.is_active = True
                existing.cancel_at_period_end = False
                existing.current_period_end = None
            else:
                logger.info("🆕 Creando nueva suscripción")
                sub = Subscription(
                    user_id=user_id,
                    stripe_subscription_id=subscription_id,
                    stripe_customer_id=customer_id,
                    plan_id=plan_id,
                    is_active=True
                )
                self.db.add(sub)
            self.db.commit()
            logger.info("✅ Suscripción procesada correctamente")

        elif event_type == "invoice.paid":
            invoice = event["data"]["object"]
            subscription_id = invoice["subscription"]
            logger.info(f"💰 Pago recibido para suscripción {subscription_id}")

            sub = self.db.query(Subscription).filter_by(stripe_subscription_id=subscription_id).first()
            if sub:
                sub.is_active = True
                self.db.commit()
                logger.info("✅ Suscripción marcada como activa")

        elif event_type == "invoice.payment_failed":
            invoice = event["data"]["object"]
            subscription_id = invoice["subscription"]
            logger.warning(f"⚠️ Pago fallido para suscripción {subscription_id}")

            sub = self.db.query(Subscription).filter_by(stripe_subscription_id=subscription_id).first()
            if sub:
                sub.is_active = False
                self.db.commit()
                logger.info("❌ Suscripción marcada como inactiva")

        elif event_type == "customer.subscription.updated":
            subscription = event["data"]["object"]
            subscription_id = subscription["id"]
            cancel_at_period_end = subscription.get("cancel_at_period_end", False)
            period_end = subscription.get("current_period_end")

            logger.info(f"🔄 Subscripción actualizada {subscription_id}, cancel_at_period_end={cancel_at_period_end}")

            sub = self.db.query(Subscription).filter_by(stripe_subscription_id=subscription_id).first()
            if sub:
                sub.cancel_at_period_end = cancel_at_period_end
                if period_end:
                    sub.current_period_end = datetime.utcfromtimestamp(period_end)
                self.db.commit()

        elif event_type == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            subscription_id = subscription["id"]
            logger.warning(f"🗑️ Subscripción eliminada: {subscription_id}")

            sub = self.db.query(Subscription).filter_by(stripe_subscription_id=subscription_id).first()
            if sub:
                sub.is_active = False
                self.db.commit()
                logger.info("🚫 Subscripción marcada como inactiva")

        else:
            logger.info(f"⚠️ Evento no manejado: {event_type}")