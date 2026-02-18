"""API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ModelInfo(BaseModel):
    type: str
    provider: str


class SummaryResponse(BaseModel):
    summary: str
    model_info: ModelInfo
    summary_id: str
    created_at: datetime


class BatchSummaryItem(BaseModel):
    filename: str
    summary: str
    summary_id: str
    created_at: datetime


class BatchSummaryResponse(BaseModel):
    summaries: list[BatchSummaryItem]
    model_info: ModelInfo


class SummaryListItem(BaseModel):
    id: str
    title: Optional[str]
    summary: str
    created_at: datetime


class SummaryListResponse(BaseModel):
    items: list[SummaryListItem]
    total: int
    limit: int
    offset: int




class ExportSummaryItem(BaseModel):
    id: str
    title: Optional[str]
    summary: str
    source_type: str
    source_value: Optional[str]
    model_type: str
    provider: str
    num_sentences: int
    created_at: datetime


class ExportSummariesResponse(BaseModel):
    items: list[ExportSummaryItem]
    total: int
    limit: int
    offset: int

class SummaryDetailResponse(BaseModel):
    id: str
    title: Optional[str]
    summary: str
    source_type: str
    source_value: Optional[str]
    model_type: str
    provider: str
    num_sentences: int
    created_at: datetime


class EvidenceItem(BaseModel):
    id: str
    claim: str
    evidence: str
    location: Optional[str]
    created_at: datetime


class EvidenceCreate(BaseModel):
    claim: str
    evidence: str
    location: Optional[str] = None


class EvidenceUpdate(BaseModel):
    claim: Optional[str] = None
    evidence: Optional[str] = None
    location: Optional[str] = None


class EvidenceListResponse(BaseModel):
    summary_id: str
    items: list[EvidenceItem]




class UserSettingsResponse(BaseModel):
    defaultModel: str
    summaryLength: int
    citationHandling: str
    autoSave: bool


class UserSettingsUpdateRequest(BaseModel):
    defaultModel: str
    summaryLength: int
    citationHandling: str
    autoSave: bool


class StorageUsageResponse(BaseModel):
    usedBytes: int
    maxBytes: int
    usedPercent: int
    summaryCount: int

class SynthesisRequest(BaseModel):
    summary_ids: list[str]


class SynthesisResponse(BaseModel):
    consensus: str
    disagreements: list[str]
    sources: list[str]
    citations: list[dict]


class JobSummaryRequest(BaseModel):
    source_type: str
    url: Optional[str] = None
    text: Optional[str] = None
    num_sentences: Optional[int] = None
    model_type: Optional[str] = None
    provider: Optional[str] = None
    keep_citations: bool = False


class JobCreateResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[dict] = None
    error: Optional[str] = None
