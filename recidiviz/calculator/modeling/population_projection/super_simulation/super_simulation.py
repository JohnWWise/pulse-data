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
"""Highest level simulation object -- runs various comparative scenarios"""

from copy import deepcopy
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

import matplotlib.axes
import pandas as pd

from recidiviz.calculator.modeling.population_projection.full_compartment import (
    FullCompartment,
)
from recidiviz.calculator.modeling.population_projection.population_simulation.population_simulation import (
    PopulationSimulation,
)
from recidiviz.calculator.modeling.population_projection.spark_compartment import (
    SparkCompartment,
)
from recidiviz.calculator.modeling.population_projection.spark_policy import SparkPolicy
from recidiviz.calculator.modeling.population_projection.super_simulation.exporter import (
    Exporter,
)
from recidiviz.calculator.modeling.population_projection.super_simulation.initializer import (
    Initializer,
)
from recidiviz.calculator.modeling.population_projection.super_simulation.simulator import (
    Simulator,
)
from recidiviz.calculator.modeling.population_projection.super_simulation.validator import (
    Validator,
)


class SuperSimulation:
    """Manage the PopulationSimulations and output data needed to run tests, baselines, and policy scenarios"""

    def __init__(
        self,
        initializer: Initializer,
        simulator: Simulator,
        validator: Validator,
        exporter: Exporter,
    ) -> None:

        self.initializer = initializer
        self.simulator = simulator
        self.validator = validator
        self.exporter = exporter

    def simulate_baseline(
        self,
        display_compartments: List[str],
        first_relevant_time_step: Optional[int] = None,
        reset: bool = True,
    ) -> None:
        """
        Calculates a baseline projection.
        `simulation_title` is the desired simulation tag for this baseline
        `first_relevant_time_step` is the time_step at which to start initialization
        """
        first_relevant_time_step = self.initializer.get_first_relevant_time_step(
            first_relevant_time_step
        )
        data_inputs = self.initializer.get_data_inputs()
        user_inputs = self.initializer.get_user_inputs()
        self.simulator.simulate_baseline(
            user_inputs,
            data_inputs,
            display_compartments,
            first_relevant_time_step,
            reset,
        )
        self.validator.reset(self.simulator.get_population_simulations())

    def simulate_policy(
        self, policy_list: List[SparkPolicy], output_compartment: str
    ) -> pd.DataFrame:
        first_relevant_time_step = self.initializer.get_first_relevant_time_step()
        data_inputs = self.initializer.get_data_inputs()
        user_inputs = self.initializer.get_user_inputs()

        simulation_output = self.simulator.simulate_policy(
            user_inputs,
            data_inputs,
            first_relevant_time_step,
            policy_list,
            output_compartment,
        )
        self.validator.reset(
            self.simulator.get_population_simulations(),
            {"policy_simulation": simulation_output},
        )

        return simulation_output.copy()

    def microsim_baseline_over_time(
        self,
        start_run_dates: List[datetime],
        projection_time_steps_override: Optional[int] = None,
    ) -> None:
        """
        Run a microsim at many different run_dates.
        `start_run_dates` should be a list of datetime at which to run the simulation
        """
        user_inputs = deepcopy(self.initializer.get_user_inputs())
        (
            data_inputs_dict,
            first_relevant_time_step_dict,
        ) = self.initializer.get_inputs_for_microsim_baseline_over_time(start_run_dates)

        self.simulator.microsim_baseline_over_time(
            user_inputs,
            data_inputs_dict,
            first_relevant_time_step_dict,
            projection_time_steps_override,
        )
        self.validator.reset(self.simulator.get_population_simulations())

    def upload_baseline_simulation_results_to_bq(
        self,
        simulation_tag: Optional[str] = None,
        override_population_data: Optional[pd.DataFrame] = None,
    ) -> Dict[str, pd.DataFrame]:
        """Upload the baseline (no-policy) simulation results to BigQuery.

        If `override_population_data` data is provided (in the case when there are
        projection intervals created separately), use that instead of the output data
        from the Validator object.
        """

        if override_population_data is None:
            output_data_dict = self.validator.get_output_data_for_upload()
            output_data = output_data_dict["baseline_projections"]
        else:
            output_data = override_population_data

        data_inputs = self.initializer.get_data_inputs()
        excluded_pop_data = data_inputs.excluded_population_data
        user_inputs = self.initializer.get_user_inputs()

        # Use the population from the starting time step to compute the
        # excluded population ratio
        population_data = data_inputs.population_data
        population_data = population_data[
            population_data.time_step == user_inputs.start_time_step
        ]

        # Format the projected outflows data before uploading it
        output_outflows_per_pop_sim = self.simulator.pop_simulations[
            "baseline_projections"
        ].get_outflows()
        # Drop transitions where the compartment and outflow are the same
        output_outflows_per_pop_sim = output_outflows_per_pop_sim[
            output_outflows_per_pop_sim.index.get_level_values("outflow_to")
            != output_outflows_per_pop_sim["compartment"]
        ].copy()

        output_outflows_per_pop_sim[
            "year"
        ] = self.initializer.time_converter.convert_time_steps_to_year(
            output_outflows_per_pop_sim.index.get_level_values("time_step")
        )
        output_outflows_per_pop_sim.reset_index(
            level="time_step", drop=True, inplace=True
        )
        output_outflows_per_pop_sim["cohort_population"] = output_outflows_per_pop_sim[
            "cohort_population"
        ].round(0)
        output_outflows_per_pop_sim = output_outflows_per_pop_sim.groupby(
            ["simulation_group", "compartment", "outflow_to", "year"]
        ).sum()

        output_outflows_per_pop_sim = output_outflows_per_pop_sim.reset_index(
            drop=False
        )

        return self.exporter.upload_baseline_simulation_results_to_bq(
            project_id="recidiviz-staging",
            simulation_tag=simulation_tag,
            output_population_data=output_data,
            output_outflows_data=output_outflows_per_pop_sim,
            excluded_pop=excluded_pop_data,
            total_pop=population_data,
        )

    def upload_policy_simulation_results_to_bq(
        self,
        simulation_tag: Optional[str] = None,
        cost_multipliers: Optional[pd.DataFrame] = None,
    ) -> Optional[Dict[str, pd.DataFrame]]:
        output_data = self.validator.get_output_data_for_upload(macrosim_override=True)

        return self.exporter.upload_policy_simulation_results_to_bq(
            "recidiviz-staging",
            simulation_tag,
            output_data,
            cost_multipliers if cost_multipliers is not None else pd.DataFrame(),
        )

    def upload_validation_projection_results_to_bq(
        self,
        validation_projections_data: pd.DataFrame,
        simulation_tag: Optional[str] = None,
    ) -> None:
        return self.exporter.upload_validation_projection_results_to_bq(
            project_id="recidiviz-staging",
            simulation_tag=simulation_tag,
            validation_projections_data=validation_projections_data,
        )

    def get_population_simulations(self) -> Dict[str, PopulationSimulation]:
        return self.simulator.get_population_simulations()

    def get_arima_output_df(self, simulation_title: str) -> pd.DataFrame:
        return self.validator.gen_arima_output_df(simulation_title)

    def get_arima_output_plots(
        self,
        simulation_title: str,
        fig_size: Tuple[int, int] = (8, 6),
        by_simulation_group: bool = False,
    ) -> List[matplotlib.axes.Axes]:
        return self.validator.gen_arima_output_plots(
            simulation_title, fig_size, by_simulation_group
        )

    def get_admissions_error(self, simulation_title: str) -> pd.DataFrame:
        admissions_data = self.initializer.get_admissions_for_error()
        return self.validator.calculate_admissions_error(
            simulation_title, admissions_data
        )

    def get_population_error(self, simulation_tag: str) -> pd.DataFrame:
        return self.validator.gen_population_error(simulation_tag)

    def get_full_error_output(self, simulation_tag: str) -> pd.DataFrame:
        return self.validator.gen_full_error_output(simulation_tag)

    def calculate_baseline_transition_error(
        self, validation_pairs: Dict[str, str]
    ) -> pd.DataFrame:
        return self.validator.calculate_baseline_admissions_error(validation_pairs)

    def calculate_cohort_hydration_error(
        self,
        output_compartment: str,
        outflow_to: str,
        lower_bound: float = 0,
        upper_bound: float = 2,
        step_size: float = 0.1,
        unit: str = "abs",
    ) -> pd.DataFrame:
        """
        `back_fill_range` is a three item tuple giving the lower and upper bounds to test in units of
            subgroup max_sentence and the step size
        """
        data_inputs = self.initializer.get_data_inputs()
        user_inputs = self.initializer.get_user_inputs()
        max_sentence = self.initializer.get_max_sentence()

        self.simulator.get_cohort_hydration_simulations(
            user_inputs,
            data_inputs,
            int(lower_bound * max_sentence),
            int(upper_bound * max_sentence),
            step_size * max_sentence,
        )

        self.validator.reset(self.simulator.get_population_simulations())
        return self.validator.calculate_cohort_hydration_error(
            output_compartment,
            outflow_to,
            int(lower_bound * max_sentence),
            int(upper_bound * max_sentence),
            step_size * max_sentence,
            unit,
        )

    def override_cross_flow_function(
        self, cross_flow_function: Callable[[pd.DataFrame, int], pd.DataFrame]
    ) -> None:
        """
        Replace default cross flow function with a custom function. Once called, will replace for all future
        simulations.
        `cross_flow_function` should be a callable that accepts a df as an input
        """
        self.initializer.set_override_cross_flow_function(cross_flow_function)

    def get_transitions_data_input(self, *compartments_input: str) -> pd.DataFrame:
        """
        Return user-inputted transitions data, supply 1 or more compartment string names (case-insensitive)
        for specific compartment data (includes all outflow_to values), otherwise returns full transitions df
        """
        inputs = self.initializer.get_data_inputs()

        columns_to_return = [
            "compartment",
            "outflow_to",
            "simulation_group",
            "compartment_duration",
            "cohort_portion",
        ]
        if not compartments_input:
            return inputs.transitions_data[columns_to_return]
        compartments = [c.lower() for c in compartments_input]
        transition_compartments = [
            c.lower() for c in inputs.compartments_architecture.keys()
        ]
        if any(c not in transition_compartments for c in compartments):
            raise ValueError(
                f"At least 1 requested compartment ('{compartments}') not in simulation architechture, available compartments are {transition_compartments}"
            )
        return inputs.transitions_data[
            inputs.transitions_data.compartment.str.lower().isin(compartments)
        ][columns_to_return]

    def get_admissions_data_input(self, *compartments_input: str) -> pd.DataFrame:
        """
        Return user-inputted admissions data, supply 1 or more compartment string names (case-insensitive)
        for specific compartment data, otherwise returns full admissions df
        """
        inputs = self.initializer.get_data_inputs()
        columns_to_return = [
            "compartment",
            "admission_to",
            "simulation_group",
            "time_step",
            "cohort_population",
        ]
        if not compartments_input:
            return inputs.admissions_data[columns_to_return]
        compartments = [c.lower() for c in compartments_input]
        return inputs.admissions_data[
            inputs.admissions_data.compartment.str.lower().isin(compartments)
        ][columns_to_return]

    def get_all_outflows_tables(
        self,
        population_simulations: Optional[List[str]] = None,
        sub_simulations: Optional[List[str]] = None,
        compartments: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Returns all outflow data from simulation, including historical/user-input data and future projected outflows,
        for all policy/sub simulations and compartments
        """
        all_compartments = self._get_all_compartments(
            population_simulations=population_simulations,
            sub_simulations=sub_simulations,
            compartments=compartments,
        )

        all_outflows_tables = {tag: c.outflows.T for tag, c in all_compartments.items()}
        outflows = pd.concat(all_outflows_tables)

        outflows_raw = (
            outflows.melt(
                value_vars=list(outflows.columns),
                var_name="outflow_to",
                value_name="counts",
                ignore_index=False,
            )
            .reset_index()
            .dropna(subset="counts")
        )

        outflows_raw.columns = [
            "policy_sim",
            "simulation_group",
            "compartment",
            "compartment_type",
            "time_step",
            "outflow_to",
            "outflows",
        ]
        return outflows_raw.drop(columns=["compartment_type"])

    def get_population_projections(self, simulation_tag: str) -> pd.DataFrame:
        return self.simulator.pop_simulations[
            simulation_tag
        ].get_population_projections()

    def get_all_sub_simulation_tags(self) -> List[str]:
        for _, pop_sim in self.get_population_simulations().items():
            return list(pop_sim.sub_simulations.keys())
        return []

    def _get_all_compartments(
        self,
        population_simulations: Optional[List[str]] = None,
        sub_simulations: Optional[List[str]] = None,
        compartments: Optional[List[str]] = None,
    ) -> Dict[Tuple[str, str, str, str], SparkCompartment]:
        flattened_compartments = {}
        for pop_sim_tag, pop_sim in self.get_population_simulations().items():
            if population_simulations and pop_sim_tag not in population_simulations:
                continue
            for sub_sim_tag, sub_sim in pop_sim.sub_simulations.items():
                if sub_simulations and sub_sim_tag not in sub_simulations:
                    continue
                for (
                    compartment_tag,
                    compartment,
                ) in sub_sim.simulation_compartments.items():
                    if compartments and compartment_tag not in compartments:
                        continue
                    tag = (
                        pop_sim_tag,
                        sub_sim_tag,
                        compartment_tag,
                        "full" if isinstance(compartment, FullCompartment) else "shell",
                    )
                    flattened_compartments[tag] = compartment
        return flattened_compartments
