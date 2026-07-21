"""Evidence bundling + storage (blueprint §C.5 evidence, §G.3). Dev = local filesystem."""

from src.services.evidence.storage import store_evidence_bundle

__all__ = ["store_evidence_bundle"]
