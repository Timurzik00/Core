import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from app import models


def create_agent(db: Session, family: str, hostname: str, version: str) -> models.Agent:
    agent_uuid = str(uuid.uuid4())
    agent = models.Agent(
        uuid=agent_uuid,
        family=family,
        hostname=hostname,
        version=version,
        last_seen=datetime.utcnow(),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def get_agent_by_uuid(db: Session, agent_uuid: str):
    return db.query(models.Agent).filter(models.Agent.uuid == agent_uuid).first()


def get_all_agents(db: Session):
    return db.query(models.Agent).order_by(models.Agent.id.asc()).all()


def get_agents_by_family(db: Session, family: str):
    """Получить все агенты определённого family"""
    return db.query(models.Agent).filter(models.Agent.family == family).order_by(models.Agent.id.asc()).all()


def delete_agent(db: Session, agent: models.Agent):
    """Удалить агента и все связанные данные"""
    db.delete(agent)
    db.commit()


def update_agent_last_seen(db: Session, agent: models.Agent):
    agent.last_seen = datetime.utcnow()
    agent.updated_at = datetime.utcnow()
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def update_agent_status(db: Session, agent: models.Agent, last_applied_version: int | None = None, last_error: str | None = None):
    if last_applied_version is not None:
        agent.last_applied_version = last_applied_version
    agent.last_error = last_error
    agent.last_reported_at = datetime.utcnow()
    agent.updated_at = datetime.utcnow()
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def create_agent_config(db: Session, agent: models.Agent, desired_config: dict):
    latest = get_latest_config_by_agent(db, agent)
    version = latest.version + 1 if latest else 1
    config = models.Config(agent_id=agent.id, desired_config=desired_config, version=version)
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def get_latest_config_by_agent(db: Session, agent: models.Agent):
    return (
        db.query(models.Config)
        .filter(models.Config.agent_id == agent.id)
        .order_by(models.Config.id.desc())
        .first()
    )


def get_config_by_version(db: Session, agent: models.Agent, version: int):
    """Получить конфиг определенной версии"""
    return (
        db.query(models.Config)
        .filter(models.Config.agent_id == agent.id, models.Config.version == version)
        .first()
    )


# ========== CONFIG HISTORY ==========

def record_config_application(
    db: Session,
    agent: models.Agent,
    config_version: int,
    success: bool,
    error: str | None = None,
    duration_seconds: int | None = None,
    applied_by: str = "agent"
):
    """Записать факт применения конфига"""
    history = models.ConfigHistory(
        agent_id=agent.id,
        config_version=config_version,
        success=success,
        error=error,
        duration_seconds=duration_seconds,
        applied_by=applied_by,
    )
    db.add(history)
    db.commit()
    db.refresh(history)
    return history


def get_config_history(db: Session, agent: models.Agent, limit: int = 50):
    """Получить историю применения конфигов для агента"""
    return (
        db.query(models.ConfigHistory)
        .filter(models.ConfigHistory.agent_id == agent.id)
        .order_by(desc(models.ConfigHistory.applied_at))
        .limit(limit)
        .all()
    )


def get_family_config_history(db: Session, family: str, limit: int = 100):
    """Получить историю для всех агентов семейства"""
    return (
        db.query(models.ConfigHistory)
        .join(models.Agent)
        .filter(models.Agent.family == family)
        .order_by(desc(models.ConfigHistory.applied_at))
        .limit(limit)
        .all()
    )


def get_config_history_by_version(db: Session, agent: models.Agent, version: int):
    """Получить историю применения конкретной версии конфига"""
    return (
        db.query(models.ConfigHistory)
        .filter(models.ConfigHistory.agent_id == agent.id, models.ConfigHistory.config_version == version)
        .order_by(desc(models.ConfigHistory.applied_at))
        .all()
    )


def get_failed_config_applications(db: Session, agent: models.Agent, limit: int = 50):
    """Получить только неудачные попытки применения"""
    return (
        db.query(models.ConfigHistory)
        .filter(models.ConfigHistory.agent_id == agent.id, models.ConfigHistory.success == False)
        .order_by(desc(models.ConfigHistory.applied_at))
        .limit(limit)
        .all()
    )


# ========== CONFIG SNAPSHOT ==========

def save_agent_config_snapshot(
    db: Session,
    agent: models.Agent,
    snapshot: dict,
    config_version: int | None = None,
    has_drift: bool = False,
    drift_summary: str | None = None
):
    """Сохранить расширенный снимок конфига с агента"""
    # Удалить старые snapshots (оставить последние 20)
    old_snapshots = (
        db.query(models.AgentConfigSnapshot)
        .filter(models.AgentConfigSnapshot.agent_id == agent.id)
        .order_by(desc(models.AgentConfigSnapshot.captured_at))
        .offset(20)
        .all()
    )
    for old in old_snapshots:
        db.delete(old)

    snapshot_record = models.AgentConfigSnapshot(
        agent_id=agent.id,
        snapshot=snapshot,
        config_version=config_version,
        has_drift=has_drift,
        drift_summary=drift_summary,
    )
    db.add(snapshot_record)
    db.commit()
    db.refresh(snapshot_record)
    return snapshot_record


def get_latest_agent_config_snapshot(db: Session, agent: models.Agent):
    """Получить последний снимок конфига агента"""
    return (
        db.query(models.AgentConfigSnapshot)
        .filter(models.AgentConfigSnapshot.agent_id == agent.id)
        .order_by(desc(models.AgentConfigSnapshot.captured_at))
        .first()
    )


def get_agent_config_snapshots(db: Session, agent: models.Agent, limit: int = 20):
    """Получить историю снимков конфига"""
    return (
        db.query(models.AgentConfigSnapshot)
        .filter(models.AgentConfigSnapshot.agent_id == agent.id)
        .order_by(desc(models.AgentConfigSnapshot.captured_at))
        .limit(limit)
        .all()
    )


def get_snapshots_with_drift(db: Session, agent: models.Agent):
    """Получить снимки, где есть дрейф (отличаются от желаемого)"""
    return (
        db.query(models.AgentConfigSnapshot)
        .filter(models.AgentConfigSnapshot.agent_id == agent.id, models.AgentConfigSnapshot.has_drift == True)
        .order_by(desc(models.AgentConfigSnapshot.captured_at))
        .all()
    )


# ========== MANAGED FILES ==========

def save_managed_file(
    db: Session,
    agent: models.Agent,
    file_path: str,
    desired_content: str | None = None,
    current_content: str | None = None,
    config_version: int | None = None,
    is_in_sync: bool = False
):
    """Сохранить или обновить информацию об управляемом файле"""
    managed_file = (
        db.query(models.ManagedFile)
        .filter(models.ManagedFile.agent_id == agent.id, models.ManagedFile.file_path == file_path)
        .first()
    )

    if managed_file:
        managed_file.desired_content = desired_content
        managed_file.current_content = current_content
        managed_file.is_in_sync = is_in_sync
        managed_file.config_version = config_version
        managed_file.last_checked_at = datetime.utcnow()
        if is_in_sync:
            managed_file.last_synced_at = datetime.utcnow()
    else:
        managed_file = models.ManagedFile(
            agent_id=agent.id,
            file_path=file_path,
            desired_content=desired_content,
            current_content=current_content,
            config_version=config_version,
            is_in_sync=is_in_sync,
            last_checked_at=datetime.utcnow(),
            last_synced_at=datetime.utcnow() if is_in_sync else None,
        )

    db.add(managed_file)
    db.commit()
    db.refresh(managed_file)
    return managed_file


def get_managed_file(db: Session, agent: models.Agent, file_path: str):
    """Получить информацию об управляемом файле"""
    return (
        db.query(models.ManagedFile)
        .filter(models.ManagedFile.agent_id == agent.id, models.ManagedFile.file_path == file_path)
        .first()
    )


def get_agent_managed_files(db: Session, agent: models.Agent):
    """Получить все управляемые файлы агента"""
    return (
        db.query(models.ManagedFile)
        .filter(models.ManagedFile.agent_id == agent.id)
        .order_by(models.ManagedFile.file_path.asc())
        .all()
    )


def get_out_of_sync_files(db: Session, agent: models.Agent):
    """Получить файлы, которые отличаются от желаемого состояния"""
    return (
        db.query(models.ManagedFile)
        .filter(models.ManagedFile.agent_id == agent.id, models.ManagedFile.is_in_sync == False)
        .order_by(models.ManagedFile.file_path.asc())
        .all()
    )


def get_family_managed_files_status(db: Session, family: str):
    """Получить статус управляемых файлов для всего семейства"""
    return (
        db.query(models.ManagedFile)
        .join(models.Agent)
        .filter(models.Agent.family == family)
        .order_by(models.Agent.hostname.asc(), models.ManagedFile.file_path.asc())
        .all()
    )