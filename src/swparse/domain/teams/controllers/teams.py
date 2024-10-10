"""User Account Controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from litestar import Controller, delete, get, patch, post
from litestar.di import Provide
from sqlalchemy import select
from swparse.db.models import Team as TeamModel
from swparse.db.models import User as UserModel
from swparse.db.models.team_member import TeamMember as TeamMemberModel
from swparse.domain.accounts.guards import requires_active_user
from swparse.domain.teams import urls
from swparse.domain.teams.dependencies import provide_teams_service
from swparse.domain.teams.guards import requires_team_admin, requires_team_membership
from swparse.domain.teams.schemas import Team, TeamCreate, TeamUpdate
from swparse.domain.teams.services import TeamService

if TYPE_CHECKING:
    from uuid import UUID

    from advanced_alchemy.service.pagination import OffsetPagination
    from litestar.params import Dependency, Parameter
    from swparse.lib.dependencies import FilterTypes


class TeamController(Controller):
    """Teams."""

    tags = ["Teams"]
    dependencies = {"teams_service": Provide(provide_teams_service)}
    guards = [requires_active_user]
    signature_namespace = {
        "TeamService": TeamService,
        "TeamUpdate": TeamUpdate,
        "TeamCreate": TeamCreate,
    }

    @get(
        component="team/list",
        name="teams.list",
        operation_id="ListTeams",
        path=urls.TEAM_LIST,
    )
    async def list_teams(
        self,
        teams_service: TeamService,
        current_user: UserModel,
        filters: Annotated[list[FilterTypes], Dependency(skip_validation=True)],
    ) -> OffsetPagination[Team]:
        """List teams that your account can access.."""
        if not teams_service.can_view_all(current_user):
            filters.append(
                TeamModel.id.in_(select(TeamMemberModel.team_id).where(TeamMemberModel.user_id == current_user.id)),  # type: ignore[arg-type]
            )
        results, total = await teams_service.list_and_count(*filters)
        return teams_service.to_schema(data=results, total=total, schema_type=Team, filters=filters)

    @post(
        operation_id="CreateTeam",
        name="teams:create",
        summary="Create a new team.",
        path=urls.TEAM_CREATE,
    )
    async def create_team(
        self,
        teams_service: TeamService,
        current_user: UserModel,
        data: TeamCreate,
    ) -> Team:
        """Create a new team."""
        obj = data.to_dict()
        obj.update({"owner_id": current_user.id, "owner": current_user})
        db_obj = await teams_service.create(obj)
        return teams_service.to_schema(schema_type=Team, data=db_obj)

    @get(
        operation_id="GetTeam",
        name="teams:get",
        guards=[requires_team_membership],
        summary="Retrieve the details of a team.",
        path=urls.TEAM_DETAIL,
    )
    async def get_team(
        self,
        teams_service: TeamService,
        team_id: Annotated[
            UUID,
            Parameter(
                title="Team ID",
                description="The team to retrieve.",
            ),
        ],
    ) -> Team:
        """Get details about a team."""
        db_obj = await teams_service.get(team_id)
        return teams_service.to_schema(schema_type=Team, data=db_obj)

    @patch(
        operation_id="UpdateTeam",
        name="teams:update",
        guards=[requires_team_admin],
        path=urls.TEAM_UPDATE,
    )
    async def update_team(
        self,
        data: TeamUpdate,
        teams_service: TeamService,
        team_id: Annotated[
            UUID,
            Parameter(
                title="Team ID",
                description="The team to update.",
            ),
        ],
    ) -> Team:
        """Update a migration team."""
        db_obj = await teams_service.update(
            item_id=team_id,
            data=data.to_dict(),
        )
        return teams_service.to_schema(schema_type=Team, data=db_obj)

    @delete(
        operation_id="DeleteTeam",
        name="teams:delete",
        guards=[requires_team_admin],
        summary="Remove Team",
        path=urls.TEAM_DELETE,
    )
    async def delete_team(
        self,
        teams_service: TeamService,
        team_id: Annotated[
            UUID,
            Parameter(title="Team ID", description="The team to delete."),
        ],
    ) -> None:
        """Delete a team."""
        _ = await teams_service.delete(team_id)
