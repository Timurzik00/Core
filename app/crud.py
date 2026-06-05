import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
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
    return db.query(models.Agent).filter(models.Agent.family == family).order_by(models.Agent.id.asc()).all()


def delete_agent(db: Session, agent: models.Agent):
    db.delete(agent)
    db.commit()


def update_agent_last_seen(db: Session, agent: models.Agent):
    """
    Обновить last_seen после успешного поллинга агента.
    Заодно чистим last_error: раз агент только что нас успешно опросил,
    значит он жив и сеть работает. Если у него сохраняется реальная ошибка
    применения конфига — она вернётся через ближайший report_status.
    """
    agent.last_seen = datetime.utcnow()
    agent.last_error = None
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


def create_agent_config(db: Session, agent: models.Agent, desired_config: dict) -> models.Config:
    latest = get_latest_config_by_agent(db, agent)
    version = latest.version + 1 if latest else 1
    config = models.Config(agent_id=agent.id, desired_config=desired_config, version=version)
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def _normalize_config(config: dict) -> dict:
    """
    Нормализовать конфиг: привести старое поле family к service.
    Если есть family но нет service — копируем значение в service и убираем family.
    """
    cfg = dict(config)
    if "family" in cfg and not cfg.get("service"):
        cfg["service"] = cfg.pop("family")
    elif "family" in cfg:
        cfg.pop("family")
    return cfg


def _config_key(config: dict) -> str:
    """
    Уникальный ключ конфига для мёрджа.
    Приоритет: service → family (legacy) → file.path → 'default'
    """
    return config.get("service") or config.get("family") or (config.get("file") or {}).get("path") or "default"


def _extract_configs_list(desired_config: dict) -> list[dict]:
    """Достать список конфигов из desired_config независимо от формата."""
    if "configs" in desired_config:
        return list(desired_config["configs"])
    return [desired_config]


def _merge_configs(existing: list[dict], incoming: list[dict]) -> list[dict]:
    """
    Смёрджить входящие конфиги с существующими по ключу service.
    Старые записи с полем family нормализуются к service перед мёрджем.
    - Совпадает service — заменить.
    - Новый service — добавить.
    - Остальные существующие — оставить без изменений.
    """
    # Нормализуем все существующие (убираем legacy family → service)
    normalized_existing = [_normalize_config(c) for c in existing]
    index: dict[str, dict] = {_config_key(c): c for c in normalized_existing}
    for cfg in incoming:
        index[_config_key(cfg)] = cfg
    return list(index.values())


def create_agent_configs_bulk(db: Session, agent: models.Agent, payloads: list[dict]) -> models.Config:
    """
    Сохранить набор конфигов как ОДНУ версию с мёрджем по service.

    Примеры:
      было [coroot, nginx] + пришёл [coroot новый] → станет [coroot новый, nginx]
      было [coroot]        + пришёл [nginx]        → станет [coroot, nginx]
      было []              + пришёл [coroot, nginx] → станет [coroot, nginx]
    """
    latest = get_latest_config_by_agent(db, agent)
    next_version = (latest.version + 1) if latest else 1

    if latest:
        existing = _extract_configs_list(latest.desired_config)
        merged = _merge_configs(existing, payloads)
    else:
        merged = payloads

    desired = merged[0] if len(merged) == 1 else {"configs": merged}

    config = models.Config(
        agent_id=agent.id,
        desired_config=desired,
        version=next_version,
    )
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
    return (
        db.query(models.ConfigHistory)
        .filter(models.ConfigHistory.agent_id == agent.id)
        .order_by(desc(models.ConfigHistory.applied_at))
        .limit(limit)
        .all()
    )


def get_family_config_history(db: Session, family: str, limit: int = 100):
    return (
        db.query(models.ConfigHistory)
        .join(models.Agent)
        .filter(models.Agent.family == family)
        .order_by(desc(models.ConfigHistory.applied_at))
        .limit(limit)
        .all()
    )


