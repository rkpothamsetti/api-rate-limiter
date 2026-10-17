from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import generate_api_key, hash_api_key
from app.db.models import APIClient, RateLimitPolicy
from app.db.session import get_db
from app.schemas.clients import ClientCreate, ClientCreated

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("", response_model=ClientCreated, status_code=201)
def create_client(
    payload: ClientCreate,
    db: Session = Depends(get_db),
):
    api_key = generate_api_key()

    client = APIClient(
        name=payload.name,
        key_hash=hash_api_key(api_key),
    )
    client.policies.append(
        RateLimitPolicy(
            endpoint="*",
            limit_count=payload.limit_count,
            window_seconds=payload.window_seconds,
        )
    )

    db.add(client)
    db.commit()
    db.refresh(client)

    policy = client.policies[0]

    return ClientCreated(
        id=client.id,
        name=client.name,
        api_key=api_key,
        limit_count=policy.limit_count,
        window_seconds=policy.window_seconds,
    )


@router.get("/{client_id}")
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
):
    client = db.scalar(
        select(APIClient).where(APIClient.id == client_id)
    )

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    return {
        "id": client.id,
        "name": client.name,
        "is_active": client.is_active,
        "policies": [
            {
                "endpoint": p.endpoint,
                "limit_count": p.limit_count,
                "window_seconds": p.window_seconds,
            }
            for p in client.policies
        ],
    }