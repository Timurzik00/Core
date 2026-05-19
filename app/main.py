from fastapi import FastAPI, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session
from app import crud, database, schemas
from app.database import SessionLocal, init_db
import difflib
from datetime import datetime
from typing import Optional

app = FastAPI(
    title="GAIA Core",
    description="Configuration management system for agents with history tracking and drift detection",
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

@app.get("/api/v1/health", tags=["System"], response_model=dict)
def health_check():
    """
    Check if the GAIA Core server is running and healthy.
    
    Returns:
    - status: "healthy" if all systems operational
    - timestamp: current server time
    - version: API version
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0"
    }


@app.get("/api/v1/info", tags=["System"], response_model=dict)
def get_api_info():
    """
    Get information about GAIA Core API.
    
    Returns:
    - title: System name
    - version: API version
    - description: What this API does
    - base_url: Base URL for all API endpoints
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
    responses={
        200: {"description": "Agent registered successfully"},
        400: {"description": "Invalid agent data"},
    }
)
def register_agent(request: schemas.AgentRegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new agent in GAIA Core.
    
    The agent will receive a unique UUID that should be stored and reused on subsequent runs.
    
    **Request body:**
    - family: Agent family/type (e.g., "coroot", "zabbix", "prometheus")
    - hostname: Agent hostname/server name
    - version: Agent software version
    
    **Response:**
    - uuid: Unique identifier for this agent (SAVE THIS!)
    
    **Example:**
    ```bash
    curl -X POST http://localhost:8000/api/v1/agent/register \\
      -H "Content-Type: application/json" \\
      -d '{
        "agent": {
          "family": "coroot",
          "hostname": "my-server",
          "version": "v1.0"
        }
      }'
    ```
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
    family: Optional[str] = Query(None, description="Filter by agent family (e.g., 'coroot')"),
    hostname: Optional[str] = Query(None, description="Search by hostname (partial match)"),
    sort_by: Optional[str] = Query("last_seen", description="Sort by: last_seen, created_at, hostname"),
    order: Optional[str] = Query("desc", description="Sort order: asc or desc"),
    limit: Optional[int] = Query(100, ge=1, le=1000, description="Max results"),
    offset: Optional[int] = Query(0, ge=0, description="Skip N results (pagination)"),
):
    """
    List all registered agents with optional filtering and pagination.
    
    **Query parameters:**
    - family: Filter by agent family (e.g., ?family=coroot)
    - hostname: Search by hostname (partial, e.g., ?hostname=server-01)
    - sort_by: Sort field (last_seen, created_at, hostname)
    - order: asc or desc
    - limit: Max results (default 100, max 1000)
    - offset: Skip N results for pagination
    
    **Examples:**
    ```bash
    # Get all coroot agents
    curl "http://localhost:8000/api/v1/agents?family=coroot"
    
    # Search by hostname
    curl "http://localhost:8000/api/v1/agents?hostname=server"
    
    # Pagination
    curl "http://localhost:8000/api/v1/agents?limit=10&offset=0"
    
    # Sort by creation date, oldest first
    curl "http://localhost:8000/api/v1/agents?sort_by=created_at&order=asc"
    ```
    """
    query = crud.get_all_agents(db)
    
    # Filter by family
    if family:
        query = [a for a in query if a.family == family]
    
    # Search by hostname
    if hostname:
        query = [a for a in query if hostname.lower() in a.hostname.lower()]
    
    # Sort
    if sort_by == "hostname":
        query = sorted(query, key=lambda x: x.hostname, reverse=(order == "desc"))
    elif sort_by == "created_at":
        query = sorted(query, key=lambda x: x.created_at, reverse=(order == "desc"))
    else:  # last_seen
        query = sorted(query, key=lambda x: x.last_seen, reverse=(order == "desc"))
    
    # Pagination
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
    """
    Get detailed information about a specific agent.
    
    Includes:
    - Agent metadata (family, hostname, version)
    - Current status (last_seen, last_applied_version, errors)
    - Current configuration snapshot
    - Recent configuration application history
    
    **Example:**
    ```bash
    curl http://localhost:8000/api/v1/agent/96828b90-855b-4d58-9b8c-1d62b344de41
    ```
    """
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
    responses={
        204: {"description": "Agent deleted successfully"},
        404: {"description": "Agent not found"},
    }
)
def delete_agent(agent_uuid: str, db: Session = Depends(get_db)):
    """
    Delete an agent and all its associated data.
    
    **WARNING:** This will delete:
    - Agent record
    - All configuration history
    - All snapshots
    - All managed file records
    
    This action cannot be undone!
    
    **Example:**
    ```bash
    curl -X DELETE http://localhost:8000/api/v1/agent/96828b90-855b-4d58-9b8c-1d62b344de41
    ```
    """
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    crud.delete_agent(db, agent)
    return None


# ========== CONFIGURATION ==========

