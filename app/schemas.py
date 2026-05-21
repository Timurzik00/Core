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
    family: Optional[str] = None
    cli: Optional[dict] = None
    file: Optional[dict] = None
 
 
# ── Запрос на создание конфига ──
class ConfigRequest(BaseModel):
    # Старый формат: один конфиг
    config: Optional[ConfigPayload] = None
    # Новый формат: массив конфигов
    configs: Optional[list[ConfigPayload]] = None
 
    def get_payloads(self) -> list[ConfigPayload]:
        """Всегда возвращает список, независимо от того, что пришло."""
        if self.configs:
            return self.configs
        if self.config:
            return [self.config]
        return []
 
 
class ConfigResponse(BaseModel):
    # config возвращается как сырой dict чтобы поддерживать
    # и одиночный формат {"family":..., "file":..., "cli":...}
    # и мультиформат {"configs": [...]}
    config: Optional[dict] = None
    version: int
 
 
# Ответ при создании нескольких конфигов сразу
class MultiConfigResponse(BaseModel):
    created: list[ConfigResponse]
    total: int
 
 
class AgentStatusRequest(BaseModel):
    last_applied_version: Optional[int] = Field(
        None,
        description="Последняя версия desired-конфига, которую агент успешно применил",
    )
    last_error: Optional[str] = Field(
        None,
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
    file_path: str
    content: Optional[str] = None
    size: Optional[int] = None
    content_type: str = "text/plain"
    error: Optional[str] = None
    last_updated: Optional[datetime] = None
 
 
class ManagedFileInfo(BaseModel):
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
    file_path: str
    desired_content: Optional[str] = None
    current_content: Optional[str] = None
    is_in_sync: bool
    differences: list[str] = []
 
 
class AgentConfigSnapshotResponse(BaseModel):
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
    family: str
    total_files: int
    synced_files: int
    out_of_sync_files: int
    files: list[ManagedFileInfo]
 
 
class ConfigVersionInfo(BaseModel):
    version: int
    created_at: datetime
    config: dict
    applications: list[ConfigHistoryRecord] = []
 
 
# ========== FAMILY CONFIG PUSH ==========
 
class FamilyConfigPushRequest(BaseModel):
    """
    Пуш одного или нескольких конфигов сразу на всю семью.
    Поле family в каждом ConfigPayload игнорируется — берётся из URL.
    """
    configs: list[ConfigPayload] = Field(
        ...,
        description="Список конфигов для применения на всех агентах семейства",
        min_length=1,
    )
 
 
class FamilyConfigPushResult(BaseModel):
    """Результат пуша для одного агента"""
    agent_uuid: str
    hostname: str
    versions_created: list[int]
    error: Optional[str] = None
 
 
class FamilyConfigPushResponse(BaseModel):
    family: str
    agents_updated: int
    agents_failed: int
    results: list[FamilyConfigPushResult]
 
 
class ErrorResponse(BaseModel):
    status: int = 1
    error: str
 
