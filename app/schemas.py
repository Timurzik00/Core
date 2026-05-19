from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class AgentInfo(BaseModel):
    family: str
    hostname: str
    version: str


class AgentRegisterRequest(BaseModel):
    agent: AgentInfo


class AgentRegisterResponse(BaseModel):
    status: int = 0
    error: str = ""
    uuid: str


class ConfigPayload(BaseModel):
    family: Optional[str]
    cli: Optional[dict]
    file: Optional[dict]


class ConfigRequest(BaseModel):
    config: ConfigPayload


class ConfigResponse(BaseModel):
    config: ConfigPayload
    version: int


class AgentStatusRequest(BaseModel):
    last_applied_version: Optional[int] = Field(
        None,
        example=1,
        description="Последняя версия desired-конфига, которую агент успешно применил",
    )
    last_error: Optional[str] = Field(
        None,
        example=None,
        description="Текст ошибки, если что-то пошло не так при применении",
    )
    current_snapshot: Optional[dict] = Field(
        None,
        description="Расширенный снимок конфига на агенте для мониторинга дрейфа",
    )


class AgentResponse(BaseModel):
    uuid: str
    family: str
    hostname: str
    version: str
    last_seen: Optional[datetime]
    last_applied_version: Optional[int] = None
    last_error: Optional[str] = None
    last_reported_at: Optional[datetime] = None


class AgentsListResponse(BaseModel):
    agents: list[AgentResponse]
    total: Optional[int] = None
    limit: Optional[int] = None
    offset: Optional[int] = None


# ========== HISTORY & SNAPSHOT ==========

class ConfigHistoryRecord(BaseModel):
    id: int
    config_version: int
    applied_at: datetime
    success: bool
    error: Optional[str]
    applied_by: str
    duration_seconds: Optional[int]

    class Config:
        from_attributes = True


class FileContentResponse(BaseModel):
    """Содержимое файла (как cat)"""
    file_path: str
    content: Optional[str] = None
    size: Optional[int] = None
    content_type: str = "text/plain"
    error: Optional[str] = None
    last_updated: Optional[datetime] = None


class ManagedFileInfo(BaseModel):
    """Информация об управляемом файле"""
    id: int
    file_path: str
    desired_content: Optional[str] = None
    current_content: Optional[str] = None
    is_in_sync: bool
    last_synced_at: Optional[datetime] = None
    last_checked_at: Optional[datetime] = None
    config_version: Optional[int] = None

    class Config:
        from_attributes = True


class ManagedFilesDiff(BaseModel):
    """Различие между желаемым и текущим состоянием файла"""
    file_path: str
    desired_content: Optional[str] = None
    current_content: Optional[str] = None
    is_in_sync: bool
    differences: list[str] = []


class AgentConfigSnapshotResponse(BaseModel):
    """Расширенный снимок конфига агента"""
    id: int
    snapshot: dict
    config_version: Optional[int] = None
    captured_at: datetime
    has_drift: bool = False
    drift_summary: Optional[str] = None

    class Config:
        from_attributes = True


class AgentDetailedResponse(BaseModel):
    uuid: str
    family: str
    hostname: str
    version: str
    last_seen: Optional[datetime]
    last_applied_version: Optional[int] = None
    last_error: Optional[str] = None
    last_reported_at: Optional[datetime] = None
    current_snapshot: Optional[AgentConfigSnapshotResponse] = None
    recent_history: list[ConfigHistoryRecord] = []


class FamilyAgentsResponse(BaseModel):
    family: str
    count: int
    agents: list[AgentResponse]


class FamilyHistoryResponse(BaseModel):
    family: str
    history: list[ConfigHistoryRecord]


class FamilyFilesStatusResponse(BaseModel):
    """Статус управляемых файлов для всего семейства"""
    family: str
    total_files: int
    synced_files: int
    out_of_sync_files: int
    files: list[ManagedFileInfo]


class ConfigVersionInfo(BaseModel):
    """Информация о версии конфига"""
    version: int
    created_at: datetime
    config: dict
    applications: list[ConfigHistoryRecord] = []


class ErrorResponse(BaseModel):
    status: int = 1
    error: str