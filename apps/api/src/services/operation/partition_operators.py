"""The people who may author and seal a partition, and how they prove it (ADR-0154).

WHAT WAS WRONG
==============

    ADR-0113 made the sealer a named human who is never the author, and checked it
    on the names typed. Anyone who could run the CLI could type both names. The
    two-person rule was recorded, not enforced.

WHAT THIS ADDS
==============

    An enrolled operator holds a credential only that person knows. Authoring and
    sealing each authenticate the named person against it, and the seal refuses
    when the two acts were done by one operator - by id, not by spelling.

    Enrolment needs a witness: an operator already enrolled, who authenticates and
    is not the person being enrolled. Only the first enrolment has none, and the
    record says so.

    Every enrolment, authoring and seal writes a `PartitionOperatorEvent`, refusals
    included. A refusal is committed on its own before it is raised, so a failed
    attempt leaves a trace even though the act left nothing.

WHAT IT DOES NOT PROVE
======================

    That two operators are two humans. One person who controls enrolment can enrol
    a second identity, and anyone with the database's own credentials can write any
    row. This turns "typed a name" into "knew that person's credential, and someone
    enrolled vouched for them" - a real bar, not proof of personhood. Tying the acts
    to The Office's MFA stays on the backlog.

The credential is never stored, logged, or put in an exception message.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.partition_operator import PartitionOperator, PartitionOperatorEvent

#: scrypt cost. n=2**14, r=8, p=1 is the interactive-login setting: ~50 ms, 16 MiB.
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1
SALT_BYTES = 16
#: A credential shorter than this is refused at enrolment.
MIN_CREDENTIAL_LENGTH = 12

#: Refusal codes on the audit row. The caller is told only that it was refused.
REFUSED_UNKNOWN = "not_enrolled"
REFUSED_WRONG = "credential_did_not_match"
REFUSED_WEAK = "credential_too_short"
REFUSED_ALREADY = "already_enrolled"
REFUSED_NO_WITNESS = "witness_required"
REFUSED_SELF_WITNESS = "witness_is_the_enrollee"
REFUSED_WITNESS_FAILED = "witness_did_not_authenticate"
REFUSED_SAME_OPERATOR = "sealer_is_the_author"
REFUSED_NOT_A_PERSON = "names_no_person"


class OperatorRefused(ValueError):
    """Authentication or enrolment refused. Its message never carries a credential."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


def _key(name: str) -> str:
    return name.strip().lower()


def hash_credential(credential: str) -> str:
    salt = os.urandom(SALT_BYTES)
    digest = hashlib.scrypt(
        credential.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P
    )
    b64 = base64.b64encode
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${b64(salt).decode()}${b64(digest).decode()}"


