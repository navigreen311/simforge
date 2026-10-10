"""Enrolled partition operators for tests (ADR-0154).

`credential_of` gives every name a credential, the same for every spelling the
ADR-0113 comparison treats as one person. `ensure` enrols a name directly, with
no witness: the witness rule has its own tests in `test_partition_operators`.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.partition_operator import PartitionOperator
from src.services.operation.held_out_partition import PartitionRefused, named_human
from src.services.operation.partition_operators import find_operator, hash_credential


def credential_of(name: str) -> str:
    return f"the credential of {name.strip().lower()}"


async def ensure(session: AsyncSession, name: str) -> None:
    """Enrol `name` unless it is enrolled already or names no person."""
    try:
        named_human(name, "operator")
    except PartitionRefused:
        return
    if await find_operator(session, name) is not None:
        return
    session.add(
        PartitionOperator(name=name.strip(), credentialHash=hash_credential(credential_of(name)))
    )
    await session.commit()
