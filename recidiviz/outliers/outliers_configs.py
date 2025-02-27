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
"""The configuration objects for Outliers states"""
from collections import defaultdict
from typing import Dict, Set

from recidiviz.common.constants.states import StateCode
from recidiviz.outliers.constants import (
    ABSCONSIONS_BENCH_WARRANTS,
    EARLY_DISCHARGE_REQUESTS,
    INCARCERATION_STARTS,
    INCARCERATION_STARTS_AND_INFERRED,
    INCARCERATION_STARTS_AND_INFERRED_TECHNICAL_VIOLATION,
    INCARCERATION_STARTS_TECHNICAL_VIOLATION,
    TASK_COMPLETIONS_FULL_TERM_DISCHARGE,
    TASK_COMPLETIONS_TRANSFER_TO_LIMITED_SUPERVISION,
    VIOLATION_RESPONSES,
    VIOLATIONS,
)
from recidiviz.outliers.types import (
    MetricOutcome,
    OutliersClientEventConfig,
    OutliersConfig,
    OutliersMetricConfig,
)

OUTLIERS_CONFIGS_BY_STATE: Dict[StateCode, OutliersConfig] = {
    StateCode.US_IX: OutliersConfig(
        metrics=[
            OutliersMetricConfig.build_from_metric(
                metric=INCARCERATION_STARTS,
                title_display_name="Incarceration Rate",
                body_display_name="incarceration rate",
                event_name="incarcerations",
                event_name_singular="incarceration",
            ),
            OutliersMetricConfig.build_from_metric(
                metric=ABSCONSIONS_BENCH_WARRANTS,
                title_display_name="Absconsion & Bench Warrant Rate",
                body_display_name="absconsion & bench warrant rate",
                event_name="absconsions & bench warrants",
                event_name_singular="absconsion/bench warrant",
            ),
            OutliersMetricConfig.build_from_metric(
                metric=TASK_COMPLETIONS_FULL_TERM_DISCHARGE,
                title_display_name="Successful Discharge Rate",
                body_display_name="successful discharge rate",
                event_name="successful discharges",
                event_name_singular="successful discharge",
            ),
            OutliersMetricConfig.build_from_metric(
                metric=TASK_COMPLETIONS_TRANSFER_TO_LIMITED_SUPERVISION,
                title_display_name="Limited Supervision Unit Transfer Rate",
                body_display_name="Limited Supervision Unit transfer rate",
                event_name="LSU transfers",
                event_name_singular="LSU transfer",
            ),
            OutliersMetricConfig.build_from_metric(
                metric=EARLY_DISCHARGE_REQUESTS,
                title_display_name="Earned Discharge Request Rate",
                body_display_name="earned discharge request rate",
                event_name="earned discharge requests",
                event_name_singular="earned discharge request",
            ),
        ],
        supervision_officer_label="officer",
        supervision_officer_metric_exclusions="""
        AND avg_daily_population BETWEEN 10 AND 150
        AND prop_period_with_critical_caseload >= 0.75""",
        learn_more_url="https://drive.google.com/file/d/1nMRMNGRFMzk_e7zAcCvuKvMP9YBOeesU/view",
        supervision_staff_exclusions="COALESCE(specialized_caseload_type_primary,'') NOT IN ('OTHER')",
    ),
    StateCode.US_PA: OutliersConfig(
        metrics=[
            OutliersMetricConfig.build_from_metric(
                metric=INCARCERATION_STARTS_AND_INFERRED,
                title_display_name="Incarceration Rate (CPVs & TPVs)",
                body_display_name="incarceration rate",
                event_name="incarcerations",
                event_name_singular="incarceration",
            ),
            OutliersMetricConfig.build_from_metric(
                metric=INCARCERATION_STARTS_AND_INFERRED_TECHNICAL_VIOLATION,
                title_display_name="Technical Incarceration Rate (TPVs)",
                body_display_name="technical incarceration rate",
                event_name="technical incarcerations",
                event_name_singular="technical incarceration",
            ),
            OutliersMetricConfig.build_from_metric(
                metric=ABSCONSIONS_BENCH_WARRANTS,
                title_display_name="Absconsion Rate",
                body_display_name="absconsion rate",
                event_name="absconsions",
                event_name_singular="absconsion",
            ),
        ],
        supervision_officer_label="agent",
        supervision_officer_metric_exclusions="""
        AND avg_daily_population BETWEEN 10 AND 150
        AND prop_period_with_critical_caseload >= 0.75
        AND (avg_population_community_confinement / avg_daily_population) <= 0.05""",
        learn_more_url="https://drive.google.com/file/d/1NvTuKhN-N1-ba1KMI562_z9ka932JqXQ/view",
        supervision_staff_exclusions="COALESCE(supervision_district_id, supervision_district_id_inferred, '') NOT IN ('FAST', 'CO')",
    ),
    StateCode.US_MI: OutliersConfig(
        metrics=[
            OutliersMetricConfig.build_from_metric(
                metric=INCARCERATION_STARTS_AND_INFERRED,
                title_display_name="Incarceration Rate",
                body_display_name="incarceration rate",
                event_name="all incarcerations",
                event_name_singular="incarceration",
            ),
            OutliersMetricConfig.build_from_metric(
                metric=ABSCONSIONS_BENCH_WARRANTS,
                title_display_name="Absconsion & Bench Warrant Rate",
                body_display_name="absconsion & bench warrant rate",
                event_name="absconsions & bench warrants",
                event_name_singular="absconsion/bench warrant",
            ),
            OutliersMetricConfig.build_from_metric(
                metric=INCARCERATION_STARTS_AND_INFERRED_TECHNICAL_VIOLATION,
                title_display_name="Technical Incarceration Rate (TPVs)",
                body_display_name="technical incarceration rate",
                event_name="technical incarcerations",
                event_name_singular="technical incarceration",
            ),
        ],
        client_events=[
            OutliersClientEventConfig.build(
                event=VIOLATIONS, display_name="Violations"
            ),
            OutliersClientEventConfig.build(
                event=VIOLATION_RESPONSES, display_name="Sanctions"
            ),
        ],
        supervision_officer_label="agent",
        supervision_officer_metric_exclusions="""
        AND avg_daily_population BETWEEN 10 AND 150
        AND prop_period_with_critical_caseload >= 0.75
        AND avg_population_unsupervised_supervision_level <= 0.50 """,
        learn_more_url="https://drive.google.com/file/d/1bbjsV6jBr4bkOwTJa8LIfK7oYYxAqa2t/view",
        supervision_district_manager_label="region manager",
        supervision_district_label="region",
    ),
    StateCode.US_TN: OutliersConfig(
        metrics=[
            OutliersMetricConfig.build_from_metric(
                metric=INCARCERATION_STARTS,
                title_display_name="Incarceration Rate",
                body_display_name="incarceration rate",
                event_name="all incarcerations",
                event_name_singular="incarceration",
            ),
            OutliersMetricConfig.build_from_metric(
                metric=ABSCONSIONS_BENCH_WARRANTS,
                title_display_name="Absconsion Rate",
                body_display_name="absconsion rate",
                event_name="absconsions",
                event_name_singular="absconsion",
            ),
            OutliersMetricConfig.build_from_metric(
                metric=INCARCERATION_STARTS_TECHNICAL_VIOLATION,
                title_display_name="Technical Incarceration Rate",
                body_display_name="technical incarceration rate",
                event_name="technical incarcerations",
                event_name_singular="technical incarceration",
            ),
        ],
        client_events=[
            OutliersClientEventConfig.build(
                event=VIOLATIONS, display_name="Violations"
            ),
            OutliersClientEventConfig.build(
                event=VIOLATION_RESPONSES, display_name="Sanctions"
            ),
        ],
        supervision_jii_label="client",
        supervision_officer_label="officer",
        supervision_supervisor_label="manager",
        supervision_unit_label="unit",
        supervision_district_manager_label="district director",
        supervision_officer_metric_exclusions="""
    --TODO(#25695): Revisit this after excluding admin supervision levels    
    AND avg_daily_population BETWEEN 10 AND 175
    AND prop_period_with_critical_caseload >= 0.75""",
        learn_more_url="https://drive.google.com/file/d/1WCNEeftLeTf-c7bcKXKYteg5HykrRba1/view",
    ),
}

METRICS_BY_OUTCOME_TYPE: Dict[MetricOutcome, Set[OutliersMetricConfig]] = defaultdict(
    set
)
for config in OUTLIERS_CONFIGS_BY_STATE.values():
    for metric in config.metrics:
        METRICS_BY_OUTCOME_TYPE[metric.outcome_type].add(metric)