def credential_matches(credential: str, stored: str) -> bool:
    """Constant-time. A malformed stored hash matches nothing."""
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(
            credential.encode("utf-8"),
            salt=base64.b64decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


async def find_operator(session: AsyncSession, name: str) -> PartitionOperator | None:
    return (
        await session.execute(
            select(PartitionOperator).where(
                func.lower(func.trim(PartitionOperator.name)) == _key(name)
            )
        )
    ).scalar_one_or_none()


def audit(
    session: AsyncSession,
    *,
    act: str,
    claimed_name: str,
    outcome: str,
    operator_id: str | None = None,
    witness_operator_id: str | None = None,
    refusal: str | None = None,
    partition_id: str | None = None,
    venture_id: str | None = None,
) -> None:
    """Add one event to the session. The caller's commit makes it permanent."""
    session.add(
        PartitionOperatorEvent(
            act=act,
            claimedName=claimed_name,
            operatorId=operator_id,
            witnessOperatorId=witness_operator_id,
            outcome=outcome,
            refusal=refusal,
            partitionId=partition_id,
            ventureId=venture_id,
        )
    )


async def refuse(
    session: AsyncSession,
    message: str,
    code: str,
    *,
    act: str,
    claimed_name: str,
    operator_id: str | None = None,
    witness_operator_id: str | None = None,
    partition_id: str | None = None,
    venture_id: str | None = None,
) -> OperatorRefused:
    """Discard anything pending, commit the refusal's audit row alone, and return the error."""
    await session.rollback()
    audit(
        session,
        act=act,
        claimed_name=claimed_name,
        outcome="refused",
        operator_id=operator_id,
        witness_operator_id=witness_operator_id,
        refusal=code,
        partition_id=partition_id,
        venture_id=venture_id,
    )
    await session.commit()
    return OperatorRefused(message, code)


async def authenticate(
    session: AsyncSession,
    name: str,
    credential: str,
    *,
    act: str,
    partition_id: str | None = None,
    venture_id: str | None = None,
) -> PartitionOperator:
    """The enrolled operator `name`, if `credential` is theirs. Otherwise an audited refusal.

    Unknown name and wrong credential read the same to the caller; the audit row tells
    them apart.
    """
    operator = await find_operator(session, name)
    if operator is None or not credential_matches(credential, operator.credentialHash):
        raise await refuse(
            session,
            f"{name!r} could not be authenticated (ADR-0154).",
            REFUSED_WRONG if operator is not None else REFUSED_UNKNOWN,
            act=act,
            claimed_name=name,
            operator_id=operator.id if operator is not None else None,
            partition_id=partition_id,
            venture_id=venture_id,
        )
    return operator


async def enrol_operator(
    session: AsyncSession,
    name: str,
    credential: str,
    *,
    witness_name: str | None = None,
    witness_credential: str | None = None,
) -> str:
    """Enrol `name` with `credential`. Returns the operator id.

    The first operator needs no witness. Every later one needs an enrolled operator,
    not themselves, to authenticate as witness.
    """
    # Imported here: held_out_partition imports this module.
    from src.services.operation.held_out_partition import PartitionRefused, named_human

    try:
        name = named_human(name, "operator")
    except PartitionRefused as exc:
        raise await refuse(
            session, str(exc), REFUSED_NOT_A_PERSON, act="enrol", claimed_name=name or ""
        ) from exc
    if len(credential) < MIN_CREDENTIAL_LENGTH:
        raise await refuse(
            session,
            f"a credential must be at least {MIN_CREDENTIAL_LENGTH} characters.",
            REFUSED_WEAK,
            act="enrol",
            claimed_name=name,
        )
    if await find_operator(session, name) is not None:
        raise await refuse(
            session,
            f"{name!r} is already enrolled.",
            REFUSED_ALREADY,
            act="enrol",
            claimed_name=name,
        )

    witness_id: str | None = None
    anyone = (await session.execute(select(PartitionOperator.id).limit(1))).first()
    if anyone is not None:
        if not witness_name or witness_credential is None:
            raise await refuse(
                session,
                "an enrolled operator must witness this enrolment (ADR-0154).",
                REFUSED_NO_WITNESS,
                act="enrol",
                claimed_name=name,
            )
        if _key(witness_name) == _key(name):
            raise await refuse(
                session,
                "a person cannot witness their own enrolment (ADR-0154).",
                REFUSED_SELF_WITNESS,
                act="enrol",
                claimed_name=name,
            )
        witness = await find_operator(session, witness_name)
        if witness is None or not credential_matches(witness_credential, witness.credentialHash):
            raise await refuse(
                session,
                f"witness {witness_name!r} could not be authenticated (ADR-0154).",
                REFUSED_WITNESS_FAILED,
                act="enrol",
                claimed_name=name,
                witness_operator_id=witness.id if witness is not None else None,
            )
        witness_id = witness.id

    operator = PartitionOperator(
        name=name, credentialHash=hash_credential(credential), witnessedBy=witness_id
    )
    session.add(operator)
    await session.flush()
    audit(
        session,
        act="enrol",
        claimed_name=name,
        outcome="done",
        operator_id=operator.id,
        witness_operator_id=witness_id,
    )
    await session.commit()
    return operator.id


__all__ = [
    "MIN_CREDENTIAL_LENGTH",
    "OperatorRefused",
    "REFUSED_ALREADY",
    "REFUSED_NOT_A_PERSON",
    "REFUSED_NO_WITNESS",
    "REFUSED_SAME_OPERATOR",
    "REFUSED_SELF_WITNESS",
    "REFUSED_UNKNOWN",
    "REFUSED_WEAK",
    "REFUSED_WITNESS_FAILED",
    "REFUSED_WRONG",
    "audit",
    "authenticate",
    "credential_matches",
    "enrol_operator",
    "find_operator",
    "hash_credential",
    "refuse",
]
