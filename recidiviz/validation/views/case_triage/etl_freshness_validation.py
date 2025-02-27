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
"""A view that can be used to validate that the Case Triage ETL has been exported within SLA."""
from recidiviz.case_triage.views.dataset_config import CASE_TRIAGE_DATASET
from recidiviz.utils.environment import GCP_PROJECT_STAGING
from recidiviz.utils.metadata import local_project_id_override
from recidiviz.validation.views.case_triage.utils import MAX_DAYS_STALE
from recidiviz.validation.views.dataset_config import VIEWS_DATASET
from recidiviz.validation.views.utils.freshness_validation import (
    FreshnessValidation,
    FreshnessValidationAssertion,
)

ETL_TABLES = ["etl_clients", "etl_opportunities"]

ETL_EXPORTED_ASSERTIONS = [
    FreshnessValidationAssertion(
        region_code="US_ID",
        assertion_name=f"{etl_table.upper()}_WAS_EXPORTED",
        description="Checks that we've exported data in the last 24 hours",
        dataset=CASE_TRIAGE_DATASET,
        table=f"{etl_table}_materialized",
        date_column_clause="CAST(exported_at AS DATE)",
        allowed_days_stale=MAX_DAYS_STALE,
    )
    for etl_table in ETL_TABLES
]

ETL_FRESHNESS_VALIDATION_VIEW_BUILDER = FreshnessValidation(
    dataset=VIEWS_DATASET,
    view_id="case_triage_etl_freshness",
    description="Builds validation table to ensure Case Triage ETL tables are exported within SLA.",
    assertions=ETL_EXPORTED_ASSERTIONS,
).to_big_query_view_builder()

if __name__ == "__main__":
    with local_project_id_override(GCP_PROJECT_STAGING):
        ETL_FRESHNESS_VALIDATION_VIEW_BUILDER.build_and_print()
