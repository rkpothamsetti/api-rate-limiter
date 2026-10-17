from pydantic import BaseModel, Field


class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    limit_count: int = Field(gt=0, le=100000)
    window_seconds: int = Field(gt=0, le=86400)


class ClientCreated(BaseModel):
    id: int
    name: str
    api_key: str
    limit_count: int
    window_seconds: int