from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.redis_client import redis_client
from app.core.security import hash_api_key
from app.db.models import APIClient, RateLimitPolicy, RequestLog
from app.db.session import get_db
from app.services.limiter import RateLimiter

router = APIRouter(tags=["protected"])


@router.get("/protected")
async def protected_endpoint(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    start = perf_counter()
    api_key = request.headers.get("X-API-Key")

    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    client = db.scalar(
        select(APIClient).where(
            APIClient.key_hash == hash_api_key(api_key)
        )
    )

    if client is None or not client.is_active:
        raise HTTPException(status_code=401, detail="Invalid API key")

    policy = db.scalar(
        select(RateLimitPolicy).where(
            RateLimitPolicy.client_id == client.id,
            RateLimitPolicy.endpoint == "*",
        )
    )

    if policy is None:
        raise HTTPException(status_code=403, detail="No rate-limit policy")

    limiter = RateLimiter(redis_client)

    result = await limiter.check(
        client.id,
        policy.limit_count,
        policy.window_seconds,
    )
    
    print("=== RATE LIMIT DEBUG ===")
    print("Client ID:", client.id)
    print("Limiter result:", result)
    print("Will return:", 200 if result["allowed"] else 429)

    status_code = 200 if result["allowed"] else 429

    response.headers["X-RateLimit-Limit"] = str(result["limit"])
    response.headers["X-RateLimit-Remaining"] = str(result["remaining"])
    
    print("=== RESPONSE DEBUG ===")
    print("Allowed:", result["allowed"])
    print("Status code:", status_code)
    
    if not result["allowed"]:
        response.headers["Retry-After"] = str(result["retry_after"])

    db.add(
        RequestLog(
            client_id=client.id,
            endpoint="/protected",
            status_code=status_code,
            latency_ms=max(
                0,
                int((perf_counter() - start) * 1000),
            ),
        )
    )
    db.commit()

    if not result["allowed"]:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={
                "Retry-After": str(result["retry_after"]),
                "X-RateLimit-Limit": str(result["limit"]),
                "X-RateLimit-Remaining": str(result["remaining"]),
            },
        )

    return {
        "message": "Request allowed",
        "client_id": client.id,
    }