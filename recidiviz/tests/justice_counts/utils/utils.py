# Recidiviz - a data platform for criminal justice reform
# Copyright (C) 2021 Recidiviz, Inc.
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

import datetime
from typing import Any, Dict, List, Optional
from unittest import TestCase

import pytest
from sqlalchemy.engine import Engine

from recidiviz.auth.auth0_client import Auth0User, JusticeCountsAuth0AppMetadata
from recidiviz.common.constants.justice_counts import ContextKey
from recidiviz.justice_counts.dimensions.law_enforcement import CallType, ForceType
from recidiviz.justice_counts.dimensions.offense import OffenseType
from recidiviz.justice_counts.dimensions.person import RaceAndEthnicity
from recidiviz.justice_counts.dimensions.prisons import ReleaseType, StaffType
from recidiviz.justice_counts.includes_excludes.prisons import (
    PrisonClinicalStaffIncludesExcludes,
    PrisonManagementAndOperationsStaffIncludesExcludes,
    PrisonProgrammaticStaffIncludesExcludes,
    PrisonSecurityStaffIncludesExcludes,
    PrisonStaffIncludesExcludes,
    VacantPrisonStaffIncludesExcludes,
)
from recidiviz.justice_counts.metrics import law_enforcement, prisons
from recidiviz.justice_counts.metrics.custom_reporting_frequency import (
    CustomReportingFrequency,
)
from recidiviz.justice_counts.metrics.metric_interface import (
    MetricAggregatedDimensionData,
    MetricContextData,
    MetricInterface,
)
from recidiviz.justice_counts.utils.constants import REPORTING_FREQUENCY_CONTEXT_KEY
from recidiviz.persistence.database.schema.justice_counts import schema
from recidiviz.persistence.database.schema_type import SchemaType
from recidiviz.persistence.database.sqlalchemy_database_key import SQLAlchemyDatabaseKey
from recidiviz.persistence.database.sqlalchemy_engine_manager import (
    SQLAlchemyEngineManager,
)
from recidiviz.tools.justice_counts.control_panel.load_fixtures import (
    reset_justice_counts_fixtures,
)
from recidiviz.tools.postgres import local_persistence_helpers, local_postgres_helpers


@pytest.mark.uses_db
class JusticeCountsDatabaseTestCase(TestCase):
    """Base class for unit tests that act on the Justice Counts database."""

    # Stores the location of the postgres DB for this test run
    temp_db_dir: Optional[str]

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_db_dir = local_postgres_helpers.start_on_disk_postgresql_database()

    def setUp(self) -> None:
        self.database_key = SQLAlchemyDatabaseKey.for_schema(SchemaType.JUSTICE_COUNTS)
        self.env_vars = (
            local_persistence_helpers.update_local_sqlalchemy_postgres_env_vars()
        )

        # Auto-generate all tables that exist in our schema in this database
        self.engine = self.get_engine()
        self.database_key.declarative_meta.metadata.create_all(self.engine)
        self.maxDiff = None

    def get_engine(self) -> Engine:
        """Return the Engine that this test class should use to connect to
        the database. By default, initialize a new engine. Subclasses can
        override this method to point to an engine that already exists."""
        return SQLAlchemyEngineManager.init_engine_for_postgres_instance(
            database_key=self.database_key,
            db_url=local_postgres_helpers.on_disk_postgres_db_url(),
        )

    def load_fixtures(self) -> None:
        reset_justice_counts_fixtures(self.engine)

    def tearDown(self) -> None:
        local_persistence_helpers.teardown_on_disk_postgresql_database(
            self.database_key
        )
        local_postgres_helpers.restore_local_env_vars(self.env_vars)

    @classmethod
    def tearDownClass(cls) -> None:
        local_postgres_helpers.stop_and_clear_on_disk_postgresql_database(
            cls.temp_db_dir
        )


