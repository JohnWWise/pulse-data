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
"""Creates the view builder and view for fetching employment periods.

TODO(#5463): In the long term, this should be replaced by ingesting into an `employment_periods`
table, but we are doing this in the short term to deliver an MVP of the Case Triage
experience.
"""

from recidiviz.big_query.big_query_view import SimpleBigQueryViewBuilder
from recidiviz.case_triage.views.dataset_config import CASE_TRIAGE_DATASET
from recidiviz.common.constants.states import StateCode
from recidiviz.ingest.direct.dataset_config import raw_latest_views_dataset_for_region
from recidiviz.ingest.direct.types.direct_ingest_instance import DirectIngestInstance
from recidiviz.utils.environment import GCP_PROJECT_STAGING
from recidiviz.utils.metadata import local_project_id_override

CURRENT_EMPLOYMENT_PERIODS_QUERY_TEMPLATE = """
SELECT
  'US_ID' AS state_code,
  offenders.offendernumber AS person_external_id,
  employers.name AS employer,
  employment.jobtitle AS job_title,
  IF(employment.startdate IS NULL, NULL, PARSE_DATE("%F", SUBSTR(startdate, 0, 10))) AS recorded_start_date,
  IF(employment.enddate IS NULL, NULL, PARSE_DATE("%F", SUBSTR(enddate, 0, 10))) AS recorded_end_date,
  REGEXP_CONTAINS(UPPER(employers.name), r".*UNEMPLOY.*") AS is_unemployed
FROM
    `{project_id}.{us_id_raw_data_up_to_date_dataset}.cis_offender_latest` offenders
LEFT JOIN
  `{project_id}.{us_id_raw_data_up_to_date_dataset}.cis_employment_latest` employment
ON employment.personemploymentid = offenders.id
LEFT JOIN
  `{project_id}.{us_id_raw_data_up_to_date_dataset}.cis_employer_latest` employers
ON
  employers.id = employment.employerid
WHERE
  codeemploymentstatusid = '1'
"""

CURRENT_EMPLOYMENT_PERIODS_DESCRIPTION = """
Provides a period-based view of employment data, indicating start and end date for
 different jobs held by people under the supervision of the state.
 
 Currently only generates data for Idaho."""

CURRENT_EMPLOYMENT_PERIODS_VIEW_BUILDER = SimpleBigQueryViewBuilder(
    dataset_id=CASE_TRIAGE_DATASET,
    view_id="employment_periods",
    description=CURRENT_EMPLOYMENT_PERIODS_DESCRIPTION,
    view_query_template=CURRENT_EMPLOYMENT_PERIODS_QUERY_TEMPLATE,
    should_materialize=True,
    us_id_raw_data_up_to_date_dataset=raw_latest_views_dataset_for_region(
        state_code=StateCode.US_ID, instance=DirectIngestInstance.PRIMARY
    ),
)

if __name__ == "__main__":
    with local_project_id_override(GCP_PROJECT_STAGING):
        CURRENT_EMPLOYMENT_PERIODS_VIEW_BUILDER.build_and_print()
