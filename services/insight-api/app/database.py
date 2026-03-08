from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = 'postgresql://admin:admin@postgres:5432/incidents'
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)