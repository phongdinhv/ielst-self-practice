import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

engine = create_engine(
    os.getenv("DATABASE_URL", "postgresql+psycopg://ielts:ielts@localhost:5432/ielts"),
    pool_pre_ping=True,
)
Session = sessionmaker(engine, expire_on_commit=False)
