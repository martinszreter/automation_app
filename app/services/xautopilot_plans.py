"""Persist X Autopilot plan state from Stripe Checkout / refunds."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PlanStatus, XAutopilotPlan
from app.services.stripe_checkout import refund_payment_intent, session_email, session_is_paid
from app.services.stripe_events import identifier


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def upsert_plan_from_checkout(
    db: AsyncSession,
    session: dict[str, Any],
    *,
    access_email: str | None = None,
) -> XAutopilotPlan:
    """Create or refresh the plan row for one Checkout Session.

    Raises ``ValueError`` when the session carries neither an id nor an email,
    which the webhook turns into a 422 rather than a 500.
    """
    checkout_id = identifier(session.get("id"))
    if not checkout_id:
        raise ValueError("checkout session has no id")
    stripe_email = session_email(session)
    email = (access_email or stripe_email).strip().lower()
    if not email:
        raise ValueError("checkout session has no email")

    result = await db.execute(
        select(XAutopilotPlan).where(XAutopilotPlan.stripe_checkout_session_id == checkout_id)
    )
    plan = result.scalar_one_or_none()
    status = PlanStatus.ACTIVE if session_is_paid(session) else PlanStatus.PENDING
    amount = int(session.get("amount_total") or 0)
    currency = str(session.get("currency") or "chf").lower()
    customer = identifier(session.get("customer")) or None
    subscription = identifier(session.get("subscription")) or None
    payment_intent = identifier(session.get("payment_intent")) or None

    if plan is None:
        plan = XAutopilotPlan(
            email=email,
            stripe_email=stripe_email or email,
            status=status,
            stripe_checkout_session_id=checkout_id,
            stripe_customer_id=customer,
            stripe_payment_intent_id=payment_intent,
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
        plan.stripe_payment_intent_id = payment_intent or plan.stripe_payment_intent_id
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
    """The newest active plan whose access email or Stripe email is ``email``."""
    needle = email.strip().lower()
    for column in (XAutopilotPlan.email, XAutopilotPlan.stripe_email):
        result = await db.execute(
            select(XAutopilotPlan)
            .where(func.lower(column) == needle, XAutopilotPlan.status == PlanStatus.ACTIVE)
            .order_by(XAutopilotPlan.created_at.desc())
            .limit(1)
        )
        plan = result.scalar_one_or_none()
        if plan is not None:
            return plan
    return None


async def list_active_plans(db: AsyncSession) -> list[XAutopilotPlan]:
    result = await db.execute(
        select(XAutopilotPlan)
        .where(XAutopilotPlan.status == PlanStatus.ACTIVE)
        .order_by(XAutopilotPlan.created_at.desc())
    )
    return list(result.scalars().all())


async def set_plan_paused(db: AsyncSession, plan: XAutopilotPlan, *, paused: bool) -> XAutopilotPlan:
    plan.paused_at = _now() if paused else None
    await db.commit()
    await db.refresh(plan)
    return plan


async def ensure_e2e_plan(db: AsyncSession, email: str) -> XAutopilotPlan:
    """CI only: an active CHF 1 plan for a synthetic checkout id, created once."""
    needle = email.strip().lower()
    checkout_id = f"e2e-{needle}"
    plan = await get_plan_by_checkout_id(db, checkout_id)
    if plan is None:
        plan = XAutopilotPlan(
            email=needle,
            stripe_email=needle,
            status=PlanStatus.ACTIVE,
            stripe_checkout_session_id=checkout_id,
            amount_cents=100,
            currency="chf",
            activated_at=_now(),
        )
        db.add(plan)
    else:
        plan.status = PlanStatus.ACTIVE
        plan.paused_at = None
    await db.commit()
    await db.refresh(plan)
    return plan


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
    if not plan.stripe_payment_intent_id:
        raise ValueError("plan has no payment intent")
    await refund_payment_intent(plan.stripe_payment_intent_id)
    plan.status = PlanStatus.REFUNDED
    await db.commit()
    await db.refresh(plan)
    return plan
