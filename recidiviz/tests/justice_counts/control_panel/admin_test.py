# Recidiviz - a data platform for criminal justice reform
# Copyright (C) 2023 Recidiviz, Inc.
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
"""Implements tests for the Justice Counts Control Panel backend API."""
from collections import defaultdict
from typing import Dict

import mock
import pytest
from mock import patch
from sqlalchemy.engine import Engine

from recidiviz.justice_counts.agency import AgencyInterface
from recidiviz.justice_counts.control_panel.config import Config
from recidiviz.justice_counts.control_panel.server import create_app
from recidiviz.justice_counts.datapoint import DatapointInterface
from recidiviz.justice_counts.metrics import law_enforcement
from recidiviz.justice_counts.metrics.custom_reporting_frequency import (
    CustomReportingFrequency,
)
from recidiviz.justice_counts.user_account import UserAccountInterface
from recidiviz.justice_counts.utils.constants import (
    REPORTING_FREQUENCY_CONTEXT_KEY,
    VALID_SYSTEMS,
)
from recidiviz.persistence.database.schema.justice_counts import schema
from recidiviz.persistence.database.schema.justice_counts.schema import (
    AgencyUserAccountAssociation,
    Source,
    UserAccount,
    UserAccountInvitationStatus,
)
from recidiviz.tests.auth.utils import get_test_auth0_config
from recidiviz.tests.justice_counts.utils.utils import (
    JusticeCountsDatabaseTestCase,
    JusticeCountsSchemaTestObjects,
)
from recidiviz.tools.postgres import local_postgres_helpers
from recidiviz.utils.auth.auth0 import passthrough_authorization_decorator
from recidiviz.utils.types import assert_type


