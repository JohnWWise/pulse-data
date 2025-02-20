# Recidiviz - a data platform for criminal justice reform
# Copyright (C) 2022 Recidiviz, Inc.
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
"""
Unit test to ensure that the DAGs are valid and will be properly loaded into the Airflow UI.
"""
import os
import unittest
from unittest.mock import patch

from airflow.models import DagBag

from recidiviz.airflow.dags.monitoring.task_failure_alerts import (
    DISCRETE_CONFIGURATION_PARAMETERS,
    KNOWN_CONFIGURATION_PARAMETERS,
)
from recidiviz.airflow.tests.test_utils import DAG_FOLDER


@patch(
    "os.environ",
    {
        "GCP_PROJECT": "recidiviz-testing",
    },
)
class TestDagIntegrity(unittest.TestCase):
    """Tests the dags defined in the /dags package."""

    def test_dag_bag_import(self) -> None:
        """
        Verify that Airflow will be able to import all DAGs in the repository without errors
        """
        dag_bag = DagBag(dag_folder=DAG_FOLDER, include_examples=False)
        self.assertEqual(
            len(dag_bag.import_errors),
            0,
            f"There should be no DAG failures. Got: {dag_bag.import_errors}",
        )

    def test_render_template_as_native(self) -> None:
        """
        Verify all DAGs utilize the native template rendering used in our Kubernetes pod operators
        """
        dag_bag = DagBag(dag_folder=DAG_FOLDER, include_examples=False)
        self.assertNotEqual(len(dag_bag.dags), 0)
        for dag in dag_bag.dags.values():
            self.assertTrue(dag.render_template_as_native_obj)

    def test_correct_dag(self) -> None:
        """
        Verify that the DAGs discovered have the correct name
        """
        dag_bag = DagBag(dag_folder=DAG_FOLDER, include_examples=False)
        self.assertSetEqual(
            set(dag_bag.dag_ids),
            {
                "recidiviz-testing_calculation_dag",
                "recidiviz-testing_sftp_dag",
                "recidiviz-testing_hourly_monitoring_dag",
                "recidiviz-testing_ingest_dag",
            },
        )

    def test_discrete_parameters_registered(self) -> None:
        """
        Verify that the DAGs have their configuration parameters registered
        """

        # _project_id is None at definition time
        parameter_keys_with_project = [
            key.replace("None_", f'{os.environ["GCP_PROJECT"]}_')
            for key in DISCRETE_CONFIGURATION_PARAMETERS
        ]

        dag_bag = DagBag(dag_folder=DAG_FOLDER, include_examples=False)
        self.assertSetEqual(
            set(parameter_keys_with_project),
            set(dag_bag.dag_ids),
        )

    def test_discrete_parameters_match_known_configuration_parameters(self) -> None:
        for (
            dag_id,
            discrete_parameters_list,
        ) in DISCRETE_CONFIGURATION_PARAMETERS.items():

            known_params_set = set(KNOWN_CONFIGURATION_PARAMETERS[dag_id])

            missing_params = set(discrete_parameters_list) - known_params_set
            if missing_params:
                self.fail(
                    f"Found parameters defined in DISCRETE_CONFIGURATION_PARAMETERS "
                    f"for dag [{dag_id}] which are not defined for that DAG in "
                    f"KNOWN_CONFIGURATION_PARAMETERS: {missing_params}"
                )
