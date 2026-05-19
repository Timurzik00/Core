import os
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

SQLITE_URL = "sqlite:///./data/core.db"
DATA_DIR = os.path.dirname(SQLITE_URL.replace("sqlite:///", ""))

os.makedirs(DATA_DIR, exist_ok=True)

engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


def init_db():
    from app import models

    Base.metadata.create_all(bind=engine)
    _ensure_agent_columns()
    _ensure_history_table()
    _ensure_snapshot_table()


def _ensure_agent_columns():
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(agents)"))
        existing_columns = {row[1] for row in result.fetchall()}

        if "last_applied_version" not in existing_columns:
            conn.execute(text("ALTER TABLE agents ADD COLUMN last_applied_version INTEGER"))
        if "last_error" not in existing_columns:
            conn.execute(text("ALTER TABLE agents ADD COLUMN last_error VARCHAR(1024)"))
        if "last_reported_at" not in existing_columns:
            conn.execute(text("ALTER TABLE agents ADD COLUMN last_reported_at DATETIME"))

        conn.commit()


def _ensure_history_table():
    with engine.connect() as conn:
        # Таблица уже создается через models.ConfigHistory
        conn.commit()


#def _ensure_snapshot_table():
#    with engine.connect() as conn:
#        # Таблица уже создается через models.AgentConfigSnapshot
#        conn.commit()
def _ensure_snapshot_table():
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(agent_config_snapshot)"))
        existing_columns = {row[1] for row in result.fetchall()}

        if "config_version" not in existing_columns:
            conn.execute(text("ALTER TABLE agent_config_snapshot ADD COLUMN config_version INTEGER"))
        if "has_drift" not in existing_columns:
            conn.execute(text("ALTER TABLE agent_config_snapshot ADD COLUMN has_drift BOOLEAN NOT NULL DEFAULT 0"))
        if "drift_summary" not in existing_columns:
            conn.execute(text("ALTER TABLE agent_config_snapshot ADD COLUMN drift_summary VARCHAR(512)"))

        conn.commit()