@pytest.mark.uses_db
class TestJusticePublisherAdminPanelAPI(JusticeCountsDatabaseTestCase):
    """Implements tests for the Justice Counts Publisher Admin Panel backend API."""

    def setUp(self) -> None:
        self.test_schema_objects = JusticeCountsSchemaTestObjects()

        def mock_create_JC_user(name: str, email: str) -> Dict[str, str]:
            return {
                "name": name,
                "email": email,
                "user_id": f"auth0|1234{name}",
            }

        mock_auth0_client = mock.Mock()
        mock_auth0_client.create_JC_user.side_effect = mock_create_JC_user

        self.client_patcher = patch("recidiviz.auth.auth0_client.Auth0")
        self.test_auth0_client = (
            self.client_patcher.start().return_value
        ) = mock_auth0_client
        test_config = Config(
            DB_URL=local_postgres_helpers.on_disk_postgres_db_url(),
            WTF_CSRF_ENABLED=False,
            AUTH_DECORATOR=passthrough_authorization_decorator(),
            AUTH_DECORATOR_ADMIN_PANEL=passthrough_authorization_decorator(),
            AUTH0_CONFIGURATION=get_test_auth0_config(),
            AUTH0_CLIENT=self.test_auth0_client,
            SEGMENT_KEY="fake_segment_key",
        )
        self.app = create_app(config=test_config)
        self.client = self.app.test_client()
        self.app.secret_key = "NOT A SECRET"
        # `flask_sqlalchemy_session` sets the `scoped_session` attribute on the app,
        # even though this is not specified in the types for `app`.
        self.session = self.app.scoped_session  # type: ignore[attr-defined]
        super().setUp()

    def get_engine(self) -> Engine:
        return self.session.get_bind()

    def load_users_and_agencies(self) -> None:
        """Loads three agency and three users to the current session."""
        agency_A = self.test_schema_objects.test_agency_A
        user_A = self.test_schema_objects.test_user_A
        agency_B = self.test_schema_objects.test_agency_B
        user_B = self.test_schema_objects.test_user_B
        agency_C = self.test_schema_objects.test_agency_C
        user_C = self.test_schema_objects.test_user_C
        self.session.add_all([agency_A, user_A, agency_B, user_B, agency_C, user_C])
        self.session.commit()
        self.session.refresh(user_A)
        self.session.refresh(user_B)
        self.session.refresh(user_C)
        self.session.refresh(agency_A)
        self.session.refresh(agency_B)
        self.session.refresh(agency_C)

        user_agency_association_A = AgencyUserAccountAssociation(
            user_account_id=user_A.id,
            agency_id=agency_A.id,
            invitation_status=UserAccountInvitationStatus.PENDING,
        )
        user_agency_association_B = AgencyUserAccountAssociation(
            user_account_id=user_B.id,
            agency_id=agency_B.id,
            invitation_status=UserAccountInvitationStatus.PENDING,
        )
        user_agency_association_C = AgencyUserAccountAssociation(
            user_account_id=user_C.id,
            agency_id=agency_C.id,
            invitation_status=UserAccountInvitationStatus.PENDING,
        )
        self.session.add_all(
            [
                user_agency_association_A,
                user_agency_association_B,
                user_agency_association_C,
            ]
        )
        self.session.commit()

    # UserAccount

    def test_get_all_users(self) -> None:
        self.load_users_and_agencies()
        response = self.client.get("/admin/user")
        self.assertEqual(response.status_code, 200)
        response_json = assert_type(response.json, dict)
        user_json_list = response_json["users"]
        self.assertEqual(len(user_json_list), 3)
        users = self.session.query(UserAccount).all()
        user_id_to_user = {user.id: user for user in users}

        for user_json in user_json_list:
            db_user = user_id_to_user[(user_json["id"])]
            agency = db_user.agency_assocs[0].agency
            self.assertEqual(user_json["auth0_user_id"], db_user.auth0_user_id)
            self.assertEqual(user_json["name"], db_user.name)
            self.assertEqual(len(user_json["agencies"]), 1)
            self.assertEqual(user_json["agencies"][0]["id"], agency.id)
            self.assertEqual(user_json["agencies"][0]["name"], agency.name)

    def test_get_user(self) -> None:
        self.load_users_and_agencies()
        user = (
            self.session.query(schema.UserAccount)
            .filter(schema.UserAccount.auth0_user_id == "auth0_id_A")
            .one()
        )
        response = self.client.get(f"/admin/user/{user.id}")
        self.assertEqual(response.status_code, 200)
        response_json = assert_type(response.json, dict)
        self.assertEqual(response_json["name"], user.name)
        self.assertEqual(response_json["id"], user.id)
        self.assertEqual(len(response_json["agencies"]), 1)
        self.assertEqual(response_json["agencies"][0]["name"], "Agency Alpha")

    def test_create_or_update_user(
        self,
    ) -> None:
        self.load_users_and_agencies()

        agency_A_id = AgencyInterface.get_agency_by_name(
            session=self.session, name="Agency Alpha"
        ).id
        agency_B_id = AgencyInterface.get_agency_by_name(
            session=self.session, name="Agency Law Enforcement"
        ).id
        # Create a new user
        response = self.client.put(
            "/admin/user",
            json={
                "users": [
                    {
                        "name": "Jane Doe",
                        "email": "email1@test.com",
                        "agency_ids": [agency_A_id, agency_B_id],
                    }
                ]
            },
        )
        self.assertEqual(response.status_code, 200)
        user = assert_type(
            UserAccountInterface.get_user_by_email(
                session=self.session, email="email1@test.com"
            ),
            schema.UserAccount,
        )
        self.assertEqual(len(user.agency_assocs), 2)
        self.assertEqual(user.agency_assocs[0].agency_id, agency_A_id)
        self.assertEqual(
            user.agency_assocs[0].role,
            schema.UserAccountRole.AGENCY_ADMIN,
        )
        self.assertEqual(user.agency_assocs[1].agency_id, agency_B_id)
        self.assertEqual(
            user.agency_assocs[1].role,
            schema.UserAccountRole.AGENCY_ADMIN,
        )

        # Update Jane Smith, Add John Doe
        response = self.client.put(
            "/admin/user",
            json={
                "users": [
                    {
                        "name": "Jane Smith Doe",
                        "email": "email1@test.com",
                        "agency_ids": [agency_B_id],
                        "user_account_id": user.id,
                    },
                    {
                        "name": "John Doe",
                        "email": "email2@test.com",
                        "agency_ids": [agency_A_id],
                    },
                ]
            },
        )
        self.assertEqual(response.status_code, 200)
        jane_doe = assert_type(
            UserAccountInterface.get_user_by_email(
                session=self.session, email="email1@test.com"
            ),
            schema.UserAccount,
        )
        self.assertIsNotNone(jane_doe)
        self.assertEqual(jane_doe.name, "Jane Smith Doe")
        self.assertEqual(len(jane_doe.agency_assocs), 1)
        self.assertEqual(jane_doe.agency_assocs[0].agency_id, agency_B_id)
        self.assertEqual(
            jane_doe.agency_assocs[0].role,
            schema.UserAccountRole.AGENCY_ADMIN,
        )

        john_doe = assert_type(
            UserAccountInterface.get_user_by_email(
                session=self.session, email="email2@test.com"
            ),
            schema.UserAccount,
        )
        self.assertIsNotNone(john_doe)
        self.assertEqual(john_doe.name, "John Doe")
        self.assertEqual(len(john_doe.agency_assocs), 1)
        self.assertEqual(john_doe.agency_assocs[0].agency_id, agency_A_id)
        self.assertEqual(
            john_doe.agency_assocs[0].role,
            schema.UserAccountRole.AGENCY_ADMIN,
        )

    # Agency
    def test_get_all_agencies(self) -> None:
        self.load_users_and_agencies()
        response = self.client.get("/admin/agency")
        self.assertEqual(response.status_code, 200)
        response_json = assert_type(response.json, dict)
        self.assertEqual(
            response_json["systems"], [enum.value for enum in VALID_SYSTEMS]
        )
        agency_json_list = response_json["agencies"]
        self.assertEqual(len(agency_json_list), 3)
        agencies = self.session.query(Source).all()
        agency_id_to_agency = {a.id: a for a in agencies}

        for agency_json in agency_json_list:
            db_agency = agency_id_to_agency[(agency_json["id"])]
            user = db_agency.user_account_assocs[0].user_account
            self.assertEqual(agency_json["name"], db_agency.name)
            self.assertEqual(agency_json["child_agency_ids"], [])
            self.assertEqual(len(agency_json["team"]), 1)
            self.assertEqual(agency_json["team"][0]["name"], user.name)

    def test_get_agency(self) -> None:
        self.load_users_and_agencies()
        agency = (
            self.session.query(schema.Agency)
            .filter(schema.Agency.name == "Agency Alpha")
            .one()
        )
        response = self.client.get(f"/admin/agency/{agency.id}")
        self.assertEqual(response.status_code, 200)
        response_json = assert_type(response.json, dict)
        self.assertEqual(
            response_json["roles"], [enum.value for enum in schema.UserAccountRole]
        )
        agency_json = response_json["agency"]
        self.assertEqual(agency_json["child_agency_ids"], [])
        self.assertEqual(agency_json["name"], agency.name)
        self.assertEqual(agency_json["id"], agency.id)
        self.assertEqual(len(agency_json["team"]), 1)
        self.assertEqual(agency_json["team"][0]["name"], "Jane Doe")

    def test_create_or_update_agency(self) -> None:
        self.load_users_and_agencies()

        user_A_id = UserAccountInterface.get_user_by_auth0_user_id(
            session=self.session, auth0_user_id="auth0_id_A"
        ).id
        user_B_id = UserAccountInterface.get_user_by_auth0_user_id(
            session=self.session, auth0_user_id="auth0_id_B"
        ).id
        # Create a new agency
        response = self.client.put(
            "/admin/agency",
            json={
                "name": "New Agency",
                "state_code": "us_ca",
                "systems": ["LAW_ENFORCEMENT", "JAILS"],
                "is_superagency": False,
                "super_agency_id": None,
                "agency_id": None,
                "team": [{"user_account_id": user_A_id, "role": "AGENCY_ADMIN"}],
                "child_agency_ids": [],
                "is_dashboard_enabled": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        agency = AgencyInterface.get_agency_by_name(
            session=self.session, name="New Agency"
        )
        self.assertIsNotNone(agency)
        self.assertFalse(agency.is_superagency)
        self.assertEqual(
            agency.systems,
            [schema.System.LAW_ENFORCEMENT.value, schema.System.JAILS.value],
        )
        self.assertEqual(agency.state_code, "us_ca")
        self.assertEqual(len(agency.user_account_assocs), 1)
        self.assertEqual(agency.user_account_assocs[0].user_account_id, user_A_id)
        self.assertEqual(
            agency.user_account_assocs[0].role,
            schema.UserAccountRole.AGENCY_ADMIN,
        )

        # Update name, users, and child agency, and turn on dashboard
        law_enforcement_agency = AgencyInterface.get_agency_by_name(
            session=self.session, name="Agency Alpha"
        )
        law_enforcement_agency_id = law_enforcement_agency.id
        response = self.client.put(
            "/admin/agency",
            json={
                "name": "New Agency New Name",
                "state_code": "us_ca",
                "systems": ["LAW_ENFORCEMENT", "JAILS"],
                "is_superagency": True,
                "super_agency_id": None,
                "child_agency_ids": [law_enforcement_agency_id],
                "agency_id": agency.id,
                "team": [
                    {"user_account_id": user_B_id, "role": "AGENCY_ADMIN"},
                    {"user_account_id": user_A_id, "role": "JUSTICE_COUNTS_ADMIN"},
                ],
                "is_dashboard_enabled": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        response_json = assert_type(response.json, dict)
        self.assertEqual(response_json["child_agency_ids"], [law_enforcement_agency_id])
        agency = AgencyInterface.get_agency_by_name(
            session=self.session, name="New Agency New Name"
        )
        self.assertIsNotNone(agency)
        self.assertTrue(agency.is_superagency)
        self.assertTrue(agency.is_dashboard_enabled)
        self.assertEqual(
            agency.systems,
            [schema.System.LAW_ENFORCEMENT.value, schema.System.JAILS.value],
        )
        self.assertEqual(agency.state_code, "us_ca")
        self.assertEqual(len(agency.user_account_assocs), 2)
        self.assertEqual(agency.user_account_assocs[0].user_account_id, user_A_id)
        self.assertEqual(
            agency.user_account_assocs[0].role,
            schema.UserAccountRole.JUSTICE_COUNTS_ADMIN,
        )
        self.assertEqual(agency.user_account_assocs[1].user_account_id, user_B_id)
        self.assertEqual(
            agency.user_account_assocs[1].role,
            schema.UserAccountRole.AGENCY_ADMIN,
        )
        child_agencies = AgencyInterface.get_child_agencies_for_agency(
            session=self.session, agency=agency
        )
        self.assertEqual(len(child_agencies), 1)
        self.assertEqual(child_agencies[0].name, "Agency Alpha")

        # Delete users from Agency and remove child agency
        response = self.client.put(
            "/admin/agency",
            json={
                "name": "New Agency New Name",
                "state_code": "us_ca",
                "systems": ["LAW_ENFORCEMENT", "JAILS"],
                "is_superagency": True,
                "super_agency_id": None,
                "child_agency_ids": [],
                "agency_id": agency.id,
                "is_dashboard_enabled": False,
                "team": [],
            },
        )

        self.assertEqual(response.status_code, 200)
        response_json = assert_type(response.json, dict)
        self.assertEqual(response_json["child_agency_ids"], [])
        agency = AgencyInterface.get_agency_by_name(
            session=self.session, name="New Agency New Name"
        )
        self.assertIsNotNone(agency)
        self.assertTrue(agency.is_superagency)
        self.assertFalse(agency.is_dashboard_enabled)
        self.assertEqual(
            agency.systems,
            [schema.System.LAW_ENFORCEMENT.value, schema.System.JAILS.value],
        )
        self.assertEqual(agency.state_code, "us_ca")
        self.assertEqual(len(agency.user_account_assocs), 0)
        child_agencies = AgencyInterface.get_child_agencies_for_agency(
            session=self.session, agency=agency
        )
        self.assertEqual(len(child_agencies), 0)

    def test_copy_metric_settings_to_child_agencies(self) -> None:
        self.load_users_and_agencies()
        super_agency = (
            self.session.query(schema.Agency)
            .filter(schema.Agency.name == "Agency Alpha")
            .one()
        )

        child_agency = schema.Agency(
            name="Agency Alpha Child Agency",
            super_agency_id=super_agency.id,
            systems=["LAW_ENFORCEMENT"],
        )

        disabled_metric = schema.Datapoint(
            metric_definition_key=law_enforcement.funding.key,
            enabled=False,
            source_id=super_agency.id,
            is_report_datapoint=False,
        )

        custom_reporting_frequency = schema.Datapoint(
            metric_definition_key=law_enforcement.expenses.key,
            source_id=super_agency.id,
            context_key=REPORTING_FREQUENCY_CONTEXT_KEY,
            value=(
                CustomReportingFrequency(
                    frequency=schema.ReportingFrequency.ANNUAL, starting_month=2
                ).to_json_str()
            ),
            is_report_datapoint=False,
        )

        self.session.add_all(
            [child_agency, disabled_metric, custom_reporting_frequency]
        )
        self.session.commit()
        self.session.refresh(child_agency)
        self.session.refresh(super_agency)
        child_agency_id = child_agency.id
        super_agency_id = super_agency.id
        response = self.client.post(
            f"/admin/agency/{super_agency_id}/child-agency/copy",
            json={
                "metric_definition_key_subset": [law_enforcement.expenses.key]
            },  # only copy over expense metric settings
        )
        self.assertEqual(response.status_code, 200)
        agency_datapoints = DatapointInterface.get_agency_datapoints(
            session=self.session, agency_id=child_agency_id
        )

        # There will be two agency datapoints, one that is a default
        # datapoint to record the includes/excludes description for the
        # expenses metric, the other that records the information about
        # the custom reporting frequency.
        self.assertEqual(len(agency_datapoints), 2)
        self.assertEqual(
            agency_datapoints[0].context_key, "INCLUDES_EXCLUDES_DESCRIPTION"
        )
        self.assertIsNone(agency_datapoints[0].value)
        self.assertEqual(agency_datapoints[1].context_key, "REPORTING_FREQUENCY")
        self.assertEqual(
            agency_datapoints[1].value,
            '{"custom_frequency": "ANNUAL", "starting_month": 2}',
        )

        response = self.client.post(
            f"/admin/agency/{super_agency_id}/child-agency/copy",
            json={"metric_definition_key_subset": ["ALL"]},  # copy over all metrics
        )

        self.assertEqual(response.status_code, 200)
        agency_datapoints = DatapointInterface.get_agency_datapoints(
            session=self.session, agency_id=child_agency_id
        )

        # There will be two agency datapoints, one that is a default
        # datapoint to record the includes/excludes description for the
        # expenses metric, the other that records the information about
        # the custom reporting frequency.
        metric_key_to_agency_datapoints = defaultdict(list)
        for datapoint in agency_datapoints:
            metric_key_to_agency_datapoints[datapoint.metric_definition_key].append(
                datapoint
            )

        for key, datapoints in metric_key_to_agency_datapoints.items():
            if key == law_enforcement.expenses.key:
                # The expenses agency datapoints will not change
                self.assertEqual(
                    datapoints[0].context_key, "INCLUDES_EXCLUDES_DESCRIPTION"
                )
                self.assertIsNone(datapoints[0].value)
                self.assertEqual(datapoints[1].context_key, "REPORTING_FREQUENCY")
                self.assertEqual(
                    datapoints[1].value,
                    '{"custom_frequency": "ANNUAL", "starting_month": 2}',
                )
            elif key == law_enforcement.funding.key:
                # The funding agency datapoints will not change from when
                # they were updated in the last call.
                self.assertEqual(datapoints[0].context_key, None)
                self.assertEqual(datapoints[0].enabled, False)
                self.assertEqual(
                    datapoints[1].context_key, "INCLUDES_EXCLUDES_DESCRIPTION"
                )
                self.assertIsNone(datapoints[1].value)
            else:
                for datapoint in datapoints:
                    self.assertIsNone(datapoint.value)
