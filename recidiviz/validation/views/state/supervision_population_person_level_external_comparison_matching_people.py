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

"""A view comparing various values from internal person-level supervision population metrics to the person-level values
from external metrics provided by the state where we both agree that the person was on supervision.
"""

from recidiviz.big_query.big_query_view import SimpleBigQueryViewBuilder
from recidiviz.calculator.query.state import dataset_config as state_dataset_config
from recidiviz.utils.environment import GCP_PROJECT_STAGING
from recidiviz.utils.metadata import local_project_id_override
from recidiviz.validation.views import dataset_config
from recidiviz.validation.views.state.supervision_population_person_level_template import (
    supervision_population_person_level_query,
)

SUPERVISION_POPULATION_PERSON_LEVEL_EXTERNAL_COMPARISON_MATCHING_PEOPLE_VIEW_PREFIX = (
    "supervision_population_person_level_external_comparison_matching_people_"
)

SUPERVISION_POPULATION_PERSON_LEVEL_EXTERNAL_COMPARISON_MATCHING_PEOPLE_DESCRIPTION_PREFIX = """
Compares internal and external lists of person-level supervision populations among rows where we both agree the person is on supervision.
"""
SUPERVISION_POPULATION_PERSON_LEVEL_EXTERNAL_COMPARISON_MATCHING_PEOPLE_WITH_DISTRICT_VIEW_BUILDER = SimpleBigQueryViewBuilder(
    dataset_id=dataset_config.VIEWS_DATASET,
    view_id=SUPERVISION_POPULATION_PERSON_LEVEL_EXTERNAL_COMPARISON_MATCHING_PEOPLE_VIEW_PREFIX
    + "district",
    view_query_template=supervision_population_person_level_query(
        include_unmatched_people=False, external_data_required_fields={"district"}
    ),
    description=SUPERVISION_POPULATION_PERSON_LEVEL_EXTERNAL_COMPARISON_MATCHING_PEOPLE_DESCRIPTION_PREFIX
    + " Only includes external data with supervision district information.",
    external_accuracy_dataset=dataset_config.EXTERNAL_ACCURACY_DATASET,
    materialized_metrics_dataset=state_dataset_config.DATAFLOW_METRICS_MATERIALIZED_DATASET,
    normalized_state_dataset=state_dataset_config.NORMALIZED_STATE_DATASET,
    should_materialize=True,
)

SUPERVISION_POPULATION_PERSON_LEVEL_EXTERNAL_COMPARISON_MATCHING_PEOPLE_WITH_LEVEL_VIEW_BUILDER = SimpleBigQueryViewBuilder(
    dataset_id=dataset_config.VIEWS_DATASET,
    view_id=SUPERVISION_POPULATION_PERSON_LEVEL_EXTERNAL_COMPARISON_MATCHING_PEOPLE_VIEW_PREFIX
    + "supervision_level",
    view_query_template=supervision_population_person_level_query(
        include_unmatched_people=False,
        external_data_required_fields={"supervision_level"},
    ),
    description=SUPERVISION_POPULATION_PERSON_LEVEL_EXTERNAL_COMPARISON_MATCHING_PEOPLE_DESCRIPTION_PREFIX
    + " Only includes external sources with supervision level information.",
    external_accuracy_dataset=dataset_config.EXTERNAL_ACCURACY_DATASET,
    materialized_metrics_dataset=state_dataset_config.DATAFLOW_METRICS_MATERIALIZED_DATASET,
    normalized_state_dataset=state_dataset_config.NORMALIZED_STATE_DATASET,
    should_materialize=True,
)


SUPERVISION_POPULATION_PERSON_LEVEL_EXTERNAL_COMPARISON_MATCHING_PEOPLE_WITH_OFFICER_VIEW_BUILDER = SimpleBigQueryViewBuilder(
    dataset_id=dataset_config.VIEWS_DATASET,
    view_id=SUPERVISION_POPULATION_PERSON_LEVEL_EXTERNAL_COMPARISON_MATCHING_PEOPLE_VIEW_PREFIX
    + "supervising_officer",
    view_query_template=supervision_population_person_level_query(
        include_unmatched_people=False,
        external_data_required_fields={"supervising_officer"},
    ),
    description=SUPERVISION_POPULATION_PERSON_LEVEL_EXTERNAL_COMPARISON_MATCHING_PEOPLE_DESCRIPTION_PREFIX
    + " Only includes external sources with supervising officer information.",
    external_accuracy_dataset=dataset_config.EXTERNAL_ACCURACY_DATASET,
    materialized_metrics_dataset=state_dataset_config.DATAFLOW_METRICS_MATERIALIZED_DATASET,
    normalized_state_dataset=state_dataset_config.NORMALIZED_STATE_DATASET,
    should_materialize=True,
)

if __name__ == "__main__":
    with local_project_id_override(GCP_PROJECT_STAGING):
        SUPERVISION_POPULATION_PERSON_LEVEL_EXTERNAL_COMPARISON_MATCHING_PEOPLE_WITH_DISTRICT_VIEW_BUILDER.build_and_print()
        SUPERVISION_POPULATION_PERSON_LEVEL_EXTERNAL_COMPARISON_MATCHING_PEOPLE_WITH_LEVEL_VIEW_BUILDER.build_and_print()
        SUPERVISION_POPULATION_PERSON_LEVEL_EXTERNAL_COMPARISON_MATCHING_PEOPLE_WITH_OFFICER_VIEW_BUILDER.build_and_print()
