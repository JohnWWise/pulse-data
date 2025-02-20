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
"""Control logic for the CloudSQL -> BigQuery refresh."""
import datetime
import logging
import time
import uuid
from typing import Optional

from recidiviz.big_query.big_query_client import BigQueryClientImpl
from recidiviz.big_query.success_persister import RefreshBQDatasetSuccessPersister
from recidiviz.cloud_storage.gcs_pseudo_lock_manager import GCSPseudoLockAlreadyExists
from recidiviz.ingest.direct.types.direct_ingest_instance import DirectIngestInstance
from recidiviz.persistence.database.bq_refresh.cloud_sql_to_bq_lock_manager import (
    CloudSqlToBQLockManager,
)
from recidiviz.persistence.database.bq_refresh.cloud_sql_to_bq_refresh_config import (
    CloudSqlToBQConfig,
)
from recidiviz.persistence.database.bq_refresh.federated_cloud_sql_to_bq_refresh import (
    federated_bq_schema_refresh,
)
from recidiviz.persistence.database.bq_refresh.union_dataflow_ingest import (
    combine_ingest_sources_into_single_state_dataset,
)
from recidiviz.persistence.database.schema_type import SchemaType
from recidiviz.pipelines.state_update_lock_manager import StateUpdateLockManager
from recidiviz.utils.environment import gcp_only

LOCK_WAIT_SLEEP_INTERVAL_SECONDS = 60  # 1 minute
LOCK_WAIT_SLEEP_MAXIMUM_TIMEOUT = 60 * 60 * 4  # 4 hours


def _lock_sql_to_bq_refresh(
    lock_manager: CloudSqlToBQLockManager,
    schema_type: SchemaType,
    ingest_instance: DirectIngestInstance,
) -> None:
    """
    Acquires the lock for the Cloud SQL to BQ refresh for a given schema_type and
    ingest_instance. Will try up to LOCK_WAIT_SLEEP_MAXIMUM_TIMEOUT seconds to
    acquire the lock.
    """
    secs_waited = 0
    lock_acquired = False
    can_proceed = False
    while secs_waited < LOCK_WAIT_SLEEP_MAXIMUM_TIMEOUT:
        try:
            if not lock_acquired:
                lock_manager.acquire_lock(
                    lock_id=str(uuid.uuid4()),
                    schema_type=schema_type,
                    ingest_instance=ingest_instance,
                )
                lock_acquired = True
            if can_proceed := lock_manager.can_proceed(schema_type, ingest_instance):
                break
        except GCSPseudoLockAlreadyExists:
            logging.warning(
                "Found lock already exists for schema type [%s] and instance [%s]. "
                "This may happen if another sandbox DAG is running at the same "
                "time. Will wait to attempt to acquire the lock again.",
                schema_type.value,
                ingest_instance.value,
            )
        finally:
            if not can_proceed:
                logging.info(
                    "Waiting to acquire lock for schema type [%s] and instance [%s]...",
                    schema_type.value,
                    ingest_instance.value,
                )
                time.sleep(LOCK_WAIT_SLEEP_INTERVAL_SECONDS)
                secs_waited += LOCK_WAIT_SLEEP_INTERVAL_SECONDS

    if not can_proceed:
        raise ValueError(
            f"Could not acquire lock after waiting {LOCK_WAIT_SLEEP_MAXIMUM_TIMEOUT} seconds for {schema_type} in {ingest_instance}."
        )


@gcp_only
def execute_cloud_sql_to_bq_refresh(
    schema_type: SchemaType,
    ingest_instance: DirectIngestInstance,
    sandbox_prefix: Optional[str] = None,
) -> None:
    """Executes the Cloud SQL to BQ refresh for a given schema_type, ingest instance and
    sandbox_prefix."""
    if not CloudSqlToBQConfig.is_valid_schema_type(schema_type):
        raise ValueError(f"Unsupported schema type: [{schema_type}]")

    cloud_sql_to_bq_lock_manager = CloudSqlToBQLockManager()
    state_update_lock_manager = StateUpdateLockManager(ingest_instance)
    state_update_lock_manager_lock_id = str(uuid.uuid4())

    try:
        # TODO(#20930): Remove once all states no longer writing to postgres
        _lock_sql_to_bq_refresh(
            cloud_sql_to_bq_lock_manager, schema_type, ingest_instance
        )
        if schema_type == SchemaType.STATE:
            state_update_lock_manager.acquire_lock(
                lock_id=state_update_lock_manager_lock_id,
                lock_wait_timeout=LOCK_WAIT_SLEEP_MAXIMUM_TIMEOUT,
            )
        start = datetime.datetime.now()

        exported_tables = federated_bq_schema_refresh(
            schema_type=schema_type,
            direct_ingest_instance=ingest_instance
            if schema_type == SchemaType.STATE
            else None,
            dataset_override_prefix=sandbox_prefix,
        )
        if schema_type == SchemaType.STATE:
            # TODO(#20930): Separate this out into its own endpoint that runs in
            # parallel to bq refresh once we only ever use dataflow ingest output.
            combine_ingest_sources_into_single_state_dataset(
                ingest_instance=ingest_instance,
                tables=exported_tables,
                output_sandbox_prefix=sandbox_prefix,
            )

        end = datetime.datetime.now()
        runtime_sec = int((end - start).total_seconds())
        success_persister = RefreshBQDatasetSuccessPersister(
            bq_client=BigQueryClientImpl()
        )
        success_persister.record_success_in_bq(
            schema_type=schema_type,
            direct_ingest_instance=ingest_instance,
            dataset_override_prefix=sandbox_prefix,
            runtime_sec=runtime_sec,
        )
    finally:
        cloud_sql_to_bq_lock_manager.release_lock(schema_type, ingest_instance)
        if schema_type == SchemaType.STATE:
            state_update_lock_manager.release_lock(state_update_lock_manager_lock_id)
