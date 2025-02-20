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
"""Verifies that code only depends on modules that are visible to it

Example usage:
$ python -m recidiviz.tools.validate_source_visibility

If you add a new dependency that causes this to fail, you should evaluate whether
this dependency (1) should exist at all and (2) if it should, whether it could be
cleaner. For example, if you need to access some constants related to persistence
from higher-level application code, consider pulling these constants out into a
shared module instead of importing persistence logic into this server.
"""
import sys
from importlib.util import find_spec
from typing import Dict, Iterable, List, Optional, Set

import attr
import pygtrie

from recidiviz.pipelines.utils.pipeline_run_utils import collect_all_pipeline_modules
from recidiviz.vendor.modulefinder import modulefinder

RECIDIVIZ_MODULE = "recidiviz"


def make_module_matcher(modules: Iterable[str]) -> pygtrie.PrefixSet:
    return pygtrie.PrefixSet(
        iterable=modules, factory=pygtrie.StringTrie, separator="."
    )


def module_is_package(module_name: str) -> bool:
    spec = find_spec(module_name)
    if spec is None:
        raise ImportError(f"No module named {module_name}")
    return spec.submodule_search_locations is not None


def is_invalid_recidiviz_dependency(
    name: str,
    valid_module_prefixes: pygtrie.PrefixSet,
) -> bool:
    return (
        name.startswith(RECIDIVIZ_MODULE)
        and not module_is_package(name)
        and name not in valid_module_prefixes
    )


def is_invalid_package_dependency(
    name: str,
    explicitly_invalid_package_dependencies: List[str],
) -> bool:
    return name in explicitly_invalid_package_dependencies and module_is_package(name)


@attr.s(frozen=True, kw_only=True)
class DependencyAnalysisResult:
    invalid_modules: Dict[str, List[str]] = attr.ib()
    missing_modules: Dict[str, List[str]] = attr.ib()

    unused_valid_module_prefixes: Set[str] = attr.ib()
    unused_allowed_missing_module_prefixes: Set[str] = attr.ib()


def get_invalid_dependencies_for_entrypoint(
    entrypoint_file: str,
    valid_module_prefixes: pygtrie.PrefixSet,
    explicitly_invalid_package_dependencies: Optional[List[str]] = None,
    allowed_missing_module_prefixes: Optional[pygtrie.PrefixSet] = None,
) -> DependencyAnalysisResult:
    """Gets the transitive dependencies for the entrypoints and checks their validity.

    Returns two elements. The first is a dictionary of invalid dependency names to the
    call chain that includes them. The second is a list of dependency prefixes that
    were explicitly allowed but that no actual dependencies relied on.
    """
    if allowed_missing_module_prefixes is None:
        allowed_missing_module_prefixes = make_module_matcher(set())

    m = modulefinder.ModuleFinder()
    m.run_script(entrypoint_file)

    valid_dependencies: Set[str] = set()
    invalid_dependencies: Dict[str, List[str]] = {}
    missing_dependencies: Dict[str, List[str]] = {}

    name: str
    for name in m.modules:
        if is_invalid_recidiviz_dependency(name, valid_module_prefixes):
            call_chain = m.call_chain_for_name(name)
            if len(call_chain) < 1:
                raise ValueError(
                    f"invalid {name} module has empty call_chain for file '{entrypoint_file}'"
                )
            if not is_invalid_recidiviz_dependency(
                call_chain[0],
                valid_module_prefixes,
            ):
                invalid_dependencies[name] = call_chain
        elif explicitly_invalid_package_dependencies and is_invalid_package_dependency(
            name, explicitly_invalid_package_dependencies
        ):
            call_chain = m.call_chain_for_package(name, RECIDIVIZ_MODULE)
            if not is_invalid_recidiviz_dependency(
                call_chain[0],
                valid_module_prefixes,
            ):
                invalid_dependencies[name] = call_chain
        else:
            valid_dependencies.add(name)

    for name in m.badmodules:
        # All non-recidiviz dependencies will be missing, we ignore these for now. In
        # the future we could attempt to check if they are actually in the dependency
        # file for the given endpoint (Pipfile, setup.py, Airflow dependencies, etc.).
        if (
            name.startswith(RECIDIVIZ_MODULE)
            and name not in allowed_missing_module_prefixes
        ):
            missing_dependencies[name] = m.call_chain_for_name(name)
        else:
            valid_dependencies.add(name)

    unused_valid = valid_module_prefixes - valid_dependencies
    unused_allowed_missing = allowed_missing_module_prefixes - valid_dependencies

    return DependencyAnalysisResult(
        invalid_modules=invalid_dependencies,
        missing_modules=missing_dependencies,
        unused_valid_module_prefixes={"".join(entry) for entry in unused_valid},
        unused_allowed_missing_module_prefixes={
            "".join(entry) for entry in unused_allowed_missing
        },
    )


