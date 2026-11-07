from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Annotated

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import DateTime, JSON, String, Text, UniqueConstraint, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

APP_VERSION = "0.1.0"
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://outcome:outcome_dev_only@localhost:5432/outcome",
)
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./data/uploads"))
MAX_FILE_BYTES = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".csv"}

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_hash", name="uq_org_idempotency"),
    )

    job_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_name: Mapped[str] = mapped_column(String(255), nullable=False)
    schema_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    idempotency_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class FieldDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    description: str
    primary: bool | None = None


class ExtractionSchema(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str = Field(min_length=1)
    fields: dict[str, FieldDefinition] = Field(min_length=1)


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    stage: str | None = None
    created_at: datetime
    updated_at: datetime
    result: dict[str, Any] | None = None
    error: dict[str, str] | None = None


app = FastAPI(title="Outcome Document Extraction Service", version=APP_VERSION)


@app.on_event("startup")
def on_startup() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": APP_VERSION}


@app.post(
    "/jobs",
    response_model=JobStatusResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_job(
    file: Annotated[UploadFile, File(...)],
    schema: Annotated[str, Form(...)],
    webhook_url: Annotated[str | None, Form()] = None,
    organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
) -> JobStatusResponse:
    org_id = organization_id or "default"
    filename = Path(file.filename or "upload").name
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail={"code": "UNSUPPORTED_FILE_TYPE", "message": "Supported types: PDF, DOCX, XLSX and CSV."},
        )

    try:
        parsed_schema = ExtractionSchema.model_validate_json(schema)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_SCHEMA", "message": "Schema must contain a name and a non-empty fields object."},
        ) from exc

    content = await file.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail={"code": "FILE_TOO_LARGE", "message": "Maximum file size is 50 MB."})
    if not content:
        raise HTTPException(status_code=400, detail={"code": "EMPTY_FILE", "message": "Uploaded file is empty."})

    file_hash = hashlib.sha256(content).hexdigest()
    schema_dict = parsed_schema.model_dump(exclude_none=True)
    canonical_schema = json.dumps(schema_dict, sort_keys=True, separators=(",", ":"))
    idempotency_hash = hashlib.sha256(
        f"{file_hash}:{canonical_schema}".encode("utf-8")
    ).hexdigest()

    with SessionLocal() as db:
        existing = db.scalar(
            select(Job).where(
                Job.organization_id == org_id,
                Job.idempotency_hash == idempotency_hash,
            )
        )
        if existing:
            return _to_response(existing)

        job_id = str(uuid.uuid4())
        stored_path = UPLOAD_DIR / f"{job_id}{extension}"
        stored_path.write_bytes(content)
        now = datetime.now(timezone.utc)
        job = Job(
            job_id=job_id,
            organization_id=org_id,
            status="PENDING",
            stage="QUEUED",
            created_at=now,
            updated_at=now,
            filename=filename,
            file_path=str(stored_path),
            file_sha256=file_hash,
            schema_name=parsed_schema.name,
            schema_json=schema_dict,
            webhook_url=webhook_url,
            result=None,
            error=None,
            idempotency_hash=idempotency_hash,
        )
        try:
            db.add(job)
            db.commit()
            db.refresh(job)
        except Exception:
            db.rollback()
            stored_path.unlink(missing_ok=True)
            # A concurrent identical request may have won the unique constraint.
            existing = db.scalar(
                select(Job).where(
                    Job.organization_id == org_id,
                    Job.idempotency_hash == idempotency_hash,
                )
            )
            if existing:
                return _to_response(existing)
            raise
        return _to_response(job)


@app.get("/jobs/{job_id}", response_model=JobStatusResponse, response_model_exclude_none=True)
def get_job(
    job_id: str,
    organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
) -> JobStatusResponse:
    org_id = organization_id or "default"
    with SessionLocal() as db:
        job = db.scalar(
            select(Job).where(Job.job_id == job_id, Job.organization_id == org_id)
        )
        if job is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": "Job not found."},
            )
        return _to_response(job)


def _to_response(job: Job) -> JobStatusResponse:
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        stage=job.stage,
        created_at=job.created_at,
        updated_at=job.updated_at,
        result=job.result if job.status in {"SUCCESS", "PARTIAL"} else None,
        error=job.error,
    )
