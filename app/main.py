from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.ami import AMIClient
from app.config import settings
from app.database import engine, SessionLocal
from app.migrations import initialize_database
from app.telephony import CallTracker
from app.routers import customer, agent, call, report, asterisk


@asynccontextmanager
async def lifespan(app):
    logging.basicConfig(level=settings.log_level.upper())
    await asyncio.to_thread(initialize_database, engine)
    app.state.ami = AMIClient(settings, CallTracker(SessionLocal))
    await app.state.ami.start()
    try:
        yield
    finally:
        await app.state.ami.stop()


app = FastAPI(title="CallFlow API", description="Local Asterisk call tracking and customer management", version="2.0.0", lifespan=lifespan)
for router in (customer.router, agent.router, call.router, report.router, asterisk.router):
    app.include_router(router)


@app.get("/")
def root():
    return {"message": "Call Flow API is running."}


@app.get("/health")
def health_check(field: str | None = None):
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(503, "Database unavailable")
    data = {"status": "healthy", "database": "connected", "version": "2.0.0"}
    if field:
        if field not in data:
            raise HTTPException(400, "Unknown health field")
        return {field: data[field]}
    return data
