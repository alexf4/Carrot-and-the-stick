from fastapi import FastAPI
from pydantic import BaseModel

from app.routers.reps import router as reps_router

app = FastAPI()
app.include_router(reps_router)


class HealthResponse(BaseModel):
    status: str


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
