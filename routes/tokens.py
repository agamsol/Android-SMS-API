import os
import hashlib
from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from models.authentication import (
    AdditionalAccountData, CreateTokenRequest, TokenResponse,
    TokenStats, UpdateTokenRequest, generate_random_password
)
from utils.models.database import APITokenInDB
from utils.secure import JWToken, Hash
from utils.database import SQLiteDb
from routes.authentication import authenticate_with_token

DATABASE_PATH = os.getenv("DATABASE_PATH", "data/Android-SMS-API.db")
db_helper = SQLiteDb(database_path=DATABASE_PATH)
database = db_helper.connect()

router = APIRouter(prefix="/auth/tokens", tags=["API Tokens"])


@router.post(
    "/create",
    response_model=TokenResponse,
    summary="Create a new API Token"
)
async def create_token_route(
    token_data: CreateTokenRequest,
    admin: Annotated[AdditionalAccountData, Depends(authenticate_with_token)]
):
    if not admin.administrator:
        raise HTTPException(status_code=403, detail="Not authorized")

    token_id = generate_random_password(custom_specials=False)

    jwt_token = await JWToken.create_api_token(token_id)

    token_hash = hashlib.sha256(jwt_token.encode()).hexdigest()

    new_token = APITokenInDB(
        id=token_id,
        name=token_data.name,
        token_hash=token_hash,
        messages_limit=token_data.messages_limit,
        is_active=True,
        created_at=datetime.utcnow()
    )

    created_token = db_helper.create_token(new_token)

    if not created_token:
        raise HTTPException(status_code=500, detail="Failed to create token (ID collision?)")

    return TokenResponse(
        id=token_id,
        token=jwt_token,
        name=token_data.name,
        messages_limit=token_data.messages_limit
    )


@router.get(
    "/list",
    response_model=list[TokenStats],
    summary="List all API Tokens"
)
async def list_tokens(
    admin: Annotated[AdditionalAccountData, Depends(authenticate_with_token)]
):
    if not admin.administrator:
        raise HTTPException(status_code=403, detail="Not authorized")

    tokens = db_helper.get_all_tokens()
    result = []
    
    for t in tokens:
        usage = db_helper.count_token_messages(t['id'])
        result.append(TokenStats(
            id=t['id'],
            name=t['name'],
            messages_limit=t['messages_limit'],
            current_usage=usage,
            is_active=bool(t['is_active']),
            created_at=str(t['created_at'])
        ))

    return result


@router.put(
    "/{token_id}",
    response_model=TokenStats,
    summary="Update API Token limits or status"
)
async def update_token_route(
    token_id: str,
    update_data: UpdateTokenRequest,
    admin: Annotated[AdditionalAccountData, Depends(authenticate_with_token)]
):
    if not admin.administrator:
        raise HTTPException(status_code=403, detail="Not authorized")

    existing = db_helper.get_token_by_id(token_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Token not found")

    updated = db_helper.update_token(
        token_id, 
        limit=update_data.messages_limit, 
        active=update_data.is_active
    )

    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update token")

    usage = db_helper.count_token_messages(token_id)
    
    return TokenStats(
        id=updated['id'],
        name=updated['name'],
        messages_limit=updated['messages_limit'],
        current_usage=usage,
        is_active=bool(updated['is_active']),
        created_at=str(updated['created_at'])
    )


@router.delete(
    "/{token_id}",
    summary="Delete an API Token"
)
async def delete_token_route(
    token_id: str,
    admin: Annotated[AdditionalAccountData, Depends(authenticate_with_token)]
):
    if not admin.administrator:
        raise HTTPException(status_code=403, detail="Not authorized")

    success = db_helper.delete_token(token_id)

    if not success:
        raise HTTPException(status_code=404, detail="Token not found")
    
    return {"detail": "Token deleted"}

@router.post(
    "/{token_id}/refresh",
    response_model=TokenResponse,
    summary="Refresh an API Token (Generate new Secret/Hash, keep ID)"
)
async def refresh_token_route(
    token_id: str,
    admin: Annotated[AdditionalAccountData, Depends(authenticate_with_token)]
):
    if not admin.administrator:
        raise HTTPException(status_code=403, detail="Not authorized")

    existing = db_helper.get_token_by_id(token_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Token not found")

    new_jwt_token = await JWToken.create_api_token(token_id)
    new_token_hash = hashlib.sha256(new_jwt_token.encode()).hexdigest()

    refreshed_token_record = db_helper.refresh_token_id(token_id, new_token_hash)

    if not refreshed_token_record:
        raise HTTPException(status_code=500, detail="Failed to refresh token")

    return TokenResponse(
        id=refreshed_token_record['id'],
        token=new_jwt_token,
        name=refreshed_token_record['name'],
        messages_limit=refreshed_token_record['messages_limit']
    )
