# Recidiviz - a data platform for criminal justice reform
# Copyright (C) 2020 Recidiviz, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# =============================================================================
"""Flask configs for different environments."""

import json
from typing import Callable, Optional

import attr

from recidiviz.auth.auth0_client import Auth0Client
from recidiviz.justice_counts.control_panel.utils import on_successful_authorization
from recidiviz.justice_counts.exceptions import JusticeCountsServerError
from recidiviz.persistence.database.constants import JUSTICE_COUNTS_DB_SECRET_PREFIX
from recidiviz.persistence.database.schema_type import SchemaType
from recidiviz.persistence.database.sqlalchemy_database_key import SQLAlchemyDatabaseKey
from recidiviz.persistence.database.sqlalchemy_engine_manager import (
    SQLAlchemyEngineManager,
)
from recidiviz.utils import environment
from recidiviz.utils.auth.auth0 import (
    JUSTICE_COUNTS_ADMIN_CLAIM,
    ROLES_CLAIMS,
    Auth0Config,
    TokenClaims,
    build_auth0_authorization_decorator,
    passthrough_authorization_decorator,
)
from recidiviz.utils.environment import in_ci, in_gcp_staging
from recidiviz.utils.secrets import get_secret
from recidiviz.utils.types import assert_type


@attr.define
class Config:
    """Config class builds database and authentication objects for justice counts app"""

    SCHEMA_TYPE: SchemaType = SchemaType.JUSTICE_COUNTS
    DATABASE_KEY: SQLAlchemyDatabaseKey = SQLAlchemyDatabaseKey.for_schema(SCHEMA_TYPE)
    # Indicates whether CSRF protection is enabled for the whole app. Should be set to False for tests.
    WTF_CSRF_ENABLED: bool = True
    # Whether to enforce the same origin policy by checking that the referrer matches the host.
    # Set to False in staging so that we can run the frontend locally against our staging backend.
    WTF_CSRF_SSL_STRICT: bool = attr.field()
    DB_URL: str = attr.field()
    AUTH0_CONFIGURATION: Auth0Config = attr.field()
    AUTH_DECORATOR: Callable = attr.field()
    AUTH_DECORATOR_ADMIN_PANEL: Callable = attr.field()
    AUTH0_CLIENT: Auth0Client = attr.field()
    SEGMENT_KEY: Optional[str] = attr.field()

    @WTF_CSRF_SSL_STRICT.default
    def _wtf_csrf_ssl_factory(self) -> bool:
        if in_gcp_staging():
            # In staging, don't enforce same origin policy. This allows us to run
            # our frontend locally against our staging backend, which is important
            # for contractors who aren't able to run our backend locally.
            return False
        return True

    @DB_URL.default
    def _db_url_factory(self) -> str:
        return SQLAlchemyEngineManager.get_server_postgres_instance_url(
            database_key=self.DATABASE_KEY,
            secret_prefix_override=JUSTICE_COUNTS_DB_SECRET_PREFIX,
        )

    @AUTH_DECORATOR.default
    def _auth_decorator_factory(self) -> Callable:
        if in_ci():
            return passthrough_authorization_decorator()

        return build_auth0_authorization_decorator(
            self.AUTH0_CONFIGURATION, on_successful_authorization
        )

    @AUTH_DECORATOR_ADMIN_PANEL.default
    def _admin_panel_auth_decorator_factory(self) -> Callable:
        if in_ci():
            return passthrough_authorization_decorator()

        def on_successful_authorization_justice_counts_admin_only(
            jwt_claims: TokenClaims,
        ) -> None:
            on_successful_authorization(jwt_claims=jwt_claims)

            roles = assert_type(jwt_claims.get(ROLES_CLAIMS, []), list)

            if roles is not None and JUSTICE_COUNTS_ADMIN_CLAIM not in set(roles):
                raise JusticeCountsServerError(
                    code="no_justice_counts_access",
                    description="You are not authorized to access this application.",
                )

        return build_auth0_authorization_decorator(
            self.AUTH0_CONFIGURATION,
            on_successful_authorization_justice_counts_admin_only,
        )

    @AUTH0_CONFIGURATION.default
    def _auth_configuration_factory(self) -> Optional[Auth0Config]:
        if in_ci():
            # In our GH Actions CI test workflow, there's no easy way to get
            # access to a working Auth0 secret, and we don't need one to
            # prove that the server is working, so just return None
            return None

        auth0_configuration = get_secret("justice_counts_auth0")
        if not auth0_configuration:
            raise JusticeCountsServerError(
                code="no_justice_counts_access",
                description="You are not authorized to access this application.",
            )
        return Auth0Config.from_config_json(json.loads(auth0_configuration))

    @AUTH0_CLIENT.default
    def auth0_client_factory(self) -> Optional[Auth0Client]:
        if in_ci():
            # In our GH Actions CI test workflow, there's no easy way to get
            # access to a working Auth0 secret, and we don't need one to
            # prove that the server is working, so just return None
            return None
        if environment.in_development() or environment.in_gcp():
            return Auth0Client(  # nosec
                domain_secret_name="justice_counts_auth0_api_domain",
                client_id_secret_name="justice_counts_auth0_api_client_id",
                client_secret_secret_name="justice_counts_auth0_api_client_secret",
            )
        return None

    @SEGMENT_KEY.default
    def _segment_key_factory(self) -> Optional[str]:
        return get_secret("justice_counts_segment_key")