@app.post(
    "/api/v1/agent/{agent_uuid}/config",
    response_model=schemas.ConfigResponse,
    tags=["Configuration"],
    summary="Set agent configuration",
)
def set_agent_config(
    agent_uuid: str,
    request: schemas.ConfigRequest,
    db: Session = Depends(get_db)
):
    """
    Set or update the desired configuration for an agent.
    
    Configuration can include:
    - **file**: Write a file to disk
    - **cli**: Execute a command
    - **family**: Optional family specification
    
    A new version number is automatically assigned.
    
    **Request body example:**
    ```json
    {
      "config": {
        "family": "coroot",
        "file": {
          "path": "/etc/coroot/config.yaml",
          "content": "server: localhost\\nport: 8080"
        },
        "cli": {
          "binary": "/usr/bin/docker",
          "args": "restart coroot-agent"
        }
      }
    }
    ```
    
    **Response:**
    - version: New config version number
    - config: The configuration that was set
    """
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    config = crud.create_agent_config(db, agent, request.config.model_dump())
    return schemas.ConfigResponse(config=config.desired_config, version=config.version)


@app.get(
    "/api/v1/agent/{agent_uuid}/config",
    response_model=schemas.ConfigResponse,
    tags=["Configuration"],
    summary="Get current desired configuration",
)
def get_agent_config(agent_uuid: str, db: Session = Depends(get_db)):
    """
    Get the current desired configuration for an agent.
    
    This is what the agent should be running.
    """
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    config = crud.get_latest_config_by_agent(db, agent)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")

    crud.update_agent_last_seen(db, agent)
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
    """
    Get a specific configuration version and its application history.
    
    Shows when this configuration version was applied and whether it succeeded.
    """
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
    include_in_schema=False,  # Internal endpoint, not for manual use
)
def report_agent_status(
    agent_uuid: str,
    request: schemas.AgentStatusRequest,
    db: Session = Depends(get_db)
):
    """Internal endpoint called by agents to report status. Do not use manually."""
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    if request.current_snapshot:
        config_version = agent.last_applied_version
        files_info = request.current_snapshot.get("files", {})

    # Достаём desired_content из текущего конфига агента
        latest_config = crud.get_latest_config_by_agent(db, agent)
        desired_file_content = None
        if latest_config and latest_config.desired_config.get("file"):
            desired_file_content = latest_config.desired_config["file"].get("content")

        for file_path, file_data in files_info.items():
            crud.save_managed_file(
                db,
                agent,
                file_path=file_path,
                desired_content=desired_file_content,
                current_content=file_data.get("content"),
                config_version=config_version,
                is_in_sync=file_data.get("is_in_sync", False),
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
        last_applied_version=agent.last_applied_version,
        last_error=agent.last_error,
        last_reported_at=agent.last_reported_at,
    )


# ========== FILE MANAGEMENT ==========

@app.get(
    "/api/v1/agent/{agent_uuid}/file",
    response_model=schemas.FileContentResponse,
    tags=["File Management"],
    summary="Read file content (like 'cat')",
)
def get_agent_file(
    agent_uuid: str,
    path: str = Query(..., description="File path to read"),
    db: Session = Depends(get_db)
):
    """
    Read the content of a file on the agent (like 'cat' in terminal).
    
    **Example:**
    ```bash
    curl "http://localhost:8000/api/v1/agent/96828b90.../file?path=/etc/config.conf"
    ```
    """
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    managed_file = crud.get_managed_file(db, agent, path)
    if not managed_file or not managed_file.current_content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File '{path}' not found or not tracked"
        )

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
    summary="View file differences (like 'diff')",
)
def get_file_diff(
    agent_uuid: str,
    path: str = Query(..., description="File path to compare"),
    db: Session = Depends(get_db)
):
    """
    View differences between desired and current file content (like 'diff').
    
    **Example:**
    ```bash
    curl "http://localhost:8000/api/v1/agent/.../file-diff?path=/etc/config.conf"
    ```
    """
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    managed_file = crud.get_managed_file(db, agent, path)
    if not managed_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File '{path}' not found"
        )

    desired = (managed_file.desired_content or "").splitlines(keepends=True)
    current = (managed_file.current_content or "").splitlines(keepends=True)

    diff = list(difflib.unified_diff(desired, current, fromfile="desired", tofile="current", lineterm=""))
    differences = [line.rstrip() for line in diff]

    return schemas.ManagedFilesDiff(
        file_path=path,
        desired_content=managed_file.desired_content,
        current_content=managed_file.current_content,
        is_in_sync=managed_file.is_in_sync,
        differences=differences,
    )


