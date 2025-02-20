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
"""Unit tests for ingest dag orchestration utils"""
import unittest
from unittest.mock import patch

from recidiviz.airflow.dags.utils.ingest_dag_orchestration_utils import (
    get_ingest_pipeline_enabled_state_and_instance_pairs,
)
from recidiviz.common.constants.states import StateCode
from recidiviz.ingest.direct.types.direct_ingest_instance import DirectIngestInstance


class TestIngestDagOrchestrationUtils(unittest.TestCase):
    """Tests for ingest dag orchestration utils."""

    def setUp(self) -> None:
        self.get_existing_states_patcher = patch(
            "recidiviz.airflow.dags.utils.ingest_dag_orchestration_utils.get_direct_ingest_states_existing_in_env",
            return_value={
                # Has views, environment=production, has env variables in mappings
                StateCode.US_DD,
                # Has views, environment=staging
                StateCode.US_XX,
                # Views gated to secondary only, environment=staging, has env variables in mappings
                StateCode.US_YY,
                # No views, environment=staging
                StateCode.US_WW,
            },
        )
        self.get_existing_states_patcher.start()

        self.ingest_pipeline_can_run_in_dag_patcher = patch(
            "recidiviz.airflow.dags.utils.ingest_dag_orchestration_utils.ingest_pipeline_can_run_in_dag",
            return_value=True,
        )
        self.mock_ingest_pipeline_can_run_in_dag = (
            self.ingest_pipeline_can_run_in_dag_patcher.start()
        )

    def tearDown(self) -> None:
        self.get_existing_states_patcher.stop()
        self.ingest_pipeline_can_run_in_dag_patcher.stop()

    def test_get_ingest_pipeline_enabled_state_and_instance_pairs(self) -> None:
        result = get_ingest_pipeline_enabled_state_and_instance_pairs()

        self.assertSetEqual(
            set(result),
            {
                (StateCode.US_DD, DirectIngestInstance.PRIMARY),
                (StateCode.US_DD, DirectIngestInstance.SECONDARY),
                (StateCode.US_XX, DirectIngestInstance.PRIMARY),
                (StateCode.US_XX, DirectIngestInstance.SECONDARY),
                (StateCode.US_YY, DirectIngestInstance.PRIMARY),
                (StateCode.US_YY, DirectIngestInstance.SECONDARY),
                (StateCode.US_WW, DirectIngestInstance.PRIMARY),
                (StateCode.US_WW, DirectIngestInstance.SECONDARY),
            },
        )

    def test_get_ingest_pipeline_enabled_state_and_instance_pairs_ingest_in_dataflow_not_enabled(
        self,
    ) -> None:
        self.mock_ingest_pipeline_can_run_in_dag.side_effect = (
            lambda state_code, ingest_instance: state_code != StateCode.US_DD
        )

        result = get_ingest_pipeline_enabled_state_and_instance_pairs()

        self.assertSetEqual(
            set(result),
            {
                (StateCode.US_XX, DirectIngestInstance.PRIMARY),
                (StateCode.US_XX, DirectIngestInstance.SECONDARY),
                (StateCode.US_YY, DirectIngestInstance.PRIMARY),
                (StateCode.US_YY, DirectIngestInstance.SECONDARY),
                (StateCode.US_WW, DirectIngestInstance.PRIMARY),
                (StateCode.US_WW, DirectIngestInstance.SECONDARY),
            },
        )