def get_config_history_by_version(db: Session, agent: models.Agent, version: int):
    return (
        db.query(models.ConfigHistory)
        .filter(models.ConfigHistory.agent_id == agent.id, models.ConfigHistory.config_version == version)
        .order_by(desc(models.ConfigHistory.applied_at))
        .all()
    )


def get_failed_config_applications(db: Session, agent: models.Agent, limit: int = 50):
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
    return (
        db.query(models.AgentConfigSnapshot)
        .filter(models.AgentConfigSnapshot.agent_id == agent.id)
        .order_by(desc(models.AgentConfigSnapshot.captured_at))
        .first()
    )


def get_agent_config_snapshots(db: Session, agent: models.Agent, limit: int = 20):
    return (
        db.query(models.AgentConfigSnapshot)
        .filter(models.AgentConfigSnapshot.agent_id == agent.id)
        .order_by(desc(models.AgentConfigSnapshot.captured_at))
        .limit(limit)
        .all()
    )


def get_snapshots_with_drift(db: Session, agent: models.Agent):
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
    return (
        db.query(models.ManagedFile)
        .filter(models.ManagedFile.agent_id == agent.id, models.ManagedFile.file_path == file_path)
        .first()
    )


def get_agent_managed_files(db: Session, agent: models.Agent):
    return (
        db.query(models.ManagedFile)
        .filter(models.ManagedFile.agent_id == agent.id)
        .order_by(models.ManagedFile.file_path.asc())
        .all()
    )


def get_out_of_sync_files(db: Session, agent: models.Agent):
    return (
        db.query(models.ManagedFile)
        .filter(models.ManagedFile.agent_id == agent.id, models.ManagedFile.is_in_sync == False)
        .order_by(models.ManagedFile.file_path.asc())
        .all()
    )


def get_family_managed_files_status(db: Session, family: str):
    return (
        db.query(models.ManagedFile)
        .join(models.Agent)
        .filter(models.Agent.family == family)
        .order_by(models.Agent.hostname.asc(), models.ManagedFile.file_path.asc())
        .all()
    )


# ========== AGENT COMMANDS ==========

def create_agent_command(
    db: Session,
    agent: models.Agent,
    command_type: str,
    params: dict | None = None,
) -> models.AgentCommand:
    """Создать команду для агента (статус pending)."""
    cmd = models.AgentCommand(
        agent_id=agent.id,
        command_type=command_type,
        params=params or {},
        status="pending",
    )
    db.add(cmd)
    db.commit()
    db.refresh(cmd)
    return cmd


def get_command(db: Session, command_id: int) -> models.AgentCommand | None:
    return db.query(models.AgentCommand).filter(models.AgentCommand.id == command_id).first()


def get_pending_commands_for_agent(db: Session, agent: models.Agent, limit: int = 10) -> list[models.AgentCommand]:
    """
    Забрать pending-команды для агента и пометить их running.
    Атомарно: pending → running с проставлением picked_at.
    """
    cmds = (
        db.query(models.AgentCommand)
        .filter(
            models.AgentCommand.agent_id == agent.id,
            models.AgentCommand.status == "pending",
        )
        .order_by(models.AgentCommand.id.asc())
        .limit(limit)
        .all()
    )
    now = datetime.utcnow()
    for cmd in cmds:
        cmd.status = "running"
        cmd.picked_at = now
    db.commit()
    for cmd in cmds:
        db.refresh(cmd)
    return cmds


def complete_command(
    db: Session,
    cmd: models.AgentCommand,
    result: dict | None = None,
    error: str | None = None,
) -> models.AgentCommand:
    """Записать результат выполнения команды."""
    cmd.status = "failed" if error else "done"
    cmd.result = result
    cmd.error = error
    cmd.completed_at = datetime.utcnow()
    db.add(cmd)
    db.commit()
    db.refresh(cmd)
    return cmd


# ========== SERVICE PRESETS ==========

def list_service_presets(db: Session) -> list[models.ServicePreset]:
    return db.query(models.ServicePreset).order_by(models.ServicePreset.service.asc()).all()


def get_service_preset(db: Session, preset_id: int) -> models.ServicePreset | None:
    return db.query(models.ServicePreset).filter(models.ServicePreset.id == preset_id).first()