def check_dependencies_for_entrypoint(
    entrypoint_file: str,
    valid_module_prefixes: pygtrie.PrefixSet,
    explicitly_invalid_package_dependencies: Optional[List[str]] = None,
    allowed_missing_module_prefixes: Optional[pygtrie.PrefixSet] = None,
) -> bool:
    """Analyzes dependencies for a given entrypoint prints information about failures.

    Returns True for success and False for failure.
    """
    dependency_result = get_invalid_dependencies_for_entrypoint(
        entrypoint_file,
        valid_module_prefixes=valid_module_prefixes,
        explicitly_invalid_package_dependencies=explicitly_invalid_package_dependencies,
        allowed_missing_module_prefixes=allowed_missing_module_prefixes,
    )

    result = True

    if dependency_result.invalid_modules:
        print(f"Invalid dependencies for {entrypoint_file}:")
        for dependency, call_chain in sorted(dependency_result.invalid_modules.items()):
            print(f"\t{dependency}")
            for caller in call_chain:
                print(f"\t\t{caller}")
        result = False

    if dependency_result.missing_modules:
        print(f"Missing internal dependencies for {entrypoint_file}:")
        print("Is this missing an __init__.py file to make it a valid module?")
        for dependency, call_chain in sorted(dependency_result.missing_modules.items()):
            print(f"\t{dependency}")
            for caller in call_chain:
                print(f"\t\t{caller}")
        result = False

    if dependency_result.unused_valid_module_prefixes:
        print(f"Unused valid dependency prefixes for {entrypoint_file}:")
        for dependency in sorted(dependency_result.unused_valid_module_prefixes):
            print(f"\t{dependency}")
        result = False

    if dependency_result.unused_allowed_missing_module_prefixes:
        print(
            f"Dependencies allowed to be missing but are found or not imported for {entrypoint_file}:"
        )
        for dependency in sorted(dependency_result.unused_valid_module_prefixes):
            print(f"\t{dependency}")
        result = False

    return result


