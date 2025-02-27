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
"""A view containing external data for person level county jail populations to validate against."""

from recidiviz.big_query.big_query_view import SimpleBigQueryViewBuilder
from recidiviz.common.constants.states import StateCode
from recidiviz.utils.environment import GCP_PROJECT_STAGING
from recidiviz.utils.metadata import local_project_id_override
from recidiviz.validation.views import dataset_config

_QUERY_TEMPLATE = """
SELECT 
    region_code,
    person_external_id,
    'US_ID_DOC' as external_id_type,
    facility,
    legal_status,
    date_of_stay,
FROM `{project_id}.{us_id_validation_dataset}.us_id_county_jail_09_2020_incarceration_population`
UNION ALL
SELECT 
    region_code,
    person_external_id,
    external_id_type,
    facility,
    legal_status,
    date_of_stay,
FROM `{project_id}.{us_ix_validation_dataset}.county_jail_incarceration_population_person_level`
"""

COUNTY_JAIL_POPULATION_PERSON_LEVEL_VIEW_BUILDER = SimpleBigQueryViewBuilder(
    dataset_id=dataset_config.EXTERNAL_ACCURACY_DATASET,
    # Note: right now the validation view that consumes this is ID specific
    view_id="county_jail_population_person_level",
    view_query_template=_QUERY_TEMPLATE,
    description="Contains external data for person level county jail populations to "
    "validate against. See http://go/external-validations for instructions on adding "
    "new data.",
    us_id_validation_dataset=dataset_config.validation_dataset_for_state(
        StateCode.US_ID
    ),
    us_ix_validation_dataset=dataset_config.validation_dataset_for_state(
        StateCode.US_IX
    ),
)

if __name__ == "__main__":
    with local_project_id_override(GCP_PROJECT_STAGING):
        COUNTY_JAIL_POPULATION_PERSON_LEVEL_VIEW_BUILDER.build_and_print()