@app.get(
    "/api/v1/agent/{agent_uuid}/files",
    response_model=list[schemas.ManagedFileInfo],
    tags=["File Management"],
    summary="List all managed files",
)
def get_agent_managed_files(agent_uuid: str, db: Session = Depends(get_db)):
    """
    Get all files managed by GAIA Core on this agent.
    """
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    files = crud.get_agent_managed_files(db, agent)
    return [
        schemas.ManagedFileInfo(
            id=f.id,
            file_path=f.file_path,
            desired_content=f.desired_content,
            current_content=f.current_content,
            is_in_sync=f.is_in_sync,
            last_synced_at=f.last_synced_at,
            last_checked_at=f.last_checked_at,
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
    """
    Get files that differ from desired state (drift detection).
    """
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    files = crud.get_out_of_sync_files(db, agent)
    if not files:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="All files are in sync")

    return [
        schemas.ManagedFileInfo(
            id=f.id,
            file_path=f.file_path,
            desired_content=f.desired_content,
            current_content=f.current_content,
            is_in_sync=f.is_in_sync,
            last_synced_at=f.last_synced_at,
            last_checked_at=f.last_checked_at,
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
    limit: int = Query(50, ge=1, le=1000, description="Max results"),
    db: Session = Depends(get_db)
):
    """
    Get the history of all configuration applications on this agent.
    """
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    history = crud.get_config_history(db, agent, limit=limit)
    return [
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
    ]


@app.get(
    "/api/v1/agent/{agent_uuid}/history/failed",
    response_model=list[schemas.ConfigHistoryRecord],
    tags=["History & Monitoring"],
    summary="Get failed application attempts",
)
def get_agent_failed_history(
    agent_uuid: str,
    limit: int = Query(50, ge=1, le=1000, description="Max results"),
    db: Session = Depends(get_db)
):
    """
    Get only the failed configuration applications.
    Useful for debugging and error analysis.
    """
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    history = crud.get_failed_config_applications(db, agent, limit=limit)
    return [
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
    ]


@app.get(
    "/api/v1/agent/{agent_uuid}/snapshot",
    response_model=schemas.AgentConfigSnapshotResponse,
    tags=["History & Monitoring"],
    summary="Get current agent snapshot",
)
def get_agent_current_snapshot(agent_uuid: str, db: Session = Depends(get_db)):
    """
    Get the current snapshot of agent state including files, CLI results, and drift status.
    """
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    snapshot = crud.get_latest_agent_config_snapshot(db, agent)
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No snapshot found")

    return schemas.AgentConfigSnapshotResponse(
        id=snapshot.id,
        snapshot=snapshot.snapshot,
        config_version=snapshot.config_version,
        captured_at=snapshot.captured_at,
        has_drift=snapshot.has_drift,
        drift_summary=snapshot.drift_summary,
    )


@app.get(
    "/api/v1/agent/{agent_uuid}/snapshots",
    response_model=list[schemas.AgentConfigSnapshotResponse],
    tags=["History & Monitoring"],
    summary="Get snapshot history",
)
def get_agent_snapshots(
    agent_uuid: str,
    limit: int = Query(20, ge=1, le=1000, description="Max results"),
    db: Session = Depends(get_db)
):
    """
    Get the history of agent state snapshots.
    """
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    snapshots = crud.get_agent_config_snapshots(db, agent, limit=limit)
    return [
        schemas.AgentConfigSnapshotResponse(
            id=s.id,
            snapshot=s.snapshot,
            config_version=s.config_version,
            captured_at=s.captured_at,
            has_drift=s.has_drift,
            drift_summary=s.drift_summary,
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
    """
    Get only snapshots where configuration drift was detected.
    """
    agent = crud.get_agent_by_uuid(db, agent_uuid)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    snapshots = crud.get_snapshots_with_drift(db, agent)
    return [
        schemas.AgentConfigSnapshotResponse(
            id=s.id,
            snapshot=s.snapshot,
            config_version=s.config_version,
            captured_at=s.captured_at,
            has_drift=s.has_drift,
            drift_summary=s.drift_summary,
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
    """
    Get all agents that belong to a specific family.
    
    **Example:**
    ```bash
    curl http://localhost:8000/api/v1/family/coroot/agents
    ```
    """
    agents = crud.get_agents_by_family(db, family)
    if not agents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No agents found for family '{family}'")

    return schemas.FamilyAgentsResponse(
        family=family,
        count=len(agents),
        agents=[
            schemas.AgentResponse(
                uuid=agent.uuid,
                family=agent.family,
                hostname=agent.hostname,
                version=agent.version,
                last_seen=agent.last_seen,
            )
            for agent in agents
        ],
    )


@app.get(
    "/api/v1/family/{family}/history",
    response_model=schemas.FamilyHistoryResponse,
    tags=["Family Management"],
    summary="Get family configuration history",
)
def get_family_history(
    family: str,
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    db: Session = Depends(get_db)
):
    """
    Get the combined configuration application history for all agents in a family.
    """
    history = crud.get_family_config_history(db, family, limit=limit)
    if not history:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No history found for family '{family}'")

    return schemas.FamilyHistoryResponse(
        family=family,
        history=[
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


@app.get(
    "/api/v1/family/{family}/files-status",
    response_model=schemas.FamilyFilesStatusResponse,
    tags=["Family Management"],
    summary="Get family file synchronization status",
)
def get_family_files_status(family: str, db: Session = Depends(get_db)):
    """
    Get the synchronization status of all managed files across all agents in a family.
    
    Useful for monitoring configuration drift across your infrastructure.
    """
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
                id=f.id,
                file_path=f.file_path,
                desired_content=f.desired_content,
                current_content=f.current_content,
                is_in_sync=f.is_in_sync,
                last_synced_at=f.last_synced_at,
                last_checked_at=f.last_checked_at,
                config_version=f.config_version,
            )
            for f in files
        ],
    )
