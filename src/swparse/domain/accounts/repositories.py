from __future__ import annotations

from advanced_alchemy.repository import SQLAlchemyAsyncRepository, SQLAlchemyAsyncSlugRepository

from swparse.db.models import ApiKeys, Role, User, UserOauthAccount, UserRole


class UserRepository(SQLAlchemyAsyncRepository[User]):
    """User SQLAlchemy Repository."""

    model_type = User


class UserOauthAccountRepository(SQLAlchemyAsyncRepository[UserOauthAccount]):
    """User SQLAlchemy Repository."""

    model_type = UserOauthAccount


class RoleRepository(SQLAlchemyAsyncSlugRepository[Role]):
    """User SQLAlchemy Repository."""

    model_type = Role


class UserRoleRepository(SQLAlchemyAsyncRepository[UserRole]):
    """User Role SQLAlchemy Repository."""

    model_type = UserRole



class ApiKeyRepository(SQLAlchemyAsyncRepository[ApiKeys]):
    """API keys SQLAlchemy Repository."""

    model_type = ApiKeys
