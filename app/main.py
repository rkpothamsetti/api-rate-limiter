from fastapi import FastAPI

from app.api.routes.clients import router as clients_router
from app.api.routes.demo import router as demo_router
from app.api.routes.analytics import router as analytics_router

app = FastAPI(title="API Rate Limiter & Analytics Service")

app.include_router(clients_router)
app.include_router(demo_router)
app.include_router(analytics_router)


@app.get("/health")
def health():
    return {"status": "ok"}