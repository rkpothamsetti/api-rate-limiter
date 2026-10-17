from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_api_key
from app.db.models import APIClient, RequestLog
from app.db.session import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary")
def analytics_summary(
    request: Request,
    db: Session = Depends(get_db),
):
    api_key = request.headers.get("X-API-Key")

    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    client = db.scalar(
        select(APIClient).where(
            APIClient.key_hash == hash_api_key(api_key),
            APIClient.is_active.is_(True),
        )
    )

    if client is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    since = datetime.now(timezone.utc) - timedelta(days=1)

    row = db.execute(
        select(
            func.count(RequestLog.id),
            func.sum(
                func.cast(RequestLog.status_code == 429, type_=__import__(
                    "sqlalchemy"
                ).Integer)
            ),
            func.avg(RequestLog.latency_ms),
        ).where(
            RequestLog.client_id == client.id,
            RequestLog.created_at >= since,
        )
    ).one()

    total = row[0] or 0
    rejected = row[1] or 0
    average_latency = row[2] or 0

    return {
        "period": "last_24_hours",
        "total_requests": total,
        "rejected_requests": rejected,
        "allowed_requests": total - rejected,
        "average_latency_ms": round(float(average_latency), 2),
    }