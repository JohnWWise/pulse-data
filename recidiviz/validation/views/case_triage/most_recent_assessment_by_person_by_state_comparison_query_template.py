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
"""Template for the most recent assessment by person by state comparison"""

# TODO(#8579): Remove the group by clauses once confirmed that there is one row per person.
from recidiviz.calculator.query.state.state_specific_query_strings import (
    get_all_primary_supervision_external_id_types,
)

MOST_RECENT_ASSESSMENT_BY_PERSON_BY_STATE_COMPARISON_QUERY_TEMPLATE = f"""
WITH most_recent_etl_date AS (
  SELECT
    person_external_id,
    state_code AS region_code,
    MAX(most_recent_assessment_date) AS most_recent_assessment_date
  FROM
    `{{project_id}}.{{case_triage_dataset}}.etl_clients_materialized`
  GROUP BY
    person_external_id,
    state_code
), score_on_etl_date AS (
  SELECT
    person_external_id,
    state_code AS region_code,
    most_recent_assessment_date,
    assessment_score
  FROM
    `{{project_id}}.{{case_triage_dataset}}.etl_clients_materialized`
), score_on_most_recent_etl_date AS (
  SELECT
    person_external_id,
    region_code,
    most_recent_assessment_date AS most_recent_etl_date,
    assessment_score AS most_recent_etl_score
  FROM
    most_recent_etl_date
  JOIN
    score_on_etl_date
  USING
    (person_external_id,
      region_code,
      most_recent_assessment_date)
), most_recent_state_assessment AS (
  SELECT
    state_code AS region_code,
    person_id,
    assessment_date AS most_recent_state_date,
    assessment_score AS most_recent_state_score
  FROM (
    SELECT
      *,
      ROW_NUMBER() OVER(PARTITION BY state_code, person_id ORDER BY assessment_date DESC, sequence_num DESC ) AS rn
    FROM
      `{{project_id}}.{{normalized_state_dataset}}.state_assessment`
    WHERE
      assessment_date IS NOT NULL
      AND assessment_type = 'LSIR' OR assessment_type LIKE 'ORAS%')
  WHERE
    rn = 1
), person_to_external_ids AS (
  SELECT
    state_code AS region_code,
    person_id,
    external_id AS person_external_id
  FROM
    `{{project_id}}.{{normalized_state_dataset}}.state_person_external_id`
  WHERE
    id_type IN {get_all_primary_supervision_external_id_types()}
)
SELECT
  region_code,
  person_external_id,
  most_recent_etl_date,
  most_recent_etl_score,
  most_recent_state_date,
  most_recent_state_score
FROM
  score_on_most_recent_etl_date
JOIN (most_recent_state_assessment
  JOIN
    person_to_external_ids
  USING
    (region_code,
      person_id))
USING
  (region_code,
    person_external_id)
"""
