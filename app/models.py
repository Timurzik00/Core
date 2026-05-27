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

    configs = relationship("Config", back_populates="agent", order_by="Config.id", cascade="all, delete-orphan")
    history = relationship("ConfigHistory", back_populates="agent", cascade="all, delete-orphan")
    snapshots = relationship("AgentConfigSnapshot", back_populates="agent", cascade="all, delete-orphan")
    files = relationship("ManagedFile", back_populates="agent", cascade="all, delete-orphan")
    commands = relationship("AgentCommand", back_populates="agent", cascade="all, delete-orphan")


class Config(Base):
    __tablename__ = "configs"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    desired_config = Column(JSON, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    agent = relationship("Agent", back_populates="configs")


class ConfigHistory(Base):
    __tablename__ = "config_history"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    config_version = Column(Integer, nullable=False)
    applied_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    success = Column(Boolean, default=False, nullable=False)
    error = Column(String(2048), nullable=True)
    applied_by = Column(String(64), default="agent", nullable=False)
    duration_seconds = Column(Integer, nullable=True)

    agent = relationship("Agent", back_populates="history")


class AgentConfigSnapshot(Base):
    __tablename__ = "agent_config_snapshot"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    config_version = Column(Integer, nullable=True)
    snapshot = Column(JSON, nullable=False)
    captured_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    has_drift = Column(Boolean, default=False, nullable=False)
    drift_summary = Column(String(512), nullable=True)

    agent = relationship("Agent", back_populates="snapshots")


class ManagedFile(Base):
    __tablename__ = "managed_files"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    file_path = Column(String(512), nullable=False, index=True)
    desired_content = Column(Text, nullable=True)
    current_content = Column(Text, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)
    last_checked_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    is_in_sync = Column(Boolean, default=False, nullable=False)
    config_version = Column(Integer, nullable=True)

    agent = relationship("Agent", back_populates="files")


class AgentCommand(Base):
    """
    Ad-hoc команды для агентов: чтение файлов, список директорий и т.д.
    Не путать с конфигами — это разовые операции запрос/ответ.
    """
    __tablename__ = "agent_commands"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    command_type = Column(String(64), nullable=False)  # read_file, list_dir, ...
    params = Column(JSON, nullable=False, default=dict)
    status = Column(String(32), default="pending", nullable=False, index=True)  # pending, running, done, failed
    result = Column(JSON, nullable=True)
    error = Column(String(2048), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    picked_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    agent = relationship("Agent", back_populates="commands")


class ServicePreset(Base):
    """
    Пресет сервиса — преднастроенный шаблон конфига:
    имя сервиса, путь файла, команда рестарта.
    Используется фронтом чтобы не вписывать одни и те же значения каждый раз.
    """
    __tablename__ = "service_presets"

    id = Column(Integer, primary_key=True, index=True)
    service = Column(String(128), unique=True, nullable=False, index=True)
    file_path = Column(String(512), nullable=True)
    cli_binary = Column(String(512), nullable=True)
    cli_args = Column(String(1024), nullable=True)
    content_template = Column(Text, nullable=True)
    description = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
