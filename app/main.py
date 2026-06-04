from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database.database import create_tables
from app.expenses.controller import router as expenses_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(expenses_router)


@app.get("/")
async def root():
    return {"status": "ok"}