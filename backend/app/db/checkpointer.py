
import os

from dotenv import load_dotenv
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from sqlalchemy.engine import URL

load_dotenv()

database_url = URL.create(
    drivername="postgresql",
    username=os.getenv("POSTGRES_USER", "postgres"),
    password=os.getenv("POSTGRES_PASSWORD"),
    host=os.getenv("POSTGRES_HOST", "localhost"),
    port=int(os.getenv("POSTGRES_PORT", "5432")),
    database=os.getenv("POSTGRES_DB", "procureai_db"),
)

connection_string = database_url.render_as_string(
    hide_password=False
)

connection_pool = ConnectionPool(
    conninfo=connection_string,
    min_size=1,
    max_size=10,
    kwargs={
        "autocommit": True,
        "prepare_threshold": 0,
        "row_factory": dict_row,
    },
    open=False,
)

checkpointer = PostgresSaver(connection_pool)


def init_checkpointer() -> None:
    """Open the pool and initialize LangGraph checkpoint tables."""
    if connection_pool.closed:
        connection_pool.open(wait=True)

    checkpointer.setup()


def close_checkpointer() -> None:
    """Close PostgreSQL connections during application shutdown."""
    if not connection_pool.closed:
        connection_pool.close()
