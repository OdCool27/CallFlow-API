from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


Database_URL = "sqlite:///./callflow.db"


#facilitates the connection to the database
engine = create_engine(
    Database_URL,
    connect_args={"check_same_thread": False} #verifies if the same thread that created the connection is using it. Not necessary here.
)

#A factory for creating sessions that provides communication channel with database
SessionLocal = sessionmaker(
    autocommit=False, #not automatically save each db change immediately
    autoflush=False, #sends pending changes to the db without current transaction
    bind=engine #assigns the configured engine to the session
)

#Required for ORM entities
Base = declarative_base()

def get_db():
    db = SessionLocal() #creates the session

    try:
        yield db #temp gives db session to requested route
    finally:
        db.close()
