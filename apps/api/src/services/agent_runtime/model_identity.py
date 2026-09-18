"""What answered the exam, in enough detail to re-sit it — and to know when it must be re-sat.

WHY A NAME IS NOT AN IDENTITY
=============================

`agent_model` records `ollama/llama3.1:8b`. That is a *request*, not a candidate. The same tag can
be re-pulled at a different quantization, the same weights can be served at temperature 0.0 or 0.7,
and a certification earned under one reads as current under the other. ADR-0054 closed the gap
between "the provider we configured" and "the provider that answered"; this closes the gap between
the model's NAME and the model.

**Ivan's ruling, 17 September 2026:** a certification counts only if it was earned on the exact
model the agent runs in production — model name, model file including its size and quantization,
and the generation settings. All of it is recorded on every result, and a change to any of the
three means re-certification.

WHAT EACH FIELD IS, AND WHY IT IS SEPARATE FROM THE NEXT
========================================================

    model             what the SERVER said answered, never what was asked for
    file_digest       the model FILE - Ollama's blob sha256. Two pulls of one tag can differ here
    file_size_bytes   the file's size. Recorded beside the digest rather than trusted from the tag
    parameter_size    "8.0B" - the model's scale, which the file size alone does not give
    quantization      "Q4_K_M". The same weights at a different quantization are a different exam
    settings          temperature, top_p, seed, token cap - what was actually SENT, not defaults

`fingerprint` is the whole of it hashed once, so re-certification is a string comparison rather
than a field-by-field argument nobody will write the same way twice.

THE ONE THING THIS CANNOT DO, STATED SO IT IS NOT ASSUMED
=========================================================

It records what SimForge examined. It cannot say whether that matches production, because SimForge
cannot read the Village's model configuration - `config.yaml`'s `mate.ollama_model_routes` lives in
another repository and reaches this one through no seam. So `fingerprint` makes the comparison
COMPUTABLE and does not perform it. The missing half is named in the report, not implied by a
field name here.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True, slots=True)
class ModelIdentity:
    """The candidate, recorded so the exam could be re-sat and so drift is detectable."""

    provider: str
    model: str
    file_digest: str | None = None
    file_size_bytes: int | None = None
    parameter_size: str | None = None
    quantization: str | None = None
    settings: dict = field(default_factory=dict)

    @property
    def has_model_file(self) -> bool:
        """Whether something with a model file on this machine answered.

        A cloud provider has none, and cannot have one: the weights are not here. Ivan's ruling
        keeps a cloud provider available for practice runs and future use, so this is not an error
        condition — it is the fact that decides whether a result is a certification or a rehearsal.
        """
        return bool(self.file_digest)

    @property
    def fingerprint(self) -> str:
        """A stable hash over every field. What a re-certification check compares.

        Sorted keys and a compact separator, for the reason every canonicalisation in this repo
        gives: two writers must produce the same bytes for the same facts, or the comparison
        becomes an argument about formatting.

        **The settings are IN the hash.** The ruling names them alongside the file, and leaving
        them out would make a temperature change invisible to exactly the check that exists to
        catch it.
        """
        payload = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def as_dict(self) -> dict:
        """The wire and storage form. `fingerprint` is NOT in it — it is derived from it, and a
        record carrying its own hash invites the two disagreeing."""
        return asdict(self)

    def as_record(self) -> dict:
        """What is persisted and reported: the fields plus the fingerprint they produce."""
        return {**self.as_dict(), "fingerprint": self.fingerprint}

    @classmethod
    def from_record(cls, record: dict | None) -> ModelIdentity | None:
        """Rebuild from a stored or received record, ignoring a carried `fingerprint`.

        Recomputed rather than trusted. A record whose stored hash did not match its fields would
        otherwise be believed on the strength of the field nobody checked.
        """
        if not record:
            return None
        known = {f for f in cls.__slots__}
        return cls(**{k: v for k, v in record.items() if k in known})


def identity_is_complete(record: dict | None) -> list[str]:
    """Which of the ruling's facts a record is missing. Empty list means it names all of them.

    Returned as a LIST rather than a boolean so a refusal can say which fact is absent. A caller
    told only that the identity is incomplete has to go and find out which half of it to fix, and
    the three facts come from three different places.

    `settings` counts as present when it is a non-empty mapping: an empty one is the accidental
    empty this repo refuses everywhere else — it cannot be told from "no settings were sent", and
    something is always sent.
    """
    identity = ModelIdentity.from_record(record)
    if identity is None:
        return ["model_identity"]
    missing = []
    if not identity.model:
        missing.append("model_identity.model")
    if not identity.file_digest:
        missing.append("model_identity.file_digest")
    if not identity.quantization:
        missing.append("model_identity.quantization")
    if not identity.settings:
        missing.append("model_identity.settings")
    return missing


__all__ = ["ModelIdentity", "identity_is_complete"]
