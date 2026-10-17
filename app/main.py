from fastapi import FastAPI

from app.api.routes.clients import router as clients_router

app = FastAPI(title="API Rate Limiter & Analytics Service")

app.include_router(clients_router)


@app.get("/health")
def health():
    return {"status": "ok"}