"""API key Controllers."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Annotated

import structlog
from litestar import Controller, Response, delete, get, patch, post
from litestar.di import Provide
from litestar.exceptions import InternalServerException

from swparse.db.models import ApiKeys, ApiKeyStatus
from swparse.db.models import User as UserModel
from swparse.domain.accounts import urls
from swparse.domain.accounts.dependencies import provide_api_key_service, provide_users_service
from swparse.domain.accounts.guards import requires_active_user
from swparse.domain.accounts.schemas import UpdateAPIKey, API_KEY_DETAIL, API_KEY, APIKeyCreate
from swparse.domain.accounts.services import ApiKeyService, UserService
from litestar.repository.filters import LimitOffset, CollectionFilter
from  litestar.exceptions import NotAuthorizedException, NotFoundException

if TYPE_CHECKING:
    from uuid import UUID
    from litestar.params import Parameter
    from advanced_alchemy.service import OffsetPagination

logger = structlog.get_logger()

class APIKeyController(Controller):
    tags = ["API Keys"]
    guards = [requires_active_user]
    dependencies = {"users_service": Provide(provide_users_service),"api_key_service":Provide(provide_api_key_service)}
    signature_namespace = {"UserService": UserService, "ApiKeyService":ApiKeyService}

    @post(
        operation_id="APIkeyGenerate",
        name="keys:generate",
        path=urls.API_KEY_GENERATE,
        summary="Generate a key.",
        guards=[requires_active_user]
    )
    async def generate_api_key(
        self,
        api_key_service: ApiKeyService,
        current_user: UserModel,
        data: APIKeyCreate
    ) -> API_KEY:
        """Generate an API key."""
        key_len = 32
        user_id = current_user.id
        api_key = secrets.token_hex(key_len)
        logger.error("current_user.id")
        logger.info(data)
        api_key_obj = await api_key_service.create(ApiKeys(api_key=api_key, name= data.key_name, user_id= user_id, status =ApiKeyStatus.ACTIVE ))

        if not api_key_obj:
            raise InternalServerException(detail="Failed to generate api-key", status_code=500)

        return api_key_service.to_schema(data = api_key_obj, schema_type= API_KEY)


    @get(
        operation_id="APIkeyList",
        name="keys:list",
        path=urls.API_KEY_LIST,
        summary="List API key.",
    )
    async def list_api_key(
        self,
        api_key_service: ApiKeyService,
        current_user: UserModel,
        limit_offset: LimitOffset
    ) -> OffsetPagination[API_KEY]:
        """Generate an API key."""
        filters = [limit_offset]
        if not current_user.is_superuser:
            filters.append(CollectionFilter("user_id", [current_user.id]))
        api_key_objs, total = await api_key_service.list_and_count(*filters)

        return api_key_service.to_schema(data=api_key_objs, total=total, schema_type=API_KEY, filters=filters)
    

    @patch(
        operation_id="APIkeyUpdate",
        name="keys:update",
        path=urls.API_KEY_UPDATE,
        summary="Rename API key.",
    )
    async def update_api_key(
        self,
        api_key_service: ApiKeyService,
        current_user: UserModel,
        data: UpdateAPIKey
    ) -> API_KEY_DETAIL:
        """Generate an API key."""
 
        api_key_obj = await api_key_service.get_one_or_none(id= data.id )

        if api_key_obj is None:
            raise NotFoundException(detail=f"There is no API key with {data.id}")

        if not current_user.is_superuser and api_key_obj.user_id == current_user.id:
            raise NotAuthorizedException(detail="Not Authorized to rename the API key")
        
        updated_api_key_obj = await api_key_service.update(item_id=data.id, data={"name": data.new_name})

        return API_KEY_DETAIL(
            id = updated_api_key_obj.id,
            name = updated_api_key_obj.name,
            username = current_user.name,
            api_key = updated_api_key_obj.api_key,
            status= updated_api_key_obj.status
        )


    @delete(
        operation_id="APIkeyDelete",
        name="keys:delete",
        path=urls.API_KEY_DELETE,
        summary="Delete API key.",
    )
    async def delete_api_key(
        self,
        api_key_service: ApiKeyService,
        current_user: UserModel,
        id: Annotated[
            UUID,
            Parameter(
                title="API Key ID",
                description="The API key to be deleted.",
            ),
        ]
    ) -> None:
        """Generate an API key."""
 
        api_key_obj = await api_key_service.get_one_or_none(id=id)

        if api_key_obj is None:
            raise NotFoundException(detail=f"There is no API key with {id}")

        if not current_user.is_superuser and api_key_obj.user_id == current_user.id:
            raise NotAuthorizedException(detail="Not Authorized to rename the API key")
        
        await api_key_service.delete(item_id=id)
 