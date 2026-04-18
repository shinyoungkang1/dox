"""
Layer 2 metadata model — extraction provenance, confidence scores, and version history.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _fix_z(ts: str) -> str:
    """Replace trailing 'Z' with '+00:00' for Python 3.10 compat."""
    if ts.endswith("Z"):
        return ts[:-1] + "+00:00"
    return ts


@dataclass
class VersionEntry:
    """A single entry in the version history."""
    timestamp: datetime
    agent: str
    action: str

    def to_dict(self) -> dict:
        return {
            "ts": self.timestamp.isoformat(),
            "agent": self.agent,
            "action": self.action,
        }

    @classmethod
    def from_dict(cls, d: dict) -> VersionEntry:
        ts = d.get("ts", "")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(_fix_z(ts))
        return cls(timestamp=ts, agent=d.get("agent", ""), action=d.get("action", ""))


@dataclass
class Confidence:
    """Per-element confidence scores."""
    overall: float = 0.0
    elements: dict[str, float] = field(default_factory=dict)

    def flagged_elements(self, threshold: float = 0.90) -> dict[str, float]:
        """Return elements with confidence below the threshold."""
        return {k: v for k, v in self.elements.items() if v < threshold}


@dataclass
class Provenance:
    """Extraction provenance information."""
    source_hash: str = ""
    extraction_pipeline: list[str] = field(default_factory=list)


@dataclass
class Metadata:
    """Layer 2 metadata block (---meta ... ---/meta)."""
    extracted_by: str = ""
    extracted_at: datetime | None = None
    confidence: Confidence = field(default_factory=Confidence)
    provenance: Provenance = field(default_factory=Provenance)
    version_history: list[VersionEntry] = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d: dict = {}
        if self.extracted_by:
            d["extracted_by"] = self.extracted_by
        if self.extracted_at:
            d["extracted_at"] = self.extracted_at.isoformat()
        if self.confidence.overall > 0 or self.confidence.elements:
            conf: dict = {}
            if self.confidence.overall > 0:
                conf["overall"] = self.confidence.overall
            conf.update(self.confidence.elements)
            d["confidence"] = conf
        if self.provenance.source_hash or self.provenance.extraction_pipeline:
            prov: dict = {}
            if self.provenance.source_hash:
                prov["source_hash"] = self.provenance.source_hash
            if self.provenance.extraction_pipeline:
                prov["extraction_pipeline"] = self.provenance.extraction_pipeline
            d["provenance"] = prov
        if self.version_history:
            d["version_history"] = [v.to_dict() for v in self.version_history]
        if self.extra:
            d.update(self.extra)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Metadata:
        meta = cls()
        meta.extracted_by = d.get("extracted_by", "")
        ea = d.get("extracted_at")
        if ea:
            meta.extracted_at = datetime.fromisoformat(_fix_z(ea)) if isinstance(ea, str) else ea

        conf_raw = d.get("confidence", {})
        if isinstance(conf_raw, dict):
            meta.confidence.overall = conf_raw.pop("overall", 0.0)
            meta.confidence.elements = {k: float(v) for k, v in conf_raw.items()}

        prov_raw = d.get("provenance", {})
        if isinstance(prov_raw, dict):
            meta.provenance.source_hash = prov_raw.get("source_hash", "")
            meta.provenance.extraction_pipeline = prov_raw.get("extraction_pipeline", [])

        vh_raw = d.get("version_history", [])
        meta.version_history = [VersionEntry.from_dict(v) for v in vh_raw]

        known_keys = {"extracted_by", "extracted_at", "confidence", "provenance", "version_history"}
        meta.extra = {k: v for k, v in d.items() if k not in known_keys}
        return meta