class JusticeCountsSchemaTestObjects:
    """Class for test schema objects"""

    def __init__(self) -> None:
        # Agencies
        self.test_agency_A = schema.Agency(
            name="Agency Alpha",
            state_code="US_XX",
            fips_county_code="us_ak_anchorage",
            systems=[schema.System.LAW_ENFORCEMENT.value],
        )
        self.test_agency_B = schema.Agency(
            name="Agency Law Enforcement",
            state_code="US_XX",
            fips_county_code="us_ca_san_francisco",
            systems=[schema.System.LAW_ENFORCEMENT.value],
        )
        self.test_agency_C = schema.Agency(
            name="Agency Supervision",
            state_code="US_XX",
            fips_county_code="us_ca_san_francisco",
            systems=[schema.System.SUPERVISION.value],
        )
        self.test_agency_D = schema.Agency(
            name="Agency Parole",
            state_code="US_XX",
            fips_county_code="us_ca_san_francisco",
            systems=[schema.System.PAROLE.value],
        )
        self.test_agency_E = schema.Agency(
            name="Agency Parole and Probation",
            state_code="US_XX",
            fips_county_code="us_ca_san_francisco",
            systems=[
                schema.System.SUPERVISION.value,
                schema.System.PAROLE.value,
                schema.System.PROBATION.value,
            ],
        )
        self.test_agency_F = schema.Agency(
            name="Agency Prosecution",
            state_code="US_XX",
            fips_county_code="us_ca_san_francisco",
            systems=[schema.System.PROSECUTION.value],
        )
        self.test_agency_G = schema.Agency(
            name="Agency Prison",
            state_code="US_XX",
            fips_county_code="us_ca_san_francisco",
            systems=[schema.System.PRISONS.value],
        )
        self.test_prison_super_agency = schema.Agency(
            name="Super Agency Prison",
            state_code="US_XX",
            fips_county_code="us_ca_san_francisco",
            systems=[schema.System.PRISONS.value],
            is_superagency=True,
        )
        self.test_prison_affiliate_A = schema.Agency(
            name="Affiliate Agency Prison A",
            state_code="US_PA",
            fips_county_code="us_ca_san_francisco",
            systems=[schema.System.PRISONS.value],
        )
        self.test_prison_affiliate_B = schema.Agency(
            name="Affiliate Agency Prison B",
            state_code="US_XX",
            fips_county_code="us_ca_san_francisco",
            systems=[schema.System.PRISONS.value],
        )

        # Auth0 Users
        self.test_auth0_user: Auth0User = {
            "email": "userA@fake.com",
            "user_id": "auth0_id_A",
            "name": "Jane Doe",
            "app_metadata": JusticeCountsAuth0AppMetadata(
                agency_ids=[], has_seen_onboarding={}
            ),
        }

        # Users
        self.test_user_A = schema.UserAccount(
            name="Jane Doe",
            auth0_user_id="auth0_id_A",
        )
        self.test_user_B = schema.UserAccount(
            name="John Doe",
            auth0_user_id="auth0_id_B",
        )
        self.test_user_C = schema.UserAccount(
            name="John Smith",
            auth0_user_id="auth0_id_C",
        )

        # Reports
        self.test_report_monthly = schema.Report(
            source=self.test_agency_A,
            type="MONTHLY",
            instance="06 2022 Metrics",
            status=schema.ReportStatus.NOT_STARTED,
            date_range_start=datetime.date.fromisoformat("2022-06-01"),
            date_range_end=datetime.date.fromisoformat("2022-07-01"),
            project=schema.Project.JUSTICE_COUNTS_CONTROL_PANEL,
            acquisition_method=schema.AcquisitionMethod.CONTROL_PANEL,
            created_at=datetime.date.fromisoformat("2022-05-30"),
        )
        self.test_report_monthly_two = schema.Report(
            source=self.test_agency_A,
            type="MONTHLY",
            instance="07 2022 Metrics",
            status=schema.ReportStatus.NOT_STARTED,
            date_range_start=datetime.date.fromisoformat("2022-07-01"),
            date_range_end=datetime.date.fromisoformat("2022-08-01"),
            project=schema.Project.JUSTICE_COUNTS_CONTROL_PANEL,
            acquisition_method=schema.AcquisitionMethod.CONTROL_PANEL,
            created_at=datetime.date.fromisoformat("2022-06-30"),
        )
        self.test_report_annual = schema.Report(
            source=self.test_agency_B,
            type="ANNUAL",
            instance="2022 Annual Metrics",
            status=schema.ReportStatus.DRAFT,
            date_range_start=datetime.date.fromisoformat("2022-01-01"),
            date_range_end=datetime.date.fromisoformat("2023-01-01"),
            modified_by=[self.test_user_B.id],
            project=schema.Project.JUSTICE_COUNTS_CONTROL_PANEL,
            acquisition_method=schema.AcquisitionMethod.CONTROL_PANEL,
            last_modified_at=datetime.datetime.fromisoformat("2022-07-05T08:00:00"),
            created_at=datetime.date.fromisoformat("2021-12-30"),
        )
        self.test_report_annual_two = schema.Report(
            source=self.test_agency_A,
            type="ANNUAL",
            instance="2023 Annual Metrics",
            status=schema.ReportStatus.DRAFT,
            date_range_start=datetime.date.fromisoformat("2023-01-01"),
            date_range_end=datetime.date.fromisoformat("2024-01-01"),
            modified_by=[self.test_user_B.id],
            project=schema.Project.JUSTICE_COUNTS_CONTROL_PANEL,
            acquisition_method=schema.AcquisitionMethod.CONTROL_PANEL,
            last_modified_at=datetime.datetime.fromisoformat("2023-07-05T08:00:00"),
            created_at=datetime.date.fromisoformat("2023-12-30"),
        )
        self.test_report_annual_three = schema.Report(
            source=self.test_agency_A,
            type="ANNUAL",
            instance="2023 Annual Metrics",
            status=schema.ReportStatus.DRAFT,
            date_range_start=datetime.date.fromisoformat("2022-01-01"),
            date_range_end=datetime.date.fromisoformat("2023-01-01"),
            modified_by=[self.test_user_B.id],
            project=schema.Project.JUSTICE_COUNTS_CONTROL_PANEL,
            acquisition_method=schema.AcquisitionMethod.CONTROL_PANEL,
            last_modified_at=datetime.datetime.fromisoformat("2023-07-05T08:00:00"),
            created_at=datetime.date.fromisoformat("2023-12-30"),
        )
        self.test_report_annual_four = schema.Report(
            source=self.test_agency_A,
            type="ANNUAL",
            instance="2023 Annual Metrics",
            status=schema.ReportStatus.DRAFT,
            date_range_start=datetime.date.fromisoformat("2023-06-01"),
            date_range_end=datetime.date.fromisoformat("2024-06-01"),
            modified_by=[self.test_user_B.id],
            project=schema.Project.JUSTICE_COUNTS_CONTROL_PANEL,
            acquisition_method=schema.AcquisitionMethod.CONTROL_PANEL,
            last_modified_at=datetime.datetime.fromisoformat("2023-07-05T08:00:00"),
            created_at=datetime.date.fromisoformat("2023-12-30"),
        )
        self.test_report_annual_five = schema.Report(
            source=self.test_agency_A,
            type="ANNUAL",
            instance="2023 Annual Metrics",
            status=schema.ReportStatus.DRAFT,
            date_range_start=datetime.date.fromisoformat("2021-06-01"),
            date_range_end=datetime.date.fromisoformat("2022-06-01"),
            modified_by=[self.test_user_B.id],
            project=schema.Project.JUSTICE_COUNTS_CONTROL_PANEL,
            acquisition_method=schema.AcquisitionMethod.CONTROL_PANEL,
            last_modified_at=datetime.datetime.fromisoformat("2023-07-05T08:00:00"),
            created_at=datetime.date.fromisoformat("2023-12-30"),
        )
        self.test_report_monthly_C = schema.Report(
            source=self.test_agency_C,
            type="MONTHLY",
            instance="01 2022 Metrics",
            status=schema.ReportStatus.NOT_STARTED,
            date_range_start=datetime.date.fromisoformat("2022-01-01"),
            date_range_end=datetime.date.fromisoformat("2022-02-01"),
            project=schema.Project.JUSTICE_COUNTS_CONTROL_PANEL,
            acquisition_method=schema.AcquisitionMethod.CONTROL_PANEL,
            created_at=datetime.date.fromisoformat("2021-12-31"),
        )
        self.test_report_supervision = self.get_report_for_agency(
            agency=self.test_agency_C
        )
        self.test_report_parole = self.get_report_for_agency(agency=self.test_agency_D)
        self.test_report_parole_probation = self.get_report_for_agency(
            agency=self.test_agency_E
        )

        self.test_report_monthly_prisons = schema.Report(
            source=self.test_agency_G,
            type="MONTHLY",
            instance="generated_instance_id",
            status=schema.ReportStatus.NOT_STARTED,
            date_range_start=datetime.date.fromisoformat("2022-06-01"),
            date_range_end=datetime.date.fromisoformat("2022-07-01"),
            project=schema.Project.JUSTICE_COUNTS_CONTROL_PANEL,
            acquisition_method=schema.AcquisitionMethod.CONTROL_PANEL,
            created_at=datetime.date.fromisoformat("2022-05-30"),
        )

        # Metrics
        self.funding_metric = JusticeCountsSchemaTestObjects.get_funding_metric()
        self.reported_calls_for_service_metric = (
            JusticeCountsSchemaTestObjects.get_reported_calls_for_service_metric()
        )
        self.arrests_metric = MetricInterface(
            key=law_enforcement.arrests.key,
            value=5000,
            aggregated_dimensions=[
                MetricAggregatedDimensionData(
                    dimension_to_value={
                        RaceAndEthnicity.UNKNOWN_ETHNICITY_AMERICAN_INDIAN_ALASKAN_NATIVE: 100,
                        RaceAndEthnicity.UNKNOWN_ETHNICITY_ASIAN: 100,
                        RaceAndEthnicity.UNKNOWN_ETHNICITY_BLACK: 1000,
                        RaceAndEthnicity.UNKNOWN_ETHNICITY_UNKNOWN: 0,
                        RaceAndEthnicity.UNKNOWN_ETHNICITY_MORE_THAN_ONE_RACE: 50,
                        RaceAndEthnicity.UNKNOWN_ETHNICITY_NATIVE_HAWAIIAN_PACIFIC_ISLANDER: 0,
                        RaceAndEthnicity.UNKNOWN_ETHNICITY_OTHER: 100,
                        RaceAndEthnicity.UNKNOWN_ETHNICITY_WHITE: 1000,
                        RaceAndEthnicity.HISPANIC_AMERICAN_INDIAN_ALASKAN_NATIVE: 10,
                        RaceAndEthnicity.HISPANIC_ASIAN: 11,
                        RaceAndEthnicity.HISPANIC_BLACK: 123,
                        RaceAndEthnicity.HISPANIC_UNKNOWN: 40,
                        RaceAndEthnicity.HISPANIC_MORE_THAN_ONE_RACE: 50,
                        RaceAndEthnicity.HISPANIC_NATIVE_HAWAIIAN_PACIFIC_ISLANDER: 0,
                        RaceAndEthnicity.HISPANIC_OTHER: 100,
                        RaceAndEthnicity.HISPANIC_WHITE: 1000,
                        RaceAndEthnicity.NOT_HISPANIC_AMERICAN_INDIAN_ALASKAN_NATIVE: 120,
                        RaceAndEthnicity.NOT_HISPANIC_ASIAN: 114,
                        RaceAndEthnicity.NOT_HISPANIC_BLACK: 122,
                        RaceAndEthnicity.NOT_HISPANIC_UNKNOWN: 420,
                        RaceAndEthnicity.NOT_HISPANIC_MORE_THAN_ONE_RACE: 50,
                        RaceAndEthnicity.NOT_HISPANIC_NATIVE_HAWAIIAN_PACIFIC_ISLANDER: 0,
                        RaceAndEthnicity.NOT_HISPANIC_OTHER: 1030,
                        RaceAndEthnicity.NOT_HISPANIC_WHITE: 1000,
                    }
                )
            ],
        )
        self.reported_admissions_metric = MetricInterface(
            key=prisons.admissions.key,
            value=1000,
            aggregated_dimensions=[
                MetricAggregatedDimensionData(
                    dimension_to_value={
                        OffenseType.DRUG: 1,
                        OffenseType.OTHER: 2,
                        OffenseType.PERSON: 3,
                        OffenseType.PROPERTY: 4,
                        OffenseType.PUBLIC_ORDER: 5,
                        OffenseType.UNKNOWN: 6,
                    }
                )
            ],
        )

        self.calls_for_service_custom_reporting_frequency = schema.Datapoint(
            metric_definition_key=law_enforcement.calls_for_service.key,
            source=self.test_agency_A,
            context_key=REPORTING_FREQUENCY_CONTEXT_KEY,
            value=CustomReportingFrequency(
                frequency=schema.ReportingFrequency.ANNUAL, starting_month=2
            ).to_json_str(),
            is_report_datapoint=False,
        )

    # Spreadsheets
    @staticmethod
    def get_test_spreadsheet(
        system: schema.System,
        user_id: str,
        agency_id: int,
        is_ingested: bool = False,
        upload_offset: int = 0,
    ) -> schema.Spreadsheet:
        uploaded_at = datetime.datetime.now(tz=datetime.timezone.utc)
        return schema.Spreadsheet(
            system=system,
            agency_id=agency_id,
            standardized_name=f"{str(agency_id)}:{system}:{uploaded_at.timestamp()}.xlsx",
            original_name=f"{system.value}_metrics.xlsx",
            uploaded_by=user_id,
            uploaded_at=uploaded_at + (datetime.timedelta(upload_offset)),
            ingested_at=uploaded_at + (datetime.timedelta(upload_offset + 50))
            if is_ingested
            else None,
            ingested_by="auth0_id_B" if is_ingested else None,
            status=schema.SpreadsheetStatus.INGESTED
            if is_ingested
            else schema.SpreadsheetStatus.UPLOADED,
        )

    @staticmethod
    def get_report_for_agency(
        agency: schema.Agency,
        frequency: Optional[str] = "MONTHLY",
        starting_month_str: Optional[str] = "01",
    ) -> schema.Report:
        return schema.Report(
            source=agency,
            type=frequency,
            instance=f"generated_instance_id_{starting_month_str}",
            status=schema.ReportStatus.NOT_STARTED,
            date_range_start=datetime.date.fromisoformat("2022-06-01")
            if frequency == "MONTHLY"
            else datetime.date.fromisoformat(f"2022-{starting_month_str}-01"),
            date_range_end=datetime.date.fromisoformat("2022-07-01")
            if frequency == "MONTHLY"
            else datetime.date.fromisoformat(f"2023-{starting_month_str}-01"),
            project=schema.Project.JUSTICE_COUNTS_CONTROL_PANEL,
            acquisition_method=schema.AcquisitionMethod.CONTROL_PANEL,
            created_at=datetime.date.fromisoformat("2022-05-30"),
        )

    @staticmethod
    def get_funding_metric(
        value: Optional[int] = 100000,
        include_contexts: bool = True,
        nullify_contexts_and_disaggregations: bool = False,
    ) -> MetricInterface:
        return MetricInterface(
            key=law_enforcement.funding.key,
            value=value,
            is_metric_enabled=True,
            contexts=[
                MetricContextData(
                    key=ContextKey.INCLUDES_EXCLUDES_DESCRIPTION,
                    value="our metrics are different because xyz"
                    if not nullify_contexts_and_disaggregations
                    else None,
                ),
            ]
            if include_contexts
            else [],
            aggregated_dimensions=[],
        )

    @staticmethod
    def get_agency_metric_interface(
        include_contexts: bool = False,
        include_disaggregation: bool = False,
        use_partially_disabled_disaggregation: bool = False,
        is_metric_enabled: bool = True,
    ) -> MetricInterface:
        return MetricInterface(
            key=law_enforcement.calls_for_service.key,
            is_metric_enabled=is_metric_enabled,
            contexts=[
                MetricContextData(
                    key=ContextKey.INCLUDES_EXCLUDES_DESCRIPTION,
                    value="our metrics are different because xyz",
                ),
            ]
            if include_contexts
            else [],
            aggregated_dimensions=[
                MetricAggregatedDimensionData(
                    dimension_to_enabled_status={
                        CallType.EMERGENCY: use_partially_disabled_disaggregation,
                        CallType.NON_EMERGENCY: False,
                        CallType.UNKNOWN: False,
                    }
                )
            ]
            if include_disaggregation is True or is_metric_enabled is False
            else [],
        )

    @staticmethod
    def get_agency_datapoints_json(
        use_reenabled_breakdown: bool = False,
        include_contexts: bool = False,
        use_disabled_disaggregation: bool = False,
        use_partially_disabled_disaggregation: bool = False,
        is_metric_enabled: bool = True,
    ) -> Dict[str, Any]:
        """Returns metric dictionaries that are formatted in /metrics/update [POST] style"""
        metric_json = {
            "key": law_enforcement.funding.key,
            "enabled": is_metric_enabled,
        }
        if use_partially_disabled_disaggregation:
            metric_json = {
                "key": law_enforcement.calls_for_service.key,
                "enabled": True,
                "disaggregations": [
                    {
                        "enabled": True,
                        "key": CallType.dimension_identifier(),
                        "dimensions": [
                            {"key": CallType.UNKNOWN.value, "enabled": False},
                            {"key": CallType.EMERGENCY.value, "enabled": False},
                        ],
                    }
                ],
            }
        if use_disabled_disaggregation:
            metric_json = {
                "key": law_enforcement.use_of_force_incidents.key,
                "enabled": True,
                "disaggregations": [
                    {
                        "key": ForceType.dimension_identifier(),
                        "enabled": False,
                    }
                ],
            }
        if use_reenabled_breakdown:
            metric_json = {
                "key": law_enforcement.calls_for_service.key,
                "enabled": True,
                "disaggregations": [
                    {
                        "enabled": True,
                        "key": CallType.dimension_identifier(),
                        "dimensions": [
                            {"key": CallType.UNKNOWN.value, "enabled": True}
                        ],
                    }
                ],
            }

        if include_contexts:
            metric_json["contexts"] = [
                {
                    "key": ContextKey.ADDITIONAL_CONTEXT.name,
                    "value": "this additional context provides contexts",
                }
            ]

        return metric_json

    @staticmethod
    def get_agency_datapoints_request(
        agency_id: int, reset_to_default: Optional[bool] = False
    ) -> Dict[str, Any]:
        return {
            "agency_id": agency_id,
            "metrics": [
                {
                    "key": prisons.funding.key,
                    "enabled": False,
                    "last_update": None,
                },
                {
                    "key": prisons.staff.key,
                    "enabled": True,
                    "last_updated": None,
                    "settings": [
                        {
                            "key": PrisonStaffIncludesExcludes.VOLUNTEER.name,
                            "included": "Yes" if reset_to_default is False else "No",
                        },
                        {
                            "key": PrisonStaffIncludesExcludes.INTERN.name,
                            "included": "Yes" if reset_to_default is False else "No",
                        },
                    ],
                    "disaggregations": [
                        {
                            "enabled": True,
                            "key": StaffType.dimension_identifier(),
                            "dimensions": [
                                {
                                    "key": StaffType.SECURITY.value,
                                    "enabled": False,
                                    "settings": [
                                        {
                                            "key": PrisonSecurityStaffIncludesExcludes.VACANT.name,
                                            "included": "Yes",
                                        },
                                    ]
                                    if reset_to_default is False
                                    else [],
                                },
                                {
                                    "key": StaffType.MANAGEMENT_AND_OPERATIONS.value,
                                    "enabled": False,
                                    "settings": [
                                        {
                                            "key": PrisonManagementAndOperationsStaffIncludesExcludes.VACANT.name,
                                            "included": "Yes",
                                        },
                                    ]
                                    if reset_to_default is False
                                    else [],
                                },
                                {
                                    "key": StaffType.CLINICAL_AND_MEDICAL.value,
                                    "enabled": True,
                                    "settings": [
                                        {
                                            "key": PrisonClinicalStaffIncludesExcludes.VACANT.name,
                                            "included": "Yes",
                                        },
                                    ]
                                    if reset_to_default is False
                                    else [],
                                },
                                {
                                    "key": StaffType.PROGRAMMATIC.value,
                                    "enabled": True,
                                    "settings": [
                                        {
                                            "key": PrisonProgrammaticStaffIncludesExcludes.VACANT.name,
                                            "included": "Yes",
                                        },
                                        {
                                            "key": PrisonProgrammaticStaffIncludesExcludes.VOLUNTEER.name,
                                            "included": "Yes",
                                        },
                                    ]
                                    if reset_to_default is False
                                    else [],
                                },
                                {
                                    "key": StaffType.OTHER.value,
                                    "enabled": True,
                                    "settings": [],
                                    "contexts": [
                                        {
                                            "key": "ADDITIONAL_CONTEXT",
                                            "value": "Other user entered text...",
                                        }
                                    ],
                                },
                                {
                                    "key": StaffType.UNKNOWN.value,
                                    "enabled": True,
                                    "settings": [],
                                    "contexts": [
                                        {
                                            "key": "ADDITIONAL_CONTEXT",
                                            "value": "Unknown user entered text...",
                                        }
                                    ],
                                },
                                {
                                    "key": StaffType.VACANT.value,
                                    "enabled": True,
                                    "settings": [
                                        {
                                            "key": VacantPrisonStaffIncludesExcludes.FILLED.name,
                                            "included": "Yes",
                                        }
                                    ]
                                    if reset_to_default is False
                                    else [],
                                },
                            ],
                        }
                    ],
                },
                {
                    "key": prisons.grievances_upheld.key,
                    "enabled": True,
                    "last_updated": None,
                    "contexts": [
                        {
                            "key": ContextKey.ADDITIONAL_CONTEXT.name,
                            "value": "this additional context provides contexts",
                        }
                    ],
                },
            ],
        }

    @staticmethod
    def get_test_agency_datapoints(
        agency_id: int,
    ) -> List[schema.Datapoint]:
        """Returns agency datapoints that can be used during testing."""
        disabled_metric = schema.Datapoint(
            metric_definition_key=prisons.funding.key,
            enabled=False,
            source_id=agency_id,
            is_report_datapoint=False,
        )
        custom_reporting_frequency = schema.Datapoint(
            metric_definition_key=prisons.funding.key,
            source_id=agency_id,
            context_key=REPORTING_FREQUENCY_CONTEXT_KEY,
            value=(
                CustomReportingFrequency(
                    frequency=schema.ReportingFrequency.ANNUAL, starting_month=2
                ).to_json_str()
            ),
            is_report_datapoint=False,
        )
        excluded_metric_settings_datapoints = [
            schema.Datapoint(
                metric_definition_key=prisons.staff.key,
                includes_excludes_key="VOLUNTEER",
                value="Yes",
                source_id=agency_id,
                is_report_datapoint=False,
            ),
            schema.Datapoint(
                metric_definition_key=prisons.staff.key,
                includes_excludes_key="INTERN",
                value="No",
                source_id=agency_id,
                is_report_datapoint=False,
            ),
        ]
        prefilled_context_datapoint = schema.Datapoint(
            metric_definition_key=prisons.readmissions.key,
            context_key=ContextKey.ADDITIONAL_CONTEXT.name,
            value="this additional context provides contexts",
            source_id=agency_id,
            is_report_datapoint=False,
        )

        disaggregation_datapoints = [
            # Disabled disaggregations
            schema.Datapoint(
                metric_definition_key=prisons.admissions.key,
                dimension_identifier_to_member={
                    OffenseType.dimension_identifier(): OffenseType.PERSON.name
                },
                enabled=False,
                source_id=agency_id,
                is_report_datapoint=False,
            ),
            schema.Datapoint(
                metric_definition_key=prisons.admissions.key,
                dimension_identifier_to_member={
                    OffenseType.dimension_identifier(): OffenseType.PROPERTY.name
                },
                enabled=False,
                source_id=agency_id,
                is_report_datapoint=False,
            ),
            schema.Datapoint(
                metric_definition_key=prisons.admissions.key,
                dimension_identifier_to_member={
                    OffenseType.dimension_identifier(): OffenseType.DRUG.name
                },
                enabled=False,
                source_id=agency_id,
                is_report_datapoint=False,
            ),
            schema.Datapoint(
                metric_definition_key=prisons.admissions.key,
                dimension_identifier_to_member={
                    OffenseType.dimension_identifier(): OffenseType.PUBLIC_ORDER.name
                },
                enabled=False,
                source_id=agency_id,
                is_report_datapoint=False,
            ),
            schema.Datapoint(
                metric_definition_key=prisons.admissions.key,
                dimension_identifier_to_member={
                    OffenseType.dimension_identifier(): OffenseType.OTHER.name
                },
                enabled=False,
                source_id=agency_id,
                is_report_datapoint=False,
            ),
            schema.Datapoint(
                metric_definition_key=prisons.admissions.key,
                dimension_identifier_to_member={
                    OffenseType.dimension_identifier(): OffenseType.UNKNOWN.name
                },
                enabled=False,
                source_id=agency_id,
                is_report_datapoint=False,
            ),
            # Excluded disaggregation settings
            schema.Datapoint(
                metric_definition_key=prisons.releases.key,
                dimension_identifier_to_member={
                    ReleaseType.dimension_identifier(): ReleaseType.TO_PAROLE_SUPERVISION.name
                },
                includes_excludes_key="AFTER_SANCTION",
                source_id=agency_id,
                value="No",
                is_report_datapoint=False,
            ),
            schema.Datapoint(
                metric_definition_key=prisons.releases.key,
                dimension_identifier_to_member={
                    ReleaseType.dimension_identifier(): ReleaseType.TO_PAROLE_SUPERVISION.name
                },
                includes_excludes_key="ELIGIBLE",
                source_id=agency_id,
                value="No",
                is_report_datapoint=False,
            ),
        ]
        return (
            [
                disabled_metric,
                custom_reporting_frequency,
                prefilled_context_datapoint,
            ]
            + disaggregation_datapoints
            + excluded_metric_settings_datapoints
        )

    @staticmethod
    def get_reported_calls_for_service_metric(
        value: Optional[int] = 100,
        emergency_value: Optional[int] = 20,
        unknown_value: Optional[int] = 20,
        include_disaggregations: Optional[bool] = True,
        nullify_contexts_and_disaggregations: Optional[bool] = False,
    ) -> MetricInterface:
        return MetricInterface(
            key=law_enforcement.calls_for_service.key,
            value=value,
            is_metric_enabled=True,
            contexts=[
                MetricContextData(
                    key=ContextKey.INCLUDES_EXCLUDES_DESCRIPTION,
                    value="our metrics are different because xyz"
                    if not nullify_contexts_and_disaggregations
                    else None,
                ),
            ],
            aggregated_dimensions=[
                MetricAggregatedDimensionData(
                    dimension_to_value={
                        CallType.EMERGENCY: emergency_value
                        if not nullify_contexts_and_disaggregations
                        else None,
                        CallType.NON_EMERGENCY: 60
                        if not nullify_contexts_and_disaggregations
                        else None,
                        CallType.OTHER: None,
                        CallType.UNKNOWN: unknown_value
                        if not nullify_contexts_and_disaggregations
                        else None,
                    },
                    dimension_to_enabled_status={
                        CallType.EMERGENCY: None,
                        CallType.NON_EMERGENCY: None,
                        CallType.UNKNOWN: None,
                        CallType.OTHER: None,
                    },
                    dimension_to_includes_excludes_member_to_setting={
                        dimension: {} for dimension in CallType
                    },
                )
            ]
            if include_disaggregations is True
            else [],
        )

    @staticmethod
    def get_reported_crime_metric() -> MetricInterface:
        return MetricInterface(
            key=law_enforcement.reported_crime.key,
            is_metric_enabled=True,
            value=230,
            contexts=[],
            aggregated_dimensions=[
                MetricAggregatedDimensionData(
                    dimension_to_value={
                        OffenseType.DRUG: None,
                        OffenseType.PERSON: None,
                        OffenseType.PROPERTY: None,
                        OffenseType.UNKNOWN: None,
                        OffenseType.OTHER: None,
                    },
                    dimension_to_enabled_status={
                        OffenseType.DRUG: True,
                        OffenseType.PERSON: True,
                        OffenseType.PROPERTY: True,
                        OffenseType.UNKNOWN: True,
                        OffenseType.OTHER: True,
                    },
                )
            ],
        )

    @staticmethod
    def get_arrests_metric() -> MetricInterface:
        return MetricInterface(
            key=law_enforcement.arrests.key,
            is_metric_enabled=True,
            value=120,
            contexts=[
                MetricContextData(
                    key=ContextKey.INCLUDES_EXCLUDES_DESCRIPTION,
                    value="our metrics are different because xyz",
                ),
            ],
            aggregated_dimensions=[
                MetricAggregatedDimensionData(
                    dimension_to_value={
                        OffenseType.DRUG: 60,
                        OffenseType.PERSON: 10,
                        OffenseType.PROPERTY: 40,
                        OffenseType.PUBLIC_ORDER: 0,
                        OffenseType.UNKNOWN: 10,
                        OffenseType.OTHER: 0,
                    },
                    dimension_to_enabled_status={
                        OffenseType.DRUG: True,
                        OffenseType.PERSON: True,
                        OffenseType.PROPERTY: True,
                        OffenseType.PUBLIC_ORDER: True,
                        OffenseType.UNKNOWN: True,
                        OffenseType.OTHER: True,
                    },
                )
            ],
        )

    @staticmethod
    def get_civilian_complaints_sustained_metric() -> MetricInterface:
        return MetricInterface(
            key=law_enforcement.civilian_complaints_sustained.key,
            value=30,
            is_metric_enabled=False,
            contexts=[],
        )