def get_service_preset_by_name(db: Session, service: str) -> models.ServicePreset | None:
    return db.query(models.ServicePreset).filter(models.ServicePreset.service == service).first()


def create_service_preset(
    db: Session,
    service: str,
    file_path: str | None = None,
    cli_binary: str | None = None,
    cli_args: str | None = None,
    content_template: str | None = None,
    description: str | None = None,
) -> models.ServicePreset:
    preset = models.ServicePreset(
        service=service,
        file_path=file_path,
        cli_binary=cli_binary,
        cli_args=cli_args,
        content_template=content_template,
        description=description,
    )
    db.add(preset)
    db.commit()
    db.refresh(preset)
    return preset


def update_service_preset(
    db: Session,
    preset: models.ServicePreset,
    **fields,
) -> models.ServicePreset:
    for key, value in fields.items():
        if hasattr(preset, key) and value is not None:
            setattr(preset, key, value)
    preset.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(preset)
    return preset


def delete_service_preset(db: Session, preset: models.ServicePreset):
    db.delete(preset)
    db.commit()


def list_agent_commands(db: Session, agent: models.Agent, limit: int = 100, status_filter: str | None = None):
    """Список команд конкретного агента."""
    q = db.query(models.AgentCommand).filter(models.AgentCommand.agent_id == agent.id)
    if status_filter:
        q = q.filter(models.AgentCommand.status == status_filter)
    return q.order_by(desc(models.AgentCommand.created_at)).limit(limit).all()


def list_all_commands(db: Session, limit: int = 100, status_filter: str | None = None, command_type: str | None = None):
    """Глобальный список команд (для UI-страницы)."""
    q = db.query(models.AgentCommand)
    if status_filter:
        q = q.filter(models.AgentCommand.status == status_filter)
    if command_type:
        q = q.filter(models.AgentCommand.command_type == command_type)
    return q.order_by(desc(models.AgentCommand.created_at)).limit(limit).all()


def list_all_config_history(db: Session, limit: int = 200, success_filter: bool | None = None, family: str | None = None):
    """Глобальная история применения конфигов с фильтрами."""
    q = db.query(models.ConfigHistory).join(models.Agent)
    if success_filter is not None:
        q = q.filter(models.ConfigHistory.success == success_filter)
    if family:
        q = q.filter(models.Agent.family == family)
    return q.order_by(desc(models.ConfigHistory.applied_at)).limit(limit).all()


# ========== FAMILY MANAGEMENT ==========

def rename_family(db: Session, old_name: str, new_name: str) -> int:
    """
    Переименовать семью: обновить поле family у всех агентов.
    Возвращает количество затронутых агентов.
    """
    agents = db.query(models.Agent).filter(models.Agent.family == old_name).all()
    for agent in agents:
        agent.family = new_name
        agent.updated_at = datetime.utcnow()
    db.commit()
    return len(agents)


def delete_family(db: Session, family: str) -> int:
    """
    Удалить семью целиком: удаляются все агенты семьи и каскадом всё связанное
    (configs, history, snapshots, files, commands).
    Возвращает количество удалённых агентов.
    """
    agents = db.query(models.Agent).filter(models.Agent.family == family).all()
    count = len(agents)
    for agent in agents:
        db.delete(agent)
    db.commit()
    return count


def update_agent_family(db: Session, agent: models.Agent, new_family: str) -> models.Agent:
    """Сменить семью у агента."""
    agent.family = new_family
    agent.updated_at = datetime.utcnow()
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def bulk_update_agents_family(db: Session, uuids: list[str], new_family: str) -> tuple[int, list[str]]:
    """
    Массовая смена семьи у списка агентов.
    Возвращает (число обновлённых, список не найденных UUID).
    """
    not_found: list[str] = []
    updated = 0
    for uid in uuids:
        agent = get_agent_by_uuid(db, uid)
        if agent is None:
            not_found.append(uid)
            continue
        agent.family = new_family
        agent.updated_at = datetime.utcnow()
        db.add(agent)
        updated += 1
    db.commit()
    return updated, not_found
