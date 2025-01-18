from swparse.config.app import alchemy
from swparse.domain.accounts.dependencies import provide_api_key_service
from litestar.exceptions import NotAuthorizedException, HTTPException
from litestar.connection import ASGIConnection
from litestar.handlers.base import BaseRouteHandler
from dotenv import load_dotenv
from swparse.config.app import settings
 
load_dotenv()
DEFAULT_API_KEY =settings.app.PARSER_API_KEY


__all__ = ["require_api_key"]

async def require_api_key(
    connection: ASGIConnection, _: BaseRouteHandler
) -> None:
 
    api_key = connection.headers.get("authorization")
    if not api_key:
        raise HTTPException(status_code=403, detail="Forbidden missing API key")
        
    result = api_key.split(" ")
    if len(result) == 1:
        api_key =result[0]
    elif len(result) == 2 and result[0] == "Bearer":
        api_key = result[1]
    else:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid API key")
    if api_key != DEFAULT_API_KEY:
 
        api_key_service = await anext(
            provide_api_key_service(alchemy.provide_session(connection.app.state, connection.scope))
        )
        is_authorized, mesg = await api_key_service.authenticate(api_key)

        if not is_authorized:
 
            raise NotAuthorizedException(status_code=403, detail=mesg)

 