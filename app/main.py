from fastapi import FastAPI, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session
from app import crud, database, schemas
from app.database import SessionLocal, init_db
import difflib
from datetime import datetime
from typing import Optional

app = FastAPI(
    title="GAIA Core",
    description="""
Система управления конфигурациями агентов с отслеживанием истории и обнаружением дрейфа.

## Как это работает

1. **Агент регистрируется** → получает UUID
2. **Вы пушите конфиг** → на агента по UUID или на всю семью сразу
3. **Агент поллит Core** каждые N секунд → если версия изменилась, применяет только изменившиеся сервисы
4. **Core хранит историю** → все версии конфигов, снимки состояния, ошибки применения

## Ключевые понятия

- **family** — группа агентов (например, `coroot`). Агент регистрируется с одной семьёй. Позволяет пушить конфиг сразу на все машины группы.
- **service** — имя сервиса внутри конфига (`coroot`, `nginx`, `zabbix`...). Ключ мёрджа: при обновлении одного сервиса остальные не трогаются.
- **last_seen** — время последнего poll-запроса агента. Если давно — агент недоступен.
- **created_at** — время регистрации агента. Не меняется.
""",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.on_event("startup")
def on_startup():
    init_db()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ========== SYSTEM ==========

@app.get("/api/v1/health", tags=["System"], summary="Health check")
def health_check():
    """
    Проверить доступность GAIA Core.

    Возвращает `status: healthy` если сервер работает нормально.
    Используйте для мониторинга и liveness-проб.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0"
    }


@app.get("/api/v1/info", tags=["System"], summary="API info")
def get_api_info():
    """
    Информация об API: версия, описание, ссылки на документацию.
    """
    return {
        "title": "GAIA Core",
        "version": "2.0.0",
        "description": "Configuration management system for agents with history tracking and drift detection",
        "base_url": "/api/v1",
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        }
    }


# ========== AGENT MANAGEMENT ==========

@app.post(
    "/api/v1/agent/register",
    response_model=schemas.AgentRegisterResponse,
    tags=["Agent Management"],
    summary="Register a new agent",
)
def register_agent(request: schemas.AgentRegisterRequest, db: Session = Depends(get_db)):
    """
    Зарегистрировать нового агента в GAIA Core.
    """
    agent = crud.create_agent(
        db,
        family=request.agent.family,
        hostname=request.agent.hostname,
        version=request.agent.version,
    )
    return schemas.AgentRegisterResponse(uuid=agent.uuid)


@app.get(
    "/api/v1/agents",
    response_model=schemas.AgentsListResponse,
    tags=["Agent Management"],
    summary="List all agents",
)
def list_agents(
    db: Session = Depends(get_db),
    family: Optional[str] = Query(None, description="Фильтр по семье (например: coroot)"),
    hostname: Optional[str] = Query(None, description="Поиск по hostname (частичное совпадение)"),
    sort_by: Optional[str] = Query("last_seen", description="Сортировка: last_seen | created_at | hostname"),
    order: Optional[str] = Query("desc", description="Порядок: asc | desc"),
    limit: Optional[int] = Query(100, ge=1, le=1000, description="Макс. результатов"),
    offset: Optional[int] = Query(0, ge=0, description="Пропустить N результатов (пагинация)"),
):
    query = crud.get_all_agents(db)

    if family:
        query = [a for a in query if a.family == family]
    if hostname:
        query = [a for a in query if hostname.lower() in a.hostname.lower()]

    if sort_by == "hostname":
        query = sorted(query, key=lambda x: x.hostname, reverse=(order == "desc"))
    elif sort_by == "created_at":
        query = sorted(query, key=lambda x: x.created_at, reverse=(order == "desc"))
    else:
        query = sorted(query, key=lambda x: x.last_seen, reverse=(order == "desc"))

    total = len(query)
    query = query[offset:offset + limit]

    return schemas.AgentsListResponse(
        agents=[
            schemas.AgentResponse(
                uuid=agent.uuid,
                family=agent.family,
                hostname=agent.hostname,
                version=agent.version,
                last_seen=agent.last_seen,
                created_at=agent.created_at,
            )
            for agent in query
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get(
    "/api/v1/agent/{agent_uuid}",
    response_model=schemas.AgentDetailedResponse,
    tags=["Agent Management"],
    summary="Get agent details",
)
def get_agent(agent_uuid: str, db: Session = Depends(get_db)):
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    latest_snapshot = crud.get_latest_agent_config_snapshot(db, agent)
    history = crud.get_config_history(db, agent, limit=10)

    return schemas.AgentDetailedResponse(
        uuid=agent.uuid,
        family=agent.family,
        hostname=agent.hostname,
        version=agent.version,
        last_seen=agent.last_seen,
        created_at=agent.created_at,
        last_applied_version=agent.last_applied_version,
        last_error=agent.last_error,
        last_reported_at=agent.last_reported_at,
        current_snapshot=latest_snapshot,
        recent_history=[
            schemas.ConfigHistoryRecord(
                id=h.id,
                config_version=h.config_version,
                applied_at=h.applied_at,
                success=h.success,
                error=h.error,
                applied_by=h.applied_by,
                duration_seconds=h.duration_seconds,
            )
            for h in history
        ],
    )


@app.delete(
    "/api/v1/agent/{agent_uuid}",
    tags=["Agent Management"],
    summary="Delete agent",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_agent(agent_uuid: str, db: Session = Depends(get_db)):
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    crud.delete_agent(db, agent)
    return None


# ========== CONFIGURATION ==========

@app.post(
    "/api/v1/agent/{agent_uuid}/config",
    response_model=schemas.MultiConfigResponse,
    tags=["Configuration"],
    summary="Set agent configuration",
)
def set_agent_config(
    agent_uuid: str,
    request: schemas.ConfigRequest,
    db: Session = Depends(get_db)
):
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    payloads = request.get_payloads()
    if not payloads:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No config or configs provided")

    config = crud.create_agent_configs_bulk(db, agent, [p.model_dump() for p in payloads])

    return schemas.MultiConfigResponse(
        created=[schemas.ConfigResponse(config=config.desired_config, version=config.version)],
        total=len(payloads),
    )


@app.get(
    "/api/v1/agent/{agent_uuid}/config",
    response_model=schemas.ConfigResponse,
    tags=["Configuration"],
    summary="Get current desired configuration",
    include_in_schema=False,
)
def get_agent_config(agent_uuid: str, db: Session = Depends(get_db)):
    """Внутренний эндпоинт. Вызывается агентом при поллинге каждые N секунд."""
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    config = crud.get_latest_config_by_agent(db, agent)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")

    crud.update_agent_last_seen(db, agent)
    return schemas.ConfigResponse(config=config.desired_config, version=config.version)


@app.get(
    "/api/v1/agent/{agent_uuid}/config/current",
    response_model=schemas.ConfigResponse,
    tags=["Configuration"],
    summary="View current desired config (read-only, no side effects)",
)
def view_agent_config(agent_uuid: str, db: Session = Depends(get_db)):
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    config = crud.get_latest_config_by_agent(db, agent)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")

    return schemas.ConfigResponse(config=config.desired_config, version=config.version)


@app.get(
    "/api/v1/agent/{agent_uuid}/config/{version}",
    response_model=schemas.ConfigVersionInfo,
    tags=["Configuration"],
    summary="Get specific config version",
)
def get_agent_config_by_version(
    agent_uuid: str,
    version: int,
    db: Session = Depends(get_db)
):
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    config = crud.get_config_by_version(db, agent, version)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Config version {version} not found")

    history = crud.get_config_history_by_version(db, agent, version)

    return schemas.ConfigVersionInfo(
        version=config.version,
        created_at=config.created_at,
        config=config.desired_config,
        applications=[
            schemas.ConfigHistoryRecord(
                id=h.id,
                config_version=h.config_version,
                applied_at=h.applied_at,
                success=h.success,
                error=h.error,
                applied_by=h.applied_by,
                duration_seconds=h.duration_seconds,
            )
            for h in history
        ],
    )


@app.post(
    "/api/v1/agent/{agent_uuid}/status",
    response_model=schemas.AgentResponse,
    tags=["Configuration"],
    summary="Report agent status",
    include_in_schema=False,
)
def report_agent_status(
    agent_uuid: str,
    request: schemas.AgentStatusRequest,
    db: Session = Depends(get_db)
):
    """Внутренний эндпоинт. Вызывается агентом после применения конфига."""
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    if request.current_snapshot:
        config_version = agent.last_applied_version
        files_info = request.current_snapshot.get("files", {})

        latest_config = crud.get_latest_config_by_agent(db, agent)

        # Строим карту path → desired content из ВСЕХ конфигов в desired_config.
        # Поддерживает оба формата: одиночный {service, file, cli} и мульти {configs: [...]}
        desired_by_path: dict[str, str] = {}
        if latest_config:
            configs_list = crud._extract_configs_list(latest_config.desired_config)
            for cfg in configs_list:
                if not isinstance(cfg, dict):
                    continue
                file_spec = cfg.get("file")
                if file_spec and file_spec.get("path"):
                    desired_by_path[file_spec["path"]] = file_spec.get("content", "")

        # Сохраняем managed_files для всех файлов из снапшота
        for file_path, file_data in files_info.items():
            crud.save_managed_file(
                db,
                agent,
                file_path=file_path,
                desired_content=desired_by_path.get(file_path),
                current_content=file_data.get("content"),
                config_version=config_version,
                is_in_sync=file_data.get("is_in_sync", False),
            )

        # Для файлов, которые есть в desired, но не в текущем снапшоте
        # (агент не упомянул их потому что они синхронизированы с предыдущей версии) —
        # обновляем desired_content, current_content оставляем как было
        for file_path, desired_content in desired_by_path.items():
            if file_path in files_info:
                continue
            existing = crud.get_managed_file(db, agent, file_path)
            if existing:
                crud.save_managed_file(
                    db,
                    agent,
                    file_path=file_path,
                    desired_content=desired_content,
                    current_content=existing.current_content,
                    config_version=config_version,
                    is_in_sync=existing.is_in_sync,
                )

        crud.save_agent_config_snapshot(
            db,
            agent,
            request.current_snapshot,
            config_version=config_version,
            has_drift=request.current_snapshot.get("has_drift", False),
            drift_summary=request.current_snapshot.get("drift_summary"),
        )

    if request.last_applied_version is not None:
        crud.record_config_application(
            db,
            agent,
            config_version=request.last_applied_version,
            success=request.last_error is None,
            error=request.last_error,
        )

    agent = crud.update_agent_status(
        db,
        agent,
        last_applied_version=request.last_applied_version,
        last_error=request.last_error,
    )
    return schemas.AgentResponse(
        uuid=agent.uuid,
        family=agent.family,
        hostname=agent.hostname,
        version=agent.version,
        last_seen=agent.last_seen,
        created_at=agent.created_at,
        last_applied_version=agent.last_applied_version,
        last_error=agent.last_error,
        last_reported_at=agent.last_reported_at,
    )


# ========== FILE MANAGEMENT ==========

@app.get(
    "/api/v1/agent/{agent_uuid}/file",
    response_model=schemas.FileContentResponse,
    tags=["File Management"],
    summary="Read file content",
)
def get_agent_file(
    agent_uuid: str,
    path: str = Query(..., description="Путь к файлу на агенте"),
    db: Session = Depends(get_db)
):
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    managed_file = crud.get_managed_file(db, agent, path)
    if not managed_file or not managed_file.current_content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File '{path}' not found or not tracked")

    content = managed_file.current_content
    return schemas.FileContentResponse(
        file_path=path,
        content=content,
        size=len(content) if content else 0,
        last_updated=managed_file.last_checked_at,
    )


@app.get(
    "/api/v1/agent/{agent_uuid}/file-diff",
    response_model=schemas.ManagedFilesDiff,
    tags=["File Management"],
    summary="View file differences",
)
def get_file_diff(
    agent_uuid: str,
    path: str = Query(..., description="Путь к файлу для сравнения"),
    db: Session = Depends(get_db)
):
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    managed_file = crud.get_managed_file(db, agent, path)
    if not managed_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File '{path}' not found")

    desired = (managed_file.desired_content or "").splitlines(keepends=True)
    current = (managed_file.current_content or "").splitlines(keepends=True)
    diff = list(difflib.unified_diff(desired, current, fromfile="desired", tofile="current", lineterm=""))

    return schemas.ManagedFilesDiff(
        file_path=path,
        desired_content=managed_file.desired_content,
        current_content=managed_file.current_content,
        is_in_sync=managed_file.is_in_sync,
        differences=[line.rstrip() for line in diff],
    )


@app.get(
    "/api/v1/agent/{agent_uuid}/files",
    response_model=list[schemas.ManagedFileInfo],
    tags=["File Management"],
    summary="List all managed files",
)
def get_agent_managed_files(agent_uuid: str, db: Session = Depends(get_db)):
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    files = crud.get_agent_managed_files(db, agent)
    return [
        schemas.ManagedFileInfo(
            id=f.id, file_path=f.file_path, desired_content=f.desired_content,
            current_content=f.current_content, is_in_sync=f.is_in_sync,
            last_synced_at=f.last_synced_at, last_checked_at=f.last_checked_at,
            config_version=f.config_version,
        )
        for f in files
    ]


@app.get(
    "/api/v1/agent/{agent_uuid}/files/out-of-sync",
    response_model=list[schemas.ManagedFileInfo],
    tags=["File Management"],
    summary="List out-of-sync files",
)
def get_agent_out_of_sync_files(agent_uuid: str, db: Session = Depends(get_db)):
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    files = crud.get_out_of_sync_files(db, agent)
    if not files:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="All files are in sync")

    return [
        schemas.ManagedFileInfo(
            id=f.id, file_path=f.file_path, desired_content=f.desired_content,
            current_content=f.current_content, is_in_sync=f.is_in_sync,
            last_synced_at=f.last_synced_at, last_checked_at=f.last_checked_at,
            config_version=f.config_version,
        )
        for f in files
    ]


# ========== HISTORY & MONITORING ==========

@app.get(
    "/api/v1/agent/{agent_uuid}/history",
    response_model=list[schemas.ConfigHistoryRecord],
    tags=["History & Monitoring"],
    summary="Get configuration application history",
)
def get_agent_history(
    agent_uuid: str,
    limit: int = Query(50, ge=1, le=1000, description="Макс. записей"),
    db: Session = Depends(get_db)
):
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    history = crud.get_config_history(db, agent, limit=limit)
    return [
        schemas.ConfigHistoryRecord(
            id=h.id, config_version=h.config_version, applied_at=h.applied_at,
            success=h.success, error=h.error, applied_by=h.applied_by,
            duration_seconds=h.duration_seconds,
        )
        for h in history
    ]


@app.get(
    "/api/v1/agent/{agent_uuid}/history/failed",
    response_model=list[schemas.ConfigHistoryRecord],
    tags=["History & Monitoring"],
    summary="Get failed application attempts",
)
def get_agent_failed_history(
    agent_uuid: str,
    limit: int = Query(50, ge=1, le=1000, description="Макс. записей"),
    db: Session = Depends(get_db)
):
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    history = crud.get_failed_config_applications(db, agent, limit=limit)
    return [
        schemas.ConfigHistoryRecord(
            id=h.id, config_version=h.config_version, applied_at=h.applied_at,
            success=h.success, error=h.error, applied_by=h.applied_by,
            duration_seconds=h.duration_seconds,
        )
        for h in history
    ]


@app.get(
    "/api/v1/agent/{agent_uuid}/snapshot",
    response_model=schemas.AgentConfigSnapshotResponse,
    tags=["History & Monitoring"],
    summary="Get current agent snapshot",
)
def get_agent_current_snapshot(agent_uuid: str, db: Session = Depends(get_db)):
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    snapshot = crud.get_latest_agent_config_snapshot(db, agent)
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No snapshot found")

    return schemas.AgentConfigSnapshotResponse(
        id=snapshot.id, snapshot=snapshot.snapshot, config_version=snapshot.config_version,
        captured_at=snapshot.captured_at, has_drift=snapshot.has_drift, drift_summary=snapshot.drift_summary,
    )


@app.get(
    "/api/v1/agent/{agent_uuid}/snapshots",
    response_model=list[schemas.AgentConfigSnapshotResponse],
    tags=["History & Monitoring"],
    summary="Get snapshot history",
)
def get_agent_snapshots(
    agent_uuid: str,
    limit: int = Query(20, ge=1, le=1000, description="Макс. снимков"),
    db: Session = Depends(get_db)
):
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    snapshots = crud.get_agent_config_snapshots(db, agent, limit=limit)
    return [
        schemas.AgentConfigSnapshotResponse(
            id=s.id, snapshot=s.snapshot, config_version=s.config_version,
            captured_at=s.captured_at, has_drift=s.has_drift, drift_summary=s.drift_summary,
        )
        for s in snapshots
    ]


@app.get(
    "/api/v1/agent/{agent_uuid}/snapshots/with-drift",
    response_model=list[schemas.AgentConfigSnapshotResponse],
    tags=["History & Monitoring"],
    summary="Get snapshots with drift",
)
def get_agent_snapshots_with_drift(agent_uuid: str, db: Session = Depends(get_db)):
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    snapshots = crud.get_snapshots_with_drift(db, agent)
    return [
        schemas.AgentConfigSnapshotResponse(
            id=s.id, snapshot=s.snapshot, config_version=s.config_version,
            captured_at=s.captured_at, has_drift=s.has_drift, drift_summary=s.drift_summary,
        )
        for s in snapshots
    ]


# ========== FAMILY MANAGEMENT ==========

@app.get(
    "/api/v1/family/{family}/agents",
    response_model=schemas.FamilyAgentsResponse,
    tags=["Family Management"],
    summary="List agents by family",
)
def list_family_agents(family: str, db: Session = Depends(get_db)):
    agents = crud.get_agents_by_family(db, family)
    if not agents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No agents found for family '{family}'")

    return schemas.FamilyAgentsResponse(
        family=family,
        count=len(agents),
        agents=[
            schemas.AgentResponse(
                uuid=agent.uuid, family=agent.family, hostname=agent.hostname,
                version=agent.version, last_seen=agent.last_seen,
                created_at=agent.created_at,
            )
            for agent in agents
        ],
    )


@app.post(
    "/api/v1/family/{family}/config",
    response_model=schemas.FamilyConfigPushResponse,
    tags=["Family Management"],
    summary="Push config to all agents in a family",
)
def push_family_config(
    family: str,
    request: schemas.FamilyConfigPushRequest,
    db: Session = Depends(get_db)
):
    agents = crud.get_agents_by_family(db, family)
    if not agents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No agents found for family '{family}'"
        )

    payloads = [p.model_dump() for p in request.configs]
    results: list[schemas.FamilyConfigPushResult] = []
    updated = 0
    failed = 0

    for agent in agents:
        try:
            config = crud.create_agent_configs_bulk(db, agent, payloads)
            results.append(schemas.FamilyConfigPushResult(
                agent_uuid=agent.uuid,
                hostname=agent.hostname,
                versions_created=[config.version],
            ))
            updated += 1
        except Exception as exc:
            results.append(schemas.FamilyConfigPushResult(
                agent_uuid=agent.uuid,
                hostname=agent.hostname,
                versions_created=[],
                error=str(exc),
            ))
            failed += 1

    return schemas.FamilyConfigPushResponse(
        family=family,
        agents_updated=updated,
        agents_failed=failed,
        results=results,
    )


@app.get(
    "/api/v1/family/{family}/history",
    response_model=schemas.FamilyHistoryResponse,
    tags=["Family Management"],
    summary="Get family configuration history",
)
def get_family_history(
    family: str,
    limit: int = Query(100, ge=1, le=1000, description="Макс. записей"),
    db: Session = Depends(get_db)
):
    history = crud.get_family_config_history(db, family, limit=limit)
    if not history:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No history found for family '{family}'")

    return schemas.FamilyHistoryResponse(
        family=family,
        history=[
            schemas.ConfigHistoryRecord(
                id=h.id, config_version=h.config_version, applied_at=h.applied_at,
                success=h.success, error=h.error, applied_by=h.applied_by,
                duration_seconds=h.duration_seconds,
            )
            for h in history
        ],
    )


@app.get(
    "/api/v1/family/{family}/files-status",
    response_model=schemas.FamilyFilesStatusResponse,
    tags=["Family Management"],
    summary="Get family file synchronization status",
)
def get_family_files_status(family: str, db: Session = Depends(get_db)):
    files = crud.get_family_managed_files_status(db, family)
    if not files:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No managed files found for family '{family}'")

    synced = sum(1 for f in files if f.is_in_sync)
    out_of_sync = sum(1 for f in files if not f.is_in_sync)

    return schemas.FamilyFilesStatusResponse(
        family=family,
        total_files=len(files),
        synced_files=synced,
        out_of_sync_files=out_of_sync,
        files=[
            schemas.ManagedFileInfo(
                id=f.id, file_path=f.file_path, desired_content=f.desired_content,
                current_content=f.current_content, is_in_sync=f.is_in_sync,
                last_synced_at=f.last_synced_at, last_checked_at=f.last_checked_at,
                config_version=f.config_version,
            )
            for f in files
        ],
    )


# ========== AGENT COMMANDS (Ad-hoc operations) ==========

import asyncio


def _build_command_response(agent_uuid: str, cmd) -> schemas.CommandResponse:
    return schemas.CommandResponse(
        id=cmd.id,
        agent_uuid=agent_uuid,
        command_type=cmd.command_type,
        params=cmd.params or {},
        status=cmd.status,
        result=cmd.result,
        error=cmd.error,
        created_at=cmd.created_at,
        picked_at=cmd.picked_at,
        completed_at=cmd.completed_at,
    )


@app.post(
    "/api/v1/agent/{agent_uuid}/exec/read-file",
    response_model=schemas.ReadFileResult,
    tags=["Ad-hoc Commands"],
    summary="Read file from agent (live)",
)
async def exec_read_file(
    agent_uuid: str,
    path: str = Query(..., description="Путь к файлу на хост-машине агента"),
    timeout: int = Query(45, ge=1, le=120, description="Сколько секунд ждать ответа от агента"),
    db: Session = Depends(get_db)
):
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    cmd = crud.create_agent_command(db, agent, command_type="read_file", params={"path": path})
    cmd_id = cmd.id

    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(1.0)
        db.expire_all()
        cmd = crud.get_command(db, cmd_id)
        if cmd and cmd.status in ("done", "failed"):
            break

    result = (cmd.result or {}) if cmd else {}
    return schemas.ReadFileResult(
        file_path=path,
        content=result.get("content"),
        size=result.get("size"),
        status=cmd.status if cmd else "unknown",
        error=cmd.error if cmd else None,
        completed_at=cmd.completed_at if cmd else None,
    )


@app.post(
    "/api/v1/agent/{agent_uuid}/commands",
    response_model=schemas.CommandResponse,
    tags=["Ad-hoc Commands"],
    summary="Queue a generic command for agent",
)
def create_command(
    agent_uuid: str,
    request: schemas.CommandRequest,
    db: Session = Depends(get_db)
):
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    cmd = crud.create_agent_command(db, agent, request.command_type, request.params)
    return _build_command_response(agent_uuid, cmd)


@app.get(
    "/api/v1/agent/{agent_uuid}/commands/{command_id}",
    response_model=schemas.CommandResponse,
    tags=["Ad-hoc Commands"],
    summary="Get command status and result",
)
def get_command_status(agent_uuid: str, command_id: int, db: Session = Depends(get_db)):
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    cmd = crud.get_command(db, command_id)
    if not cmd or cmd.agent_id != agent.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Command not found")

    return _build_command_response(agent_uuid, cmd)


# ----- Внутренние эндпоинты для агента -----

@app.get(
    "/api/v1/agent/{agent_uuid}/commands/pending/list",
    response_model=list[schemas.AgentCommandQueueItem],
    tags=["Ad-hoc Commands"],
    summary="(internal) Fetch pending commands for agent",
    include_in_schema=False,
)
def fetch_pending_commands(agent_uuid: str, db: Session = Depends(get_db)):
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    cmds = crud.get_pending_commands_for_agent(db, agent)
    return [
        schemas.AgentCommandQueueItem(id=c.id, command_type=c.command_type, params=c.params or {})
        for c in cmds
    ]


@app.post(
    "/api/v1/agent/{agent_uuid}/commands/{command_id}/result",
    tags=["Ad-hoc Commands"],
    summary="(internal) Submit command result",
    include_in_schema=False,
)
def submit_command_result(
    agent_uuid: str,
    command_id: int,
    request: schemas.CommandResultRequest,
    db: Session = Depends(get_db)
):
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    cmd = crud.get_command(db, command_id)
    if not cmd or cmd.agent_id != agent.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Command not found")

    crud.complete_command(db, cmd, result=request.result, error=request.error)
    return {"status": "ok"}


# ========== SERVICE PRESETS ==========

@app.get(
    "/api/v1/service-presets",
    response_model=list[schemas.ServicePresetResponse],
    tags=["Service Presets"],
    summary="List all service presets",
)
def list_presets(db: Session = Depends(get_db)):
    return crud.list_service_presets(db)


@app.post(
    "/api/v1/service-presets",
    response_model=schemas.ServicePresetResponse,
    tags=["Service Presets"],
    summary="Create a new service preset",
    status_code=status.HTTP_201_CREATED,
)
def create_preset(request: schemas.ServicePresetCreate, db: Session = Depends(get_db)):
    existing = crud.get_service_preset_by_name(db, request.service)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Preset for service '{request.service}' already exists"
        )
    return crud.create_service_preset(db, **request.model_dump())


@app.get(
    "/api/v1/service-presets/{preset_id}",
    response_model=schemas.ServicePresetResponse,
    tags=["Service Presets"],
    summary="Get service preset by id",
)
def get_preset(preset_id: int, db: Session = Depends(get_db)):
    preset = crud.get_service_preset(db, preset_id)
    if not preset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preset not found")
    return preset


@app.put(
    "/api/v1/service-presets/{preset_id}",
    response_model=schemas.ServicePresetResponse,
    tags=["Service Presets"],
    summary="Update service preset",
)
def update_preset(preset_id: int, request: schemas.ServicePresetUpdate, db: Session = Depends(get_db)):
    preset = crud.get_service_preset(db, preset_id)
    if not preset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preset not found")
    return crud.update_service_preset(db, preset, **request.model_dump(exclude_unset=True))


@app.delete(
    "/api/v1/service-presets/{preset_id}",
    tags=["Service Presets"],
    summary="Delete service preset",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_preset(preset_id: int, db: Session = Depends(get_db)):
    preset = crud.get_service_preset(db, preset_id)
    if not preset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preset not found")
    crud.delete_service_preset(db, preset)
    return None


@app.get(
    "/api/v1/commands",
    response_model=list[schemas.CommandListItem],
    tags=["Ad-hoc Commands"],
    summary="List all commands (global)",
)
def list_commands(
    limit: int = Query(100, ge=1, le=1000, description="Макс. записей"),
    status_filter: Optional[str] = Query(None, description="Фильтр по статусу: pending, running, done, failed"),
    command_type: Optional[str] = Query(None, description="Фильтр по типу команды"),
    db: Session = Depends(get_db),
):
    cmds = crud.list_all_commands(db, limit=limit, status_filter=status_filter, command_type=command_type)
    return [
        schemas.CommandListItem(
            id=c.id,
            agent_uuid=c.agent.uuid,
            agent_hostname=c.agent.hostname,
            agent_family=c.agent.family,
            command_type=c.command_type,
            params=c.params or {},
            status=c.status,
            result=c.result,
            error=c.error,
            created_at=c.created_at,
            picked_at=c.picked_at,
            completed_at=c.completed_at,
        )
        for c in cmds
    ]


@app.get(
    "/api/v1/agent/{agent_uuid}/commands",
    response_model=list[schemas.CommandResponse],
    tags=["Ad-hoc Commands"],
    summary="List commands for an agent",
)
def list_agent_commands_endpoint(
    agent_uuid: str,
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    cmds = crud.list_agent_commands(db, agent, limit=limit, status_filter=status_filter)
    return [_build_command_response(agent_uuid, c) for c in cmds]


@app.get(
    "/api/v1/history",
    response_model=list[schemas.GlobalHistoryRecord],
    tags=["History & Monitoring"],
    summary="Get global config application history",
)
def get_global_history(
    limit: int = Query(200, ge=1, le=2000, description="Макс. записей"),
    success: Optional[bool] = Query(None, description="Фильтр"),
    family: Optional[str] = Query(None, description="Фильтр по семье"),
    db: Session = Depends(get_db),
):
    records = crud.list_all_config_history(db, limit=limit, success_filter=success, family=family)
    return [
        schemas.GlobalHistoryRecord(
            id=h.id,
            agent_uuid=h.agent.uuid,
            agent_hostname=h.agent.hostname,
            agent_family=h.agent.family,
            config_version=h.config_version,
            applied_at=h.applied_at,
            success=h.success,
            error=h.error,
            applied_by=h.applied_by,
            duration_seconds=h.duration_seconds,
        )
        for h in records
    ]


@app.put(
    "/api/v1/family/{family}/rename",
    response_model=schemas.FamilyOperationResponse,
    tags=["Family Management"],
    summary="Rename family",
)
def rename_family(family: str, request: schemas.FamilyRenameRequest, db: Session = Depends(get_db)):
    if family == request.new_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="new_name совпадает со старым")

    agents = crud.get_agents_by_family(db, family)
    if not agents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Family '{family}' not found")

    count = crud.rename_family(db, family, request.new_name)
    return schemas.FamilyOperationResponse(
        family=request.new_name,
        agents_affected=count,
        message=f"Renamed family '{family}' → '{request.new_name}' ({count} agents)",
    )


@app.delete(
    "/api/v1/family/{family}",
    response_model=schemas.FamilyOperationResponse,
    tags=["Family Management"],
    summary="Delete family and all its agents",
)
def delete_family(family: str, db: Session = Depends(get_db)):
    agents = crud.get_agents_by_family(db, family)
    if not agents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Family '{family}' not found")

    count = crud.delete_family(db, family)
    return schemas.FamilyOperationResponse(
        family=family,
        agents_affected=count,
        message=f"Deleted family '{family}' ({count} agents removed)",
    )


@app.put(
    "/api/v1/agent/{agent_uuid}/family",
    response_model=schemas.AgentResponse,
    tags=["Agent Management"],
    summary="Change agent family",
)
def change_agent_family(
    agent_uuid: str,
    request: schemas.AgentFamilyUpdateRequest,
    db: Session = Depends(get_db),
):
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    crud.update_agent_family(db, agent, request.family)
    return schemas.AgentResponse(
        uuid=agent.uuid,
        family=agent.family,
        hostname=agent.hostname,
        version=agent.version,
        last_seen=agent.last_seen,
        created_at=agent.created_at,
        last_applied_version=agent.last_applied_version,
        last_error=agent.last_error,
        last_reported_at=agent.last_reported_at,
    )


@app.put(
    "/api/v1/agents/bulk-family",
    response_model=schemas.AgentsBulkResponse,
    tags=["Agent Management"],
    summary="Bulk change family for selected agents",
)
def bulk_change_family(request: schemas.AgentsBulkFamilyUpdate, db: Session = Depends(get_db)):
    updated, not_found = crud.bulk_update_agents_family(db, request.uuids, request.family)
    return schemas.AgentsBulkResponse(updated=updated, not_found=not_found)


@app.post(
    "/api/v1/agent/{agent_uuid}/config/{version}/rollback",
    response_model=schemas.MultiConfigResponse,
    tags=["Configuration"],
    summary="Rollback to a previous config version",
)
def rollback_agent_config(agent_uuid: str, version: int, db: Session = Depends(get_db)):
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    target = crud.get_config_by_version(db, agent, version)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config version {version} not found",
        )

    desired = target.desired_config
    if isinstance(desired, dict) and "configs" in desired:
        payloads = list(desired["configs"])
    else:
        payloads = [desired]

    new_config = crud.create_agent_configs_bulk(db, agent, payloads)

    return schemas.MultiConfigResponse(
        created=[schemas.ConfigResponse(config=new_config.desired_config, version=new_config.version)],
        total=len(payloads),
    )



@app.post(
    "/api/v1/agent/{agent_uuid}/exec/list-dir",
    response_model=schemas.ListDirResult,
    tags=["Ad-hoc Commands"],
    summary="List directory contents on agent",
)
async def exec_list_dir(
    agent_uuid: str,
    path: str = Query("/", description="Путь к директории на хост-машине агента"),
    timeout: int = Query(45, ge=1, le=120, description="Сколько секунд ждать ответа от агента"),
    db: Session = Depends(get_db),
):
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    cmd = crud.create_agent_command(db, agent, command_type="list_dir", params={"path": path})
    cmd_id = cmd.id

    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(1.0)
        db.expire_all()
        cmd = crud.get_command(db, cmd_id)
        if cmd and cmd.status in ("done", "failed"):
            break

    result = (cmd.result or {}) if cmd else {}
    entries = result.get("entries", [])

    return schemas.ListDirResult(
        path=result.get("path", path),
        entries=[schemas.DirEntry(**e) for e in entries],
        total=result.get("total"),
        status=cmd.status if cmd else "unknown",
        error=cmd.error if cmd else None,
        completed_at=cmd.completed_at if cmd else None,
    )
