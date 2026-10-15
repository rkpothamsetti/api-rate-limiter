from fastapi import FastAPI

app = FastAPI(title="API Rate Limiter & Analytics Service")


@app.get("/health")
def health():
    return {"status": "ok"}
