import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

# A URL deve seguir o padrao: postgresql+asyncpg://user:pass@host:port/dbname
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/modernizer_db")


class Base(DeclarativeBase):
    pass


engine = create_async_engine(DATABASE_URL, echo=False)

async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_db():
    """
    Dependency para fornecer sessoes assincronas nas rotas do FastAPI.
    """
    async with async_session() as session:
        yield session