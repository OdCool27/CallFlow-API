#importing fastAPI to facilitate HTTP requests & responses (as JSON) and run backend logic.
from fastapi import FastAPI

from app.database import engine
from app import models
from app.routers import customer, agent, call, report

models.Base.metadata.create_all(bind=engine)

#creates an instance of FastAPI application and stores it in app.
app = FastAPI(
    title="CallFlow API",
    description="REST API for managing customers, agents, and telephony calls.",
    version="1.0.0"
)

app.include_router(customer.router)
app.include_router(agent.router)
app.include_router(call.router)
app.include_router(report.router)


#route defined for root
@app.get("/")
def root():
    return {"message": "Call Flow API is running."}

#route defined for health
#Written to accommodate for specific fields in the URL using: /health?field=[field]
@app.get("/health")
def health_check(field: str | None = None):
    health_data = {
        "status": "healthy",
        "database": "connected",
        "version": "1.0.0"
    }

    if field:
        return {field: health_data[field]}

    return health_data