def main() -> int:
    """Analyzes each entrypoint in our codebase and ensures that it only depends on
    code from a fixed set of modules.

    This analysis includes transitive dependencies, not just direct ones.

    This is the inverse of how most code visibility enforcement works, where a module
    would define what other modules can depend on it. In the future it may be useful to
    move to that model.

    Note, this currently only deals with recidiviz source, it does not check external
    package dependencies and whether they should be allowed. This could be a
    potential extension, but would be easiest if we used a dependency analysis tool
    that allowed us to limit to only the first layer of external packages, and omit
    any packages that those packages depend on.
    """
    # TODO(#6862): Move entrypoint/visibility configuration to a global yaml or package
    # specific yamls.
    # TODO(#6861): Support enforcing which external packages can be used as well.
    success = True

    for pipeline in collect_all_pipeline_modules():
        if pipeline.__file__ is None:
            raise ValueError(f"No file associated with {pipeline}.")
        valid_prefixes = {
            "recidiviz.big_query.address_overrides",
            "recidiviz.calculator",
            "recidiviz.pipelines",
            "recidiviz.cloud_storage",
            "recidiviz.common",
            "recidiviz.tools",
            "recidiviz.utils",
        }
        if "metrics" in pipeline.__name__ or "normalization" in pipeline.__name__:
            valid_prefixes = valid_prefixes.union(
                {
                    "recidiviz.big_query.big_query_address",
                    "recidiviz.big_query.big_query_query_builder",
                    "recidiviz.big_query.big_query_utils",
                    "recidiviz.big_query.big_query_view",
                    # TODO(#8118): Remove this dependency once IP pre-processing no
                    #  longer relies on ingest mappings
                    "recidiviz.ingest.direct",
                    "recidiviz.datasets.static_data.config",
                    "recidiviz.persistence",
                }
            )
        if (
            "us_id_case_note" in pipeline.__name__
            or "us_ix_case_note" in pipeline.__name__
        ):
            valid_prefixes = valid_prefixes.union(
                {
                    "recidiviz.big_query.big_query_address",
                    "recidiviz.big_query.big_query_query_builder",
                    "recidiviz.big_query.big_query_utils",
                    "recidiviz.big_query.big_query_view",
                    "recidiviz.ingest.direct.types.direct_ingest_instance",
                    "recidiviz.ingest.direct.dataset_config",
                    "recidiviz.persistence",
                }
            )
        if "ingest" in pipeline.__name__:
            valid_prefixes = valid_prefixes.union(
                {
                    "recidiviz.ingest",
                    "recidiviz.persistence",
                    "recidiviz.big_query",
                    "recidiviz.metrics.metric_big_query_view",
                    "recidiviz.justice_counts",
                    "recidiviz.task_eligibility",
                    "recidiviz.case_triage",
                    "recidiviz.outliers",
                    "recidiviz.view_registry",
                    "recidiviz.aggregated_metrics",
                    "recidiviz.datasets",
                    "recidiviz.monitoring",
                    "recidiviz.validation",
                }
            )
        success &= check_dependencies_for_entrypoint(
            pipeline.__file__,
            valid_module_prefixes=make_module_matcher(valid_prefixes),
        )

    valid_calculation_dag_prefixes = {
        "recidiviz.airflow.dags",
        "recidiviz.calculator.query.state.dataset_config",
        "recidiviz.common",
        "recidiviz.cloud_storage",
        "recidiviz.ingest.direct.types.direct_ingest_instance",
        "recidiviz.metrics.export.products",
        "recidiviz.persistence.database.reserved_words",
        "recidiviz.persistence.database.schema_type",
        "recidiviz.pipelines",
        "recidiviz.tools.utils.script_helpers",
        "recidiviz.utils",
        "recidiviz.big_query",
    }

    success &= check_dependencies_for_entrypoint(
        "recidiviz/airflow/dags/calculation_dag.py",
        valid_module_prefixes=make_module_matcher(valid_calculation_dag_prefixes),
        allowed_missing_module_prefixes=make_module_matcher(set()),
    )

    success &= check_dependencies_for_entrypoint(
        "recidiviz/airflow/tests/calculation_dag_test.py",
        valid_module_prefixes=make_module_matcher(
            {
                *valid_calculation_dag_prefixes,
                "recidiviz.airflow",
                "recidiviz.tools.postgres",
            }
        ),
    )

    valid_sftp_dag_prefixes = {
        "recidiviz.airflow.dags",
        "recidiviz.cloud_storage",
        "recidiviz.common.attr_validators",
        "recidiviz.common.constants.states",
        "recidiviz.common.io",
        "recidiviz.common.retry_predicate",
        "recidiviz.ingest.direct",
        "recidiviz.persistence.database.schema_type",
        "recidiviz.utils.environment",
        "recidiviz.utils.metadata",
        "recidiviz.utils.yaml_dict",
        "recidiviz.utils.types",
    }
    success &= check_dependencies_for_entrypoint(
        "recidiviz/airflow/dags/sftp_dag.py",
        valid_module_prefixes=make_module_matcher(valid_sftp_dag_prefixes),
        allowed_missing_module_prefixes=make_module_matcher(set()),
    )

    success &= check_dependencies_for_entrypoint(
        "recidiviz/airflow/tests/sftp_dag_test.py",
        valid_module_prefixes=make_module_matcher(
            {
                *valid_sftp_dag_prefixes,
                "recidiviz.airflow.tests",
                "recidiviz.tools.utils.script_helpers",
                "recidiviz.tools.postgres.local_postgres_helpers",
            }
        ),
    )

    success &= check_dependencies_for_entrypoint(
        "recidiviz/cloud_functions/main.py",
        valid_module_prefixes=make_module_matcher(set()),
    )

    success &= check_dependencies_for_entrypoint(
        "recidiviz/server.py",
        valid_module_prefixes=make_module_matcher(
            {
                "recidiviz.admin_panel",
                "recidiviz.aggregated_metrics",
                "recidiviz.auth",
                "recidiviz.backup",
                "recidiviz.big_query",
                "recidiviz.calculator",
                "recidiviz.pipelines",
                "recidiviz.case_triage",
                "recidiviz.cloud_tasks",
                "recidiviz.cloud_sql",
                "recidiviz.cloud_storage",
                "recidiviz.common",
                "recidiviz.datasets",
                "recidiviz.firestore",
                "recidiviz.ingest",
                "recidiviz.justice_counts",
                "recidiviz.monitoring",
                "recidiviz.metrics",
                "recidiviz.outliers",
                "recidiviz.persistence",
                "recidiviz.workflows",
                "recidiviz.reporting",
                "recidiviz.server_blueprint_registry",
                "recidiviz.server_config",
                "recidiviz.task_eligibility",
                "recidiviz.tools.archive",
                "recidiviz.utils",
                "recidiviz.validation",
                "recidiviz.view_registry",
            }
        ),
        # TODO(#3828): We won't have to explicitly disallow apache_beam once we've
        #  isolated the Dataflow pipeline code completely
        explicitly_invalid_package_dependencies=["apache_beam"],
    )

    success &= check_dependencies_for_entrypoint(
        "recidiviz/case_triage/server.py",
        valid_module_prefixes=make_module_matcher(
            {
                # TODO(#24506): Clean up this dependency
                "recidiviz.aggregated_metrics",
                "recidiviz.calculator",
                "recidiviz.big_query",
                "recidiviz.task_eligibility",
                "recidiviz.ingest",
                # TODO(#6859): Get rid of this dependency
                "recidiviz.pipelines",
                "recidiviz.calculator.query.state.views.dashboard.pathways",
                "recidiviz.calculator.query.state.views.outliers.outliers_enabled_states",
                "recidiviz.case_triage",
                "recidiviz.cloud_memorystore",
                "recidiviz.cloud_storage",
                "recidiviz.common",
                "recidiviz.firestore",
                "recidiviz.monitoring",
                "recidiviz.outliers",
                "recidiviz.persistence",
                "recidiviz.tools.utils.fixture_helpers",
                "recidiviz.utils",
            }
        ),
    )

    success &= check_dependencies_for_entrypoint(
        "recidiviz/justice_counts/control_panel/server.py",
        valid_module_prefixes=make_module_matcher(
            {
                "recidiviz.justice_counts",
                "recidiviz.common",
                "recidiviz.persistence",
                "recidiviz.utils",
                "recidiviz.auth",
                "recidiviz.cloud_storage",
                "recidiviz.monitoring",
                "recidiviz.reporting",
            }
        ),
    )

    success &= check_dependencies_for_entrypoint(
        "recidiviz/entrypoints/monitoring/report_metric_export_timeliness.py",
        valid_module_prefixes=make_module_matcher(
            {
                "recidiviz.common",
                "recidiviz.entrypoints",
                "recidiviz.monitoring",
                "recidiviz.justice_counts",
                "recidiviz.pipelines",
                "recidiviz.ingest.direct",
                "recidiviz.utils",
                "recidiviz.aggregated_metrics",
                "recidiviz.big_query",
                "recidiviz.calculator",
                "recidiviz.case_triage",
                "recidiviz.cloud_storage",
                "recidiviz.datasets",
                "recidiviz.metrics",
                "recidiviz.persistence",
                "recidiviz.task_eligibility",
                "recidiviz.case_triage.views",
                "recidiviz.ingest.views",
                "recidiviz.validation",
                "recidiviz.outliers",
            }
        ),
        # TODO(#3828): We won't have to explicitly disallow apache_beam once we've
        #  isolated the Dataflow pipeline code completely
        explicitly_invalid_package_dependencies=["apache_beam"],
    )

    success &= check_dependencies_for_entrypoint(
        "recidiviz/admin_panel/server.py",
        valid_module_prefixes=make_module_matcher(
            {
                "recidiviz.admin_panel",
                "recidiviz.aggregated_metrics",
                "recidiviz.auth",
                "recidiviz.big_query",
                "recidiviz.calculator",
                "recidiviz.pipelines",
                "recidiviz.case_triage",
                "recidiviz.cloud_sql",
                "recidiviz.cloud_storage",
                "recidiviz.common",
                "recidiviz.datasets",
                "recidiviz.firestore",
                "recidiviz.ingest",
                "recidiviz.justice_counts",
                "recidiviz.metrics",
                "recidiviz.monitoring",
                "recidiviz.outliers",
                "recidiviz.persistence",
                "recidiviz.reporting",
                "recidiviz.server_config",
                "recidiviz.task_eligibility",
                "recidiviz.utils",
                "recidiviz.validation",
                "recidiviz.view_registry",
            }
        ),
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
