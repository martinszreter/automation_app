"""Persist X Autopilot plan state from Stripe Checkout / refunds."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PlanStatus, XAutopilotPlan
from app.services.stripe_checkout import session_email


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _payment_intent_id(session: dict[str, Any]) -> str | None:
    value = session.get("payment_intent")
    if isinstance(value, dict):
        return value.get("id")
    return value


async def upsert_plan_from_checkout(
    db: AsyncSession,
    session: dict[str, Any],
    *,
    access_email: str | None = None,
) -> XAutopilotPlan:
    checkout_id = session["id"]
    stripe_email = session_email(session)
    email = (access_email or stripe_email).strip().lower()
    if not email:
        raise ValueError("checkout session has no email")

    result = await db.execute(
        select(XAutopilotPlan).where(XAutopilotPlan.stripe_checkout_session_id == checkout_id)
    )
    plan = result.scalar_one_or_none()
    paid = session.get("payment_status") == "paid" or session.get("status") == "complete"
    status = PlanStatus.ACTIVE if paid else PlanStatus.PENDING
    amount = int(session.get("amount_total") or 0)
    currency = (session.get("currency") or "chf").lower()
    customer = session.get("customer")
    if isinstance(customer, dict):
        customer = customer.get("id")
    subscription = session.get("subscription")
    if isinstance(subscription, dict):
        subscription = subscription.get("id")

    if plan is None:
        plan = XAutopilotPlan(
            email=email,
            stripe_email=stripe_email or email,
            status=status,
            stripe_checkout_session_id=checkout_id,
            stripe_customer_id=customer,
            stripe_payment_intent_id=_payment_intent_id(session),
            stripe_subscription_id=subscription,
            amount_cents=amount,
            currency=currency,
            activated_at=_now() if status == PlanStatus.ACTIVE else None,
        )
        db.add(plan)
    else:
        plan.email = email
        if stripe_email:
            plan.stripe_email = stripe_email
        plan.stripe_customer_id = customer or plan.stripe_customer_id
        plan.stripe_payment_intent_id = _payment_intent_id(session) or plan.stripe_payment_intent_id
        plan.stripe_subscription_id = subscription or plan.stripe_subscription_id
        if amount:
            plan.amount_cents = amount
        plan.currency = currency
        if status == PlanStatus.ACTIVE and plan.status != PlanStatus.REFUNDED:
            plan.status = PlanStatus.ACTIVE
            if plan.activated_at is None:
                plan.activated_at = _now()

    await db.commit()
    await db.refresh(plan)
    return plan


async def get_active_plan_for_email(db: AsyncSession, email: str) -> XAutopilotPlan | None:
    needle = email.strip().lower()
    result = await db.execute(
        select(XAutopilotPlan)
        .where(
            func.lower(XAutopilotPlan.email) == needle,
            XAutopilotPlan.status == PlanStatus.ACTIVE,
        )
        .order_by(XAutopilotPlan.created_at.desc())
        .limit(1)
    )
    plan = result.scalar_one_or_none()
    if plan is not None:
        return plan
    result = await db.execute(
        select(XAutopilotPlan)
        .where(
            func.lower(XAutopilotPlan.stripe_email) == needle,
            XAutopilotPlan.status == PlanStatus.ACTIVE,
        )
        .order_by(XAutopilotPlan.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_plan_by_checkout_id(db: AsyncSession, checkout_id: str) -> XAutopilotPlan | None:
    result = await db.execute(
        select(XAutopilotPlan).where(XAutopilotPlan.stripe_checkout_session_id == checkout_id)
    )
    return result.scalar_one_or_none()


async def mark_plan_refunded(db: AsyncSession, payment_intent_id: str) -> XAutopilotPlan | None:
    result = await db.execute(
        select(XAutopilotPlan).where(XAutopilotPlan.stripe_payment_intent_id == payment_intent_id)
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        return None
    plan.status = PlanStatus.REFUNDED
    await db.commit()
    await db.refresh(plan)
    return plan


async def refund_plan(db: AsyncSession, plan: XAutopilotPlan) -> XAutopilotPlan:
    from app.services.stripe_checkout import refund_payment_intent

    if not plan.stripe_payment_intent_id:
        raise ValueError("plan has no payment intent")
    await refund_payment_intent(plan.stripe_payment_intent_id)
    plan.status = PlanStatus.REFUNDED
    await db.commit()
    await db.refresh(plan)
    return plan
