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
"""SparkCompartment that tracks cohorts internally to determine population size and outflows"""

from typing import Dict

import numpy as np
import pandas as pd

from recidiviz.calculator.modeling.population_projection.cohort_table import CohortTable
from recidiviz.calculator.modeling.population_projection.compartment_transitions import (
    CompartmentTransitions,
)
from recidiviz.calculator.modeling.population_projection.spark_compartment import (
    SparkCompartment,
)
from recidiviz.calculator.modeling.population_projection.utils.transitions_utils import (
    SIG_FIGS,
)


class FullCompartment(SparkCompartment):
    """Complex Spark Compartment that tracks cohorts over time and sends groups to other compartments over time"""

    def __init__(
        self,
        outflow_data: pd.DataFrame,
        compartment_transitions: CompartmentTransitions,
        starting_time_step: int,
        tag: str,
    ) -> None:

        super().__init__(outflow_data, starting_time_step, tag)

        # store all population cohorts with their population counts per time-step
        self.cohorts: CohortTable = CohortTable(starting_time_step)

        # separate incoming cohorts that should be processed after .step_forward()
        self.incoming_cohorts: float = 0

        # transition tables object from compartment out
        self.compartment_transitions = compartment_transitions

        # Series containing compartment population at the end of each time_step in the simulation
        self.end_time_step_populations = pd.Series(dtype=float)

    def single_cohort_initialize(self, compartment_population: int) -> None:
        """Populate cohort table with single starting cohort"""
        self.cohorts.append_time_step_end_count(
            self.cohorts.get_latest_population(), self.current_time_step
        )
        self.ingest_incoming_cohort({self.tag: compartment_population})
        self.create_new_cohort()
        self.prepare_for_next_step()

    def _generate_outflow_dict(self) -> Dict[str, float]:
        """step forward all cohorts one time step and generate outflow dict"""

        per_time_step_transitions = (
            self.compartment_transitions.get_per_time_step_transition_table(
                self.current_time_step
            )
        )

        latest_time_step_pop = self.cohorts.get_latest_population()

        # convert index from starting year to years in compartment
        latest_time_step_pop.index = self.current_time_step - latest_time_step_pop.index

        # no cohort should start in cohort after current_ts
        if any(latest_time_step_pop.index < 0):
            raise ValueError(
                "Cohort cannot start after current time step\n"
                f"Current time step: {self.current_time_step}\n"
                f"Cohort start times: {self.current_time_step - latest_time_step_pop.index}"
            )

        # Handle long/life-sentences separately from shorter sentences, assume the people on longer
        # sentences will never outflow from the compartment during the simulation and only compute
        # the outflows for the people on (relatively) shorter sentences
        latest_time_step_pop_short = latest_time_step_pop[
            latest_time_step_pop.index <= len(per_time_step_transitions)
        ]
        latest_time_step_pop_long = latest_time_step_pop[
            latest_time_step_pop.index > len(per_time_step_transitions)
        ]
        if not np.isclose(latest_time_step_pop_long.fillna(0), 0, SIG_FIGS).all():
            raise ValueError(
                f"cohorts not empty after max sentence: {latest_time_step_pop_long}"
            )

        # broadcast latest cohort populations onto transition table
        latest_time_step_pop_short = per_time_step_transitions.mul(
            latest_time_step_pop_short, axis=0
        ).dropna(how="all")

        latest_time_step_pop = pd.concat(
            [latest_time_step_pop_long, latest_time_step_pop_short.remaining]
        )

        # convert index back to starting year from years in compartment
        latest_time_step_pop.index = self.current_time_step - latest_time_step_pop.index

        self.cohorts.append_time_step_end_count(
            latest_time_step_pop.sort_index(), self.current_time_step
        )

        outflow_dict = {
            outflow: latest_time_step_pop_short.sum(axis=0)[outflow]
            for outflow in latest_time_step_pop_short.columns
            if outflow != "remaining"
        }
        return outflow_dict

    def ingest_incoming_cohort(self, influx: Dict[str, float]) -> None:
        """Ingest the population coming from one compartment into another by the end of the `current_time_step`

        influx: dictionary of cohort type (str) to number of people revoked for the time_step (int)
        """
        if self.tag in influx.keys() and influx[self.tag] != 0:
            self.incoming_cohorts += influx[self.tag]

    def ingest_cross_simulation_cohorts(
        self, cross_simulation_flows: pd.DataFrame
    ) -> None:
        self.cohorts.ingest_cross_simulation_cohorts(
            cross_simulation_flows[cross_simulation_flows.compartment == self.tag].drop(
                "compartment", axis=1
            )
        )

    def step_forward(self) -> None:
        """Simulate one time step in the projection"""
        super().step_forward()
        outflow_dict = self._generate_outflow_dict()

        # If there is a new outflow compartment then create a new index in the outflows df
        missing_keys = [
            key for key in outflow_dict.keys() if key not in self.outflows.index
        ]
        if len(missing_keys) > 0:
            new_rows = pd.DataFrame(
                0, index=missing_keys, columns=self.outflows.columns
            )
            self.outflows = pd.concat([self.outflows, new_rows]).sort_index()

        # if historical data available, use that instead
        if self.current_time_step in self.historical_outflows.columns:
            model_outflow = pd.Series(outflow_dict, dtype=float)
            outflow_dict = self.historical_outflows[self.current_time_step].to_dict()
            self.error[self.current_time_step] = (
                100
                * (model_outflow - self.historical_outflows[self.current_time_step])
                / self.historical_outflows[self.current_time_step]
            )

        # if prior to historical data, interpolate from earliest ts of data
        elif not self.historical_outflows.empty and self.current_time_step < min(
            self.historical_outflows.columns
        ):
            # TODO(#5431): replace outflows during initialization with better backward projection
            outflow_dict = self.historical_outflows[
                min(self.historical_outflows.columns)
            ].to_dict()

        # if no outflow, don't ingest to edges
        if not bool(outflow_dict):
            return

        # Store the outflows with the previous time step since transitions from the last
        # time step get us the total population for this time step
        self.outflows.loc[:, self.current_time_step - 1] = outflow_dict

        for edge in self.edges:
            edge.ingest_incoming_cohort(outflow_dict)

    def create_new_cohort(self) -> None:
        """Create a new cohort from new admissions from other compartments"""
        self.cohorts.append_cohort(self.incoming_cohorts, self.current_time_step)
        self.incoming_cohorts = 0

    def prepare_for_next_step(self) -> None:
        """Clean up any data structures and move the time step 1 unit forward"""
        # move the incoming cohort into the cohorts list
        if self.current_time_step in self.end_time_step_populations:
            raise ValueError(
                f"Cannot prepare_for_next_step() if population already recorded for this time step \n"
                f"time step {self.current_time_step} already in end_time_step_populations"
            )
        self.end_time_step_populations = pd.concat(
            [
                self.end_time_step_populations,
                pd.Series({self.current_time_step: self.get_current_population()}),
            ]
        )

        super().prepare_for_next_step()

    def scale_cohorts(self, scale_factor: float) -> None:
        self.cohorts.scale_cohort_size(scale_factor)

    def get_per_time_step_population(self) -> pd.Series:
        """Return the per_time_step projected population as a pd.Series of counts per EOTS"""
        return self.end_time_step_populations

    def get_current_population(self) -> float:
        return self.cohorts.get_latest_population().sum()

    def get_cohort_df(self) -> pd.DataFrame:
        return self.cohorts.pop_cohorts()
