from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Sua connection string real do Neon.tech
SQLALCHEMY_DATABASE_URL = "postgresql://neondb_owner:npg_AFcwNmo0lXY5@ep-curly-art-acr8jc4w-pooler.sa-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# Garantindo que o SQLAlchemy entenda o formato do Postgres
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()