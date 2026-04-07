from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import (
    get_db_session,
    UserProfile,
    Subscription,
    SubscriptionStatus,
    Plan,
    PlanType,
    Conversation,
)
from src.db import UserRole, Transaction
from src.polarservice.polar_client import get_polar_client
from src.settings import get_settings

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _month_bounds(dt: datetime):
    # return (start_of_month, start_of_next_month)
    start = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1)
    else:
        next_month = start.replace(month=start.month + 1)
    return start, next_month


def _last_month_bounds(dt: datetime):
    # return (start_of_last_month, start_of_this_month)
    this_start, _ = _month_bounds(dt)
    if this_start.month == 1:
        last = this_start.replace(year=this_start.year - 1, month=12)
    else:
        last = this_start.replace(month=this_start.month - 1)
    return last, this_start


def _safe_amount_from_order(o: dict) -> float:
    # Defensive picking of amount fields from Polar order dict
    for k in ("amount_paid", "amount", "total", "amount_total", "price"):
        v = o.get(k)
        if v is None:
            continue
        try:
            return float(v)
        except Exception:
            continue
    return 0.0


@router.get("/")
async def get_dashboard(
    db: AsyncSession = Depends(get_db_session),
    polar_client=Depends(get_polar_client),
    settings=Depends(get_settings),
):
    try:
        # Total users (exclude admins)
        r = await db.execute(select(func.count()).select_from(UserProfile).where(UserProfile.role == UserRole.USER))
        total_users = int(r.scalar_one() or 0)

        # Active subscriptions (only for USER role)
        r = await db.execute(
            select(func.count()).select_from(Subscription).join(UserProfile, Subscription.user_id == UserProfile.id).where(Subscription.status == SubscriptionStatus.ACTIVE, UserProfile.role == UserRole.USER)
        )
        active_subs = int(r.scalar_one() or 0)

        # Active sessions (last hour) for USER role
        r = await db.execute(
            select(func.count()).select_from(UserProfile).where(UserProfile.last_active_at >= text("CURRENT_TIMESTAMP - INTERVAL '1 hour'"), UserProfile.role == UserRole.USER)
        )
        active_sessions = int(r.scalar_one() or 0)

        # Plan distribution (exclude admins)
        r = await db.execute(select(UserProfile.plan_type, func.count()).where(UserProfile.role == UserRole.USER).group_by(UserProfile.plan_type))
        rows = r.all()
        total_for_pct = total_users or 1
        plan_distribution = []
        for plan_type, count in rows:
            plan_name = plan_type.value if hasattr(plan_type, "value") else str(plan_type)
            plan_distribution.append({"plan_type": plan_name, "count": int(count), "pct": round(100.0 * int(count) / total_for_pct, 2)})

        # Recent users (last 7 days), exclude admins
        r = await db.execute(
            select(UserProfile.id, UserProfile.name, UserProfile.email_id, UserProfile.plan_type, UserProfile.created_at)
            .where(UserProfile.created_at >= text("CURRENT_TIMESTAMP - INTERVAL '7 days'"), UserProfile.role == UserRole.USER)
            .order_by(UserProfile.created_at.desc())
            .limit(10)
        )
        recent_users = []
        for _id, name, email, plan_type, created_at in r.all():
            recent_users.append({
                "id": str(_id),
                "name": name,
                "email": email,
                "plan_type": plan_type.value if hasattr(plan_type, "value") else str(plan_type),
                "created_at": created_at.isoformat() if created_at is not None else None,
            })

        # Revenue: attempt to use Polar Orders API if configured
        now = datetime.now(timezone.utc)
        this_start, this_next = _month_bounds(now)
        last_start, last_end = _last_month_bounds(now)

        revenue_this_month = 0.0
        revenue_last_month = 0.0

        try:
            org_id = settings.polar_organization_id
            # Polar SDK returns a model-like object; convert to dict when possible
            res_this = polar_client.orders.list(organization_id=org_id, start_date=this_start.strftime("%Y-%m-%d"), end_date=this_next.strftime("%Y-%m-%d"), limit=100)
            res_last = polar_client.orders.list(organization_id=org_id, start_date=last_start.strftime("%Y-%m-%d"), end_date=last_end.strftime("%Y-%m-%d"), limit=100)

            def _iter_items(res):
                if res is None:
                    return []
                data = res.model_dump() if hasattr(res, "model_dump") else (res.dict() if hasattr(res, "dict") else res)
                # common shapes: {'result': {'items': [...]}} or {'items': [...]}
                if isinstance(data, dict):
                    if "result" in data and isinstance(data["result"], dict):
                        return data["result"].get("items", [])
                    return data.get("items", [])
                return []

            for o in _iter_items(res_this):
                revenue_this_month += _safe_amount_from_order(o)
            for o in _iter_items(res_last):
                revenue_last_month += _safe_amount_from_order(o)
        except Exception:
            # If polar is not configured or call fails, leave revenue as 0.0
            revenue_this_month = 0.0
            revenue_last_month = 0.0

        month_over_month_pct = 0.0
        if revenue_last_month:
            month_over_month_pct = round(100.0 * (revenue_this_month - revenue_last_month) / revenue_last_month, 2)

        # Recent transactions — try local `transactions` first (only for users with role USER), else Polar orders in last 7 days
        recent_tx = []
        try:
            # Try local transactions joined to user_profiles to exclude admins
            stmt = (
                select(Transaction.id, Transaction.user_id, Transaction.plan_id, Transaction.amount, Transaction.currency, Transaction.created_at)
                .join(UserProfile, Transaction.user_id == UserProfile.id)
                .where(Transaction.created_at >= text("CURRENT_TIMESTAMP - INTERVAL '7 days'"), UserProfile.role == UserRole.USER)
                .order_by(Transaction.created_at.desc())
                .limit(20)
            )
            t_res = await db.execute(stmt)
            tx_rows = t_res.all()
            if tx_rows:
                for _id, user_id, plan_id, amount, currency, created_at in tx_rows:
                    recent_tx.append({
                        "id": str(_id),
                        "user_id": str(user_id) if user_id is not None else None,
                        "plan_id": plan_id,
                        "amount": float(amount),
                        "currency": currency,
                        "created_at": created_at.isoformat() if created_at is not None else None,
                    })
            else:
                seven_days = (now - __import__("datetime").timedelta(days=7)).strftime("%Y-%m-%d")
                res = polar_client.orders.list(organization_id=settings.polar_organization_id, start_date=seven_days, limit=20)
                items = res.model_dump().get("result", {}).get("items", []) if hasattr(res, "model_dump") else (res.get("result", {}).get("items", []) if isinstance(res, dict) else [])
                for o in items:
                    # Filter Polar results by metadata.user_id when possible
                    meta = o.get("metadata") or o.get("subscription", {}).get("metadata") or {}
                    user_meta_id = meta.get("user_id") if isinstance(meta, dict) else None
                    if user_meta_id:
                        # Verify user exists and is USER role
                        try:
                            ures = await db.execute(select(UserProfile.id).where(UserProfile.auth_user_id == user_meta_id, UserProfile.role == UserRole.USER))
                            if ures.scalar_one_or_none() is None:
                                continue
                        except Exception:
                            # If check fails, skip role filtering and include the item
                            pass
                    recent_tx.append({
                        "id": o.get("id") or o.get("order_id") or None,
                        "user_name": o.get("customer", {}).get("name") if isinstance(o.get("customer"), dict) else None,
                        "plan_name": o.get("plan", {}).get("name") if isinstance(o.get("plan"), dict) else o.get("product_name"),
                        "amount": _safe_amount_from_order(o),
                        "currency": o.get("currency") or o.get("amount_currency") or "USD",
                        "created_at": o.get("created_at") or o.get("createdAt") or None,
                    })
        except Exception:
            recent_tx = []

        return {
            "total_users": total_users,
            "active_subscriptions": active_subs,
            "total_revenue": {
                "this_month": round(revenue_this_month, 2),
                "last_month": round(revenue_last_month, 2),
                "month_over_month_pct": month_over_month_pct,
            },
            "active_sessions_last_hour": active_sessions,
            "plan_distribution": plan_distribution,
            "recent_users": recent_users,
            "recent_transactions": recent_tx,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/count")
async def dashboard_count(
    db: AsyncSession = Depends(get_db_session),
    polar_client=Depends(get_polar_client),
    settings=Depends(get_settings),
):
    """Return top-level counts and revenue summary."""
    try:
        # Total users (exclude admins)
        r = await db.execute(select(func.count()).select_from(UserProfile).where(UserProfile.role == UserRole.USER))
        total_users = int(r.scalar_one() or 0)

        # Active subscriptions (only for USER role)
        r = await db.execute(
            select(func.count()).select_from(Subscription).join(UserProfile, Subscription.user_id == UserProfile.id).where(Subscription.status == SubscriptionStatus.ACTIVE, UserProfile.role == UserRole.USER)
        )
        active_subs = int(r.scalar_one() or 0)

        # Active sessions (last hour) for USER role
        r = await db.execute(
            select(func.count()).select_from(UserProfile).where(UserProfile.last_active_at >= text("CURRENT_TIMESTAMP - INTERVAL '1 hour'"), UserProfile.role == UserRole.USER)
        )
        active_sessions = int(r.scalar_one() or 0)

        # Revenue: prefer local transactions table if present
        now = datetime.now(timezone.utc)
        this_start, this_next = _month_bounds(now)
        last_start, last_end = _last_month_bounds(now)

        revenue_this_month = 0.0
        revenue_last_month = 0.0

        try:
            # Try local transactions first
            r = await db.execute(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.created_at >= text("date_trunc('month', CURRENT_DATE)") )
            )
            revenue_this_month = float(r.scalar_one() or 0.0)

            r = await db.execute(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.created_at >= text("date_trunc('month', CURRENT_DATE) - INTERVAL '1 month'")).where(Transaction.created_at < text("date_trunc('month', CURRENT_DATE)"))
            )
            revenue_last_month = float(r.scalar_one() or 0.0)
        except Exception:
            # Fallback to Polar
            try:
                org_id = settings.polar_organization_id
                res_this = polar_client.orders.list(organization_id=org_id, start_date=this_start.strftime("%Y-%m-%d"), end_date=this_next.strftime("%Y-%m-%d"), limit=100)
                res_last = polar_client.orders.list(organization_id=org_id, start_date=last_start.strftime("%Y-%m-%d"), end_date=last_end.strftime("%Y-%m-%d"), limit=100)

                def _iter_items(res):
                    if res is None:
                        return []
                    data = res.model_dump() if hasattr(res, "model_dump") else (res.dict() if hasattr(res, "dict") else res)
                    if isinstance(data, dict):
                        if "result" in data and isinstance(data["result"], dict):
                            return data["result"].get("items", [])
                        return data.get("items", [])
                    return []

                for o in _iter_items(res_this):
                    revenue_this_month += _safe_amount_from_order(o)
                for o in _iter_items(res_last):
                    revenue_last_month += _safe_amount_from_order(o)
            except Exception:
                revenue_this_month = 0.0
                revenue_last_month = 0.0

        month_over_month_pct = 0.0
        if revenue_last_month:
            month_over_month_pct = round(100.0 * (revenue_this_month - revenue_last_month) / revenue_last_month, 2)

        return {
            "total_users": total_users,
            "active_subscriptions": active_subs,
            "total_revenue": {
                "this_month": round(revenue_this_month, 2),
                "last_month": round(revenue_last_month, 2),
                "month_over_month_pct": month_over_month_pct,
            },
            "active_sessions_last_hour": active_sessions,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plan_distribution")
async def dashboard_plan_distribution(db: AsyncSession = Depends(get_db_session)):
    try:
        r = await db.execute(select(UserProfile.plan_type, func.count()).where(UserProfile.role == UserRole.USER).group_by(UserProfile.plan_type))
        rows = r.all()
        r2 = await db.execute(select(func.count()).select_from(UserProfile).where(UserProfile.role == UserRole.USER))
        total = int(r2.scalar_one() or 0) or 1
        out = []
        for plan_type, count in rows:
            plan_name = plan_type.value if hasattr(plan_type, "value") else str(plan_type)
            out.append({"plan_type": plan_name, "count": int(count), "pct": round(100.0 * int(count) / total, 2)})
        return out
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent_users")
async def dashboard_recent_users(limit: int = 10, days: int = 7, db: AsyncSession = Depends(get_db_session)):
    try:
        stmt = (
            select(UserProfile.id, UserProfile.name, UserProfile.email_id, UserProfile.plan_type, UserProfile.created_at)
            .where(UserProfile.created_at >= text(f"CURRENT_TIMESTAMP - INTERVAL '{int(days)} days'"), UserProfile.role == UserRole.USER)
            .order_by(UserProfile.created_at.desc())
            .limit(int(limit))
        )
        r = await db.execute(stmt)
        out = []
        for _id, name, email, plan_type, created_at in r.all():
            out.append({
                "id": str(_id),
                "name": name,
                "email": email,
                "plan_type": plan_type.value if hasattr(plan_type, "value") else str(plan_type),
                "created_at": created_at.isoformat() if created_at is not None else None,
            })
        return out
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent_transactions")
async def dashboard_recent_transactions(limit: int = 10, days: int = 7, db: AsyncSession = Depends(get_db_session), polar_client=Depends(get_polar_client), settings=Depends(get_settings)):
    try:
        # Prefer local transactions
        try:
            stmt = (
                select(Transaction.id, Transaction.user_id, Transaction.plan_id, Transaction.amount, Transaction.currency, Transaction.created_at)
                .join(UserProfile, Transaction.user_id == UserProfile.id)
                .where(Transaction.created_at >= text(f"CURRENT_TIMESTAMP - INTERVAL '{int(days)} days'"), UserProfile.role == UserRole.USER)
                .order_by(Transaction.created_at.desc())
                .limit(int(limit))
            )
            r = await db.execute(stmt)
            rows = r.all()
            out = []
            for _id, user_id, plan_id, amount, currency, created_at in rows:
                out.append({
                    "id": str(_id),
                    "user_id": str(user_id) if user_id is not None else None,
                    "plan_id": plan_id,
                    "amount": float(amount),
                    "currency": currency,
                    "created_at": created_at.isoformat() if created_at is not None else None,
                })
            return out
        except Exception:
            # Fallback to Polar
            now = datetime.now(timezone.utc)
            seven_days = (now - __import__("datetime").timedelta(days=int(days))).strftime("%Y-%m-%d")
            res = polar_client.orders.list(organization_id=settings.polar_organization_id, start_date=seven_days, limit=int(limit))
            items = res.model_dump().get("result", {}).get("items", []) if hasattr(res, "model_dump") else (res.get("result", {}).get("items", []) if isinstance(res, dict) else [])
            out = []
            for o in items:
                out.append({
                    "id": o.get("id") or o.get("order_id") or None,
                    "user_name": o.get("customer", {}).get("name") if isinstance(o.get("customer"), dict) else None,
                    "plan_name": o.get("plan", {}).get("name") if isinstance(o.get("plan"), dict) else o.get("product_name"),
                    "amount": _safe_amount_from_order(o),
                    "currency": o.get("currency") or o.get("amount_currency") or "USD",
                    "created_at": o.get("created_at") or o.get("createdAt") or None,
                })
            return out

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users_at_limit")
async def dashboard_users_at_limit(db: AsyncSession = Depends(get_db_session)):
    """
    Returns the number of FREE users who have used all their chat quota.
    Counts distinct users who have >= chat_limit conversations.
    """
    try:
        # Get the free plan's chat_limit
        plan_result = await db.execute(
            select(Plan.chat_limit).where(Plan.plan_type == PlanType.FREE).limit(1)
        )
        chat_limit_str = plan_result.scalar_one_or_none()
        try:
            chat_limit = int(chat_limit_str) if chat_limit_str else 3
        except (ValueError, TypeError):
            chat_limit = 3

        # Count FREE users whose non-deleted conversation count >= chat_limit
        subq = (
            select(Conversation.user_id, func.count().label("conv_count"))
            .where(Conversation.deleted_at.is_(None))
            .group_by(Conversation.user_id)
            .subquery()
        )
        result = await db.execute(
            select(func.count())
            .select_from(UserProfile)
            .join(subq, subq.c.user_id == UserProfile.id)
            .where(
                UserProfile.plan_type == PlanType.FREE,
                UserProfile.role == UserRole.USER,
                subq.c.conv_count >= chat_limit,
            )
        )
        users_at_limit = int(result.scalar_one() or 0)

        # Total FREE users for percentage
        total_free_result = await db.execute(
            select(func.count()).select_from(UserProfile).where(
                UserProfile.plan_type == PlanType.FREE,
                UserProfile.role == UserRole.USER,
            )
        )
        total_free_count = int(total_free_result.scalar_one() or 0)
        pct = round(100.0 * users_at_limit / total_free_count, 1) if total_free_count else 0.0

        return {
            "users_at_limit": users_at_limit,
            "total_free_users": total_free_count,
            "pct": pct,
            "chat_limit": chat_limit,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signups_trend")
async def dashboard_signups_trend(days: int = 30, db: AsyncSession = Depends(get_db_session)):
    """
    Returns daily new user signup counts for the last `days` days.
    """
    try:
        stmt = text(
            "SELECT DATE(created_at AT TIME ZONE 'UTC') AS day, COUNT(*) AS signups "
            "FROM user_profiles "
            "WHERE role = 'user' "
            f"AND created_at >= CURRENT_TIMESTAMP - INTERVAL '{int(days)} days' "
            "GROUP BY day ORDER BY day ASC"
        )
        result = await db.execute(stmt)
        rows = result.all()
        return [
            {"date": str(row.day), "signups": int(row.signups)}
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
