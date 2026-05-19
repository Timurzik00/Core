from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Boolean, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, index=True, nullable=False)
    family = Column(String(128), nullable=False, index=True)
    hostname = Column(String(128), nullable=False)
    version = Column(String(64), nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_applied_version = Column(Integer, nullable=True)
    last_error = Column(String(1024), nullable=True)
    last_reported_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

#    configs = relationship("Config", back_populates="agent", order_by="Config.id")
    configs = relationship("Config", back_populates="agent", order_by="Config.id", cascade="all, delete-orphan")
    history = relationship("ConfigHistory", back_populates="agent", cascade="all, delete-orphan")
    snapshots = relationship("AgentConfigSnapshot", back_populates="agent", cascade="all, delete-orphan")
    files = relationship("ManagedFile", back_populates="agent", cascade="all, delete-orphan")


class Config(Base):
    __tablename__ = "configs"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    desired_config = Column(JSON, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    agent = relationship("Agent", back_populates="configs")


class ConfigHistory(Base):
    """История применения конфигов на агентах"""
    __tablename__ = "config_history"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    config_version = Column(Integer, nullable=False)
    applied_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    success = Column(Boolean, default=False, nullable=False)
    error = Column(String(2048), nullable=True)
    applied_by = Column(String(64), default="agent", nullable=False)  # agent, manual, scheduler
    duration_seconds = Column(Integer, nullable=True)

    agent = relationship("Agent", back_populates="history")


class AgentConfigSnapshot(Base):
    """Расширенный снимок текущего состояния агента для мониторинга дрейфа"""
    __tablename__ = "agent_config_snapshot"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    config_version = Column(Integer, nullable=True)  # какую версию конфига отражает snapshot
    snapshot = Column(JSON, nullable=False)  # расширенные данные
    captured_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # Поля для быстрого поиска дрейфа
    has_drift = Column(Boolean, default=False, nullable=False)  # отличается ли от желаемого
    drift_summary = Column(String(512), nullable=True)  # краткое описание различий

    agent = relationship("Agent", back_populates="snapshots")


class ManagedFile(Base):
    """Отслеживание файлов, которыми управляет конфиг"""
    __tablename__ = "managed_files"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    file_path = Column(String(512), nullable=False, index=True)  # /etc/config.conf
    desired_content = Column(Text, nullable=True)  # желаемое содержимое
    current_content = Column(Text, nullable=True)  # текущее содержимое на агенте
    last_synced_at = Column(DateTime, nullable=True)  # когда последний раз синхронизировали
    last_checked_at = Column(DateTime, default=datetime.utcnow, nullable=True)  # когда последний раз проверяли
    is_in_sync = Column(Boolean, default=False, nullable=False)  # совпадает ли с желаемым
    config_version = Column(Integer, nullable=True)  # версия конфига

    agent = relationship("Agent", back_populates="files")
