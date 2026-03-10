import enum
from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


def _utcnow() -> datetime:
    """Return timezone-aware UTC datetime (works with both SQLite and PostgreSQL)."""
    return datetime.now(timezone.utc)


# --- Enums ---


class NodeType(str, enum.Enum):
    START = "start"
    END = "end"
    NORMAL = "normal"


# --- SQLAlchemy ORM Models ---


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    twilio_phone_number: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    nodes: Mapped[list["Node"]] = relationship(
        back_populates="scenario",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    edges: Mapped[list["Edge"]] = relationship(
        back_populates="scenario",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE")
    )
    label: Mapped[str] = mapped_column(String(255))
    script: Mapped[str] = mapped_column(Text, default="")
    node_type: Mapped[NodeType] = mapped_column(default=NodeType.NORMAL)
    position_x: Mapped[float] = mapped_column(default=0.0)
    position_y: Mapped[float] = mapped_column(default=0.0)

    scenario: Mapped["Scenario"] = relationship(back_populates="nodes")
    audio_cache: Mapped["AudioCache | None"] = relationship(
        back_populates="node", uselist=False, lazy="selectin"
    )


class Edge(Base):
    __tablename__ = "edges"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE")
    )
    source_node_id: Mapped[str] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE")
    )
    target_node_id: Mapped[str] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE")
    )
    condition_label: Mapped[str] = mapped_column(Text)

    scenario: Mapped["Scenario"] = relationship(back_populates="edges")


class AudioCache(Base):
    __tablename__ = "audio_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    node_id: Mapped[str] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE"), unique=True
    )
    file_path: Mapped[str] = mapped_column(String(500))
    format: Mapped[str] = mapped_column(String(20), default="mulaw")
    script_hash: Mapped[str] = mapped_column(String(64))
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    node: Mapped["Node"] = relationship(back_populates="audio_cache")


# --- Pydantic Schemas ---


class NodeSchema(BaseModel):
    id: str
    label: str
    script: str = ""
    node_type: NodeType = NodeType.NORMAL
    position_x: float = 0.0
    position_y: float = 0.0
    has_audio: bool = False

    model_config = {"from_attributes": True}


class EdgeSchema(BaseModel):
    id: str
    source_node_id: str
    target_node_id: str
    condition_label: str

    model_config = {"from_attributes": True}


class ScenarioCreate(BaseModel):
    name: str
    description: str | None = None
    twilio_phone_number: str | None = None


class ScenarioUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    twilio_phone_number: str | None = None


class ScenarioListItem(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScenarioResponse(BaseModel):
    id: int
    name: str
    description: str | None
    twilio_phone_number: str | None
    nodes: list[NodeSchema]
    edges: list[EdgeSchema]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BatchNodesUpdate(BaseModel):
    nodes: list[NodeSchema]


class BatchEdgesUpdate(BaseModel):
    edges: list[EdgeSchema]


class AudioGenerationResult(BaseModel):
    generated: int
    skipped: int
    errors: list[dict]


class BranchDecisionResult(BaseModel):
    matched_condition: str
    target_node_id: str
    confidence: float
