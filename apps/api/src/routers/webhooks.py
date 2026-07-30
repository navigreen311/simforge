"""Inbound webhooks (§C.11) — external systems calling into SimForge.

Currently: Linear issue-state changes that close the gap loop. These endpoints are unauthenticated
by role (external callers have no SimForge identity) and instead authenticate by HMAC signature.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.services.reporter.inbound import apply_linear_event, verify_signature

router = APIRouter()


@router.post("/linear")
async def linear_webhook(request: Request, session: AsyncSession = Depends(get_session)) -> dict:
    raw = await request.body()
    signature = request.headers.get("Linear-Signature")
    if not verify_signature(raw, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid Linear-Signature"
        )
    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="malformed JSON body"
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="body must be an object"
        )
    return await apply_linear_event(session, payload)
