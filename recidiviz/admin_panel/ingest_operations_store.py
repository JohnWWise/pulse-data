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
"""Store used to keep information related to direct ingest operations"""
import json
import logging
from collections import Counter, defaultdict
from concurrent import futures
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from google.cloud import tasks_v2

from recidiviz.admin_panel.admin_panel_store import AdminPanelStore
from recidiviz.admin_panel.ingest_dataflow_operations import (
    DataflowPipelineMetadataResponse,
    get_all_latest_ingest_jobs,
)
from recidiviz.big_query.big_query_client import (
    BQ_CLIENT_MAX_POOL_SIZE,
    BigQueryClientImpl,
)
from recidiviz.cloud_storage.gcsfs_factory import GcsfsFactory
from recidiviz.cloud_storage.gcsfs_path import GcsfsDirectoryPath, GcsfsFilePath
from recidiviz.common.constants.operations.direct_ingest_instance_status import (
    DirectIngestStatus,
)
from recidiviz.common.constants.states import StateCode
from recidiviz.common.serialization import attr_from_json_dict, attr_to_json_dict
from recidiviz.ingest.direct import direct_ingest_regions
from recidiviz.ingest.direct.dataset_config import raw_tables_dataset_for_region
from recidiviz.ingest.direct.direct_ingest_cloud_task_queue_manager import (
    DirectIngestCloudTaskQueueManagerImpl,
    get_direct_ingest_queues_for_state,
)
from recidiviz.ingest.direct.direct_ingest_regions import get_direct_ingest_region
from recidiviz.ingest.direct.gating import is_ingest_in_dataflow_enabled
from recidiviz.ingest.direct.gcs.direct_ingest_gcs_file_system import (
    DirectIngestGCSFileSystem,
)
from recidiviz.ingest.direct.gcs.directory_path_utils import (
    gcsfs_direct_ingest_bucket_for_state,
    gcsfs_direct_ingest_storage_directory_path_for_state,
)
from recidiviz.ingest.direct.gcs.filename_parts import filename_parts_from_path
from recidiviz.ingest.direct.ingest_view_materialization.instance_ingest_view_contents import (
    InstanceIngestViewContentsImpl,
)
from recidiviz.ingest.direct.metadata.direct_ingest_file_metadata_manager import (
    DirectIngestRawFileMetadataSummary,
)
from recidiviz.ingest.direct.metadata.direct_ingest_view_materialization_metadata_manager import (
    DirectIngestViewMaterializationMetadataManagerImpl,
)
from recidiviz.ingest.direct.metadata.postgres_direct_ingest_file_metadata_manager import (
    PostgresDirectIngestRawFileMetadataManager,
)
from recidiviz.ingest.direct.metadata.postgres_direct_ingest_instance_status_manager import (
    PostgresDirectIngestInstanceStatusManager,
)
from recidiviz.ingest.direct.raw_data.raw_file_configs import (
    DirectIngestRegionRawFileConfig,
)
from recidiviz.ingest.direct.regions.direct_ingest_region_utils import (
    get_direct_ingest_states_existing_in_env,
    get_direct_ingest_states_launched_in_env,
)
from recidiviz.ingest.direct.types.direct_ingest_instance import DirectIngestInstance
from recidiviz.ingest.direct.types.errors import (
    DirectIngestError,
    DirectIngestInstanceError,
)
from recidiviz.ingest.direct.types.instance_database_key import database_key_for_state
from recidiviz.persistence.entity.operations.entities import DirectIngestInstanceStatus
from recidiviz.utils import metadata
from recidiviz.utils.types import assert_type

BucketSummaryType = Dict[str, Union[str, int]]


class IngestOperationsStore(AdminPanelStore):
    """
    A store for tracking the current state of direct ingest.
    """

    def __init__(self) -> None:
        self.fs = DirectIngestGCSFileSystem(GcsfsFactory.build())
        self.cloud_task_manager = DirectIngestCloudTaskQueueManagerImpl()
        self.cloud_tasks_client = tasks_v2.CloudTasksClient()
        self.bq_client = BigQueryClientImpl()
        self.cache_key = f"{self.__class__}"

    def hydrate_cache(self) -> None:
        latest_jobs = get_all_latest_ingest_jobs()
        self.set_cache(latest_jobs)

    def set_cache(
        self,
        latest_jobs: Dict[
            StateCode,
            Dict[DirectIngestInstance, Optional[DataflowPipelineMetadataResponse]],
        ],
    ) -> None:

        jobs_dict = {
            state_code.value: {
                instance.value: attr_to_json_dict(
                    job,  # type: ignore[arg-type]
                )
                if job
                else None
                for instance, job in responses_by_instance.items()
            }
            for state_code, responses_by_instance in latest_jobs.items()
        }

        jobs_json = json.dumps(jobs_dict)

        self.redis.set(
            self.cache_key,
            jobs_json,
        )

    def get_most_recent_dataflow_job_statuses(
        self,
    ) -> Dict[
        StateCode,
        Dict[DirectIngestInstance, Optional[DataflowPipelineMetadataResponse]],
    ]:
        """Retrieve the most recent dataflow job statuses for each state from the cache if available, or via
        new requests to the dataflow API."""
        jobs_json = self.redis.get(self.cache_key)
        if not jobs_json:
            self.hydrate_cache()
            jobs_json = self.redis.get(self.cache_key)

        if not jobs_json:
            raise ValueError(
                "Expected the cache to have dataflow jobs hydrated by this point."
            )
        parsed_jobs_dict = json.loads(jobs_json)

        rehydrated_jobs: Dict[
            StateCode,
            Dict[DirectIngestInstance, Optional[DataflowPipelineMetadataResponse]],
        ] = defaultdict(dict)
        for state_code in get_direct_ingest_states_existing_in_env():
            # There is an edge case where if a state was newly added, it would not
            # appear in the cache results yet. We allow for this and just add a None
            # value for pipeline results until the cache is next hydrated.
            responses_by_instance = parsed_jobs_dict.get(state_code.value)
            for instance in DirectIngestInstance:
                job_dict = (
                    responses_by_instance.get(instance.value)
                    if responses_by_instance
                    else None
                )
                rehydrated_jobs[state_code][instance] = (
                    assert_type(
                        attr_from_json_dict(job_dict), DataflowPipelineMetadataResponse
                    )
                    if job_dict
                    else None
                )

        return rehydrated_jobs

    @property
    def state_codes_launched_in_env(self) -> List[StateCode]:
        return get_direct_ingest_states_launched_in_env()

    def _verify_clean_secondary_raw_data_state(self, state_code: StateCode) -> None:
        """Confirm that all raw file metadata / data has been invalidated and the BQ raw data dataset is clean in
        SECONDARY."""
        raw_data_manager = PostgresDirectIngestRawFileMetadataManager(
            region_code=state_code.value,
            raw_data_instance=DirectIngestInstance.SECONDARY,
        )

        # Confirm there aren't non-invalidated raw files for the instance. The metadata state should be completely
        # clean before kicking off a rerun.
        if len(raw_data_manager.get_non_invalidated_files()) != 0:
            raise DirectIngestInstanceError(
                "Cannot kick off ingest rerun, as there are still unprocessed raw files on Postgres."
            )

        # Confirm that all the tables in the `us_xx_raw_data_secondary` on BQ are empty
        secondary_raw_data_dataset = raw_tables_dataset_for_region(
            state_code=state_code, instance=DirectIngestInstance.SECONDARY
        )
        query = (
            "SELECT SUM(size_bytes) as total_bytes FROM "
            f"{metadata.project_id()}.{secondary_raw_data_dataset}.__TABLES__"
        )
        query_job = self.bq_client.run_query_async(
            query_str=query, use_query_cache=False
        )
        results = list(query_job)
        if int(results[0]["total_bytes"]) > 0:
            raise DirectIngestInstanceError(
                f"There are tables in {secondary_raw_data_dataset} that are not empty. Cannot proceed with "
                f"ingest rerun."
            )

    def _verify_clean_ingest_view_state(
        self, state_code: StateCode, instance: DirectIngestInstance
    ) -> None:
        """Confirm that all ingest view metadata / data has been invalidated."""

        # Confirm that all metadata about ingest view materialization has been
        # invalidated for this instance.
        ingest_view_materialization_manager = (
            DirectIngestViewMaterializationMetadataManagerImpl(
                state_code.value, instance
            )
        )

        # If instance summaries is empty, that means that all ingest view
        # materialization metadata has been invalidated.
        if len(ingest_view_materialization_manager.get_instance_summaries()) != 0:
            raise DirectIngestInstanceError(
                "Cannot kick off ingest rerun, as not all ingest view materialization"
                "metadata has been invalidated on Postgres."
            )

        # Confirm that there aren't any materialized ingest view results in BQ.
        ingest_view_contents = InstanceIngestViewContentsImpl(
            self.bq_client, state_code.value, instance, dataset_prefix=None
        )
        dataset_id = ingest_view_contents.results_dataset()
        if (
            self.bq_client.dataset_exists(dataset_id)
            and len(list(self.bq_client.list_tables(dataset_id))) > 0
        ):
            raise DirectIngestInstanceError(
                f"There are ingest view results in {dataset_id} that have not been"
                f"cleaned up. Cannot proceed with ingest rerun."
            )

    def trigger_task_scheduler(
        self, state_code: StateCode, instance: DirectIngestInstance
    ) -> None:
        """This function creates a cloud task to schedule the next job for a given state code and instance.
        Requires:
        - state_code: (required) State code to start ingest for (i.e. "US_ID")
        - instance: (required) Which instance to start ingest for (either PRIMARY or SECONDARY)
        """
        can_start_ingest = state_code in self.state_codes_launched_in_env

        formatted_state_code = state_code.value.lower()
        region = get_direct_ingest_region(formatted_state_code)

        logging.info(
            "Creating cloud task to schedule next job and kick ingest for %s instance in %s.",
            instance,
            formatted_state_code,
        )
        self.cloud_task_manager.create_direct_ingest_handle_new_files_task(
            region=region,
            ingest_instance=instance,
            can_start_ingest=can_start_ingest,
        )

    def update_ingest_queues_state(
        self, state_code: StateCode, new_queue_state: str
    ) -> None:
        """This function is called through the Ingest Operations UI in the admin panel.
        It updates the state of the ingest-related queues by either pausing or resuming the
        queues.

        Requires:
        - state_code: (required) State code to pause queues for
        - new_queue_state: (required) The state to set the queues
        """
        self.cloud_task_manager.update_ingest_queue_states_str(
            state_code=state_code, new_queue_state_str=new_queue_state
        )

    def purge_ingest_queues(
        self,
        state_code: StateCode,
    ) -> None:
        """This function is called through the flash checklist in the admin panel. It purges all tasks in the
        ingest queues for the specified state."""
        queues_to_purge = sorted(get_direct_ingest_queues_for_state(state_code))

        for queue in queues_to_purge:
            self.cloud_task_manager.purge_queue(queue_name=queue)

    def get_ingest_queue_states(self, state_code: StateCode) -> List[Dict[str, str]]:
        """Returns a list of dictionaries that contain the name and states of direct ingest queues for a given region"""
        ingest_queue_states = self.cloud_task_manager.get_ingest_queue_states(
            state_code
        )

        return [
            {"name": queue_info["name"], "state": queue_info["state"].name}
            for queue_info in ingest_queue_states
        ]

    # TODO(#20930): Delete this function once ingest in Dataflow is enabled for all
    #  states.
    def start_ingest_rerun(
        self,
        state_code: StateCode,
        instance: DirectIngestInstance,
        raw_data_source_instance: DirectIngestInstance,
    ) -> None:
        """Kicks off an ingest rerun in the specified instance.
        Requires:
        - state_code: (required) State code to start ingest rerun for (i.e. "US_ID")
        - instance: (required) Ingest instance to start ingest rerun for (i.e. SECONDARY)
        - raw_data_source_instance: (required)  Source instance of raw data (i.e. PRIMARY)
        """
        if is_ingest_in_dataflow_enabled(state_code, instance):
            raise ValueError(
                f"Cannot start an ingest rerun for a state with ingest in Dataflow "
                f"enabled: {state_code.value}"
            )

        formatted_state_code = state_code.value.lower()

        # TODO(#13406): remove check once this rerun endpoint can be triggered in
        #  PRIMARY as well.
        if instance != DirectIngestInstance.SECONDARY:
            raise DirectIngestInstanceError(
                "Ingest reruns can only be kicked off for SECONDARY instances."
            )

        region = direct_ingest_regions.get_direct_ingest_region(
            region_code=formatted_state_code
        )
        if not self.cloud_task_manager.all_ingest_instance_queues_are_empty(
            region, instance
        ):
            raise DirectIngestInstanceError(
                "Cannot kick off ingest rerun because not all ingest related queues are "
                "empty. Please check queues on Ingest Operations Admin Panel to see "
                "which have remaining tasks."
            )

        if raw_data_source_instance == DirectIngestInstance.SECONDARY:
            self._verify_clean_secondary_raw_data_state(state_code)

        # Confirm that all ingest view metadata / data has been invalidated.
        self._verify_clean_ingest_view_state(state_code, instance)

        # Validation that a rerun is a valid status transition is handled within the
        # instance manager.
        instance_status_manager = PostgresDirectIngestInstanceStatusManager(
            region_code=formatted_state_code,
            ingest_instance=instance,
            is_ingest_in_dataflow_enabled=is_ingest_in_dataflow_enabled(
                state_code, instance
            ),
        )
        instance_status_manager.change_status_to(
            DirectIngestStatus.STANDARD_RERUN_STARTED
            if raw_data_source_instance == DirectIngestInstance.PRIMARY
            else DirectIngestStatus.RERUN_WITH_RAW_DATA_IMPORT_STARTED
        )

        self.trigger_task_scheduler(state_code, instance)

    def start_secondary_raw_data_reimport(self, state_code: StateCode) -> None:
        """Enables the SECONDARY instance for |state_code| so that it can import
        any raw files in the SECONDARY GCS ingest bucket to the us_xx_raw_data_secondary
        dataset in BigQuery.
        """
        instance = DirectIngestInstance.SECONDARY

        if not is_ingest_in_dataflow_enabled(state_code, instance):
            raise ValueError(
                f"Cannot start a secondary raw data reimport for a state without ingest"
                f"in Dataflow enabled: {state_code.value}"
            )

        formatted_state_code = state_code.value.lower()

        region = direct_ingest_regions.get_direct_ingest_region(
            region_code=formatted_state_code
        )
        if not self.cloud_task_manager.all_ingest_instance_queues_are_empty(
            region, instance
        ):
            raise DirectIngestInstanceError(
                "Cannot kick off raw datat reimport because not all related Cloud Task "
                "queues are empty. Please check queues on Ingest Operations Admin "
                "Panel to see which have remaining tasks."
            )

        self._verify_clean_secondary_raw_data_state(state_code)

        instance_status_manager = PostgresDirectIngestInstanceStatusManager(
            region_code=formatted_state_code,
            ingest_instance=instance,
            is_ingest_in_dataflow_enabled=is_ingest_in_dataflow_enabled(
                state_code, instance
            ),
        )
        # Validation that this is a valid status transition is handled within the
        # instance manager.
        instance_status_manager.change_status_to(
            DirectIngestStatus.RAW_DATA_REIMPORT_STARTED
        )

        self.trigger_task_scheduler(state_code, instance)

    def get_ingest_instance_resources(
        self, state_code: StateCode, ingest_instance: DirectIngestInstance
    ) -> Dict[str, Any]:
        """Returns a dictionary containing the following info for the provided instance:
        i.e. {
            dbName: database name for this instance,
            storageDirectoryPath: storage directory absolute path,
            ingestBucketPath: ingest bucket path,
        }
        """
        formatted_state_code = state_code.value.lower()

        # Get the ingest bucket path
        ingest_bucket_path = gcsfs_direct_ingest_bucket_for_state(
            region_code=formatted_state_code,
            ingest_instance=ingest_instance,
            project_id=metadata.project_id(),
        )

        # Get the storage bucket for this instance
        storage_bucket_path = gcsfs_direct_ingest_storage_directory_path_for_state(
            region_code=formatted_state_code,
            ingest_instance=ingest_instance,
            project_id=metadata.project_id(),
        )

        # Get the database name corresponding to this instance
        ingest_db_name = database_key_for_state(ingest_instance, state_code).db_name

        return {
            "storageDirectoryPath": storage_bucket_path.abs_path(),
            "ingestBucketPath": ingest_bucket_path.abs_path(),
            "dbName": ingest_db_name,
        }

    def get_ingest_raw_file_processing_status(
        self, state_code: StateCode, ingest_instance: DirectIngestInstance
    ) -> List[Dict[str, Any]]:
        """Returns a list of dictionaries containing the following info for filetags in the provided instance:
        i.e. [{
            fileTag: the file tag name,
            hasConfig: whether a raw file config exists for this file tag,
            numberFilesInBucket: number of files in the ingest bucket for this file tag,
            numberUnprocessedFiles: number of files that have not been processed for this file tag,
            numberProcessedFiles: number of files that have been processed,
            latestDiscoveryTime: most recent discovery time for this file tag,
            latestProcessedTime: most recent processed time for this file tag,
            containsDelayedFiles: if there are files that are more than 24 hours delayed from the latestProcessedTime,
        }]
        """
        formatted_state_code = state_code.value.lower()
        region = get_direct_ingest_region(formatted_state_code)

        ingest_bucket_file_tag_counts = self._get_ingest_bucket_file_tag_counts(
            state_code, ingest_instance
        )
        operations_db_file_tag_summaries = self._get_raw_file_metadata_summaries(
            state_code, ingest_instance
        )
        tags_with_configs = DirectIngestRegionRawFileConfig(
            region_code=region.region_code,
            region_module=region.region_module,
        ).raw_file_tags

        all_file_tags = {
            *ingest_bucket_file_tag_counts.keys(),
            *operations_db_file_tag_summaries.keys(),
            *tags_with_configs,
        }

        all_file_tag_metadata = []
        for file_tag in all_file_tags:
            file_tag_metadata = {
                "fileTag": file_tag,
                "hasConfig": False,
                "numberFilesInBucket": 0,
                "numberUnprocessedFiles": 0,
                "numberProcessedFiles": 0,
                "latestDiscoveryTime": None,
                "latestProcessedTime": None,
                "latestUpdateDatetime": None,
            }

            if file_tag in tags_with_configs:
                file_tag_metadata["hasConfig"] = True

            if file_tag in ingest_bucket_file_tag_counts:
                file_tag_metadata[
                    "numberFilesInBucket"
                ] = ingest_bucket_file_tag_counts[file_tag]

            if file_tag in operations_db_file_tag_summaries:
                summary = operations_db_file_tag_summaries[file_tag]
                file_tag_metadata = {
                    **file_tag_metadata,
                    "numberUnprocessedFiles": summary.num_unprocessed_files,
                    "numberProcessedFiles": summary.num_processed_files,
                    "latestDiscoveryTime": summary.latest_discovery_time.isoformat(),
                    "latestProcessedTime": summary.latest_processed_time.isoformat()
                    if summary.latest_processed_time
                    else None,
                    "latestUpdateDatetime": summary.latest_update_datetime.isoformat()
                    if summary.latest_update_datetime
                    else None,
                }
            all_file_tag_metadata.append(file_tag_metadata)

        return all_file_tag_metadata

    def _get_ingest_bucket_file_tag_counts(
        self, state_code: StateCode, ingest_instance: DirectIngestInstance
    ) -> Counter[str]:
        """
        Returns a counter of file tag names to the number of files in the ingest bucket for that file tag.
        """
        ingest_bucket_path = gcsfs_direct_ingest_bucket_for_state(
            region_code=state_code.value.lower(),
            ingest_instance=ingest_instance,
            project_id=metadata.project_id(),
        )

        files_in_bucket = [
            p
            for p in self.fs.ls_with_blob_prefix(
                bucket_name=ingest_bucket_path.bucket_name, blob_prefix=""
            )
            if isinstance(p, GcsfsFilePath)
        ]

        file_tag_counts: Counter[str] = Counter()
        for file_path in files_in_bucket:
            if GcsfsDirectoryPath.from_file_path(file_path).relative_path != "":
                file_tag_counts["IGNORED_IN_SUBDIRECTORY"] += 1
                continue
            try:
                file_tag_counts[filename_parts_from_path(file_path).file_tag] += 1
            except DirectIngestError as e:
                logging.warning(
                    "Error getting file tag for file [%s]: %s", file_path, e
                )
                file_tag_counts["UNNORMALIZED"] += 1

        return file_tag_counts

    @staticmethod
    def _get_raw_file_metadata_summaries(
        state_code: StateCode, ingest_instance: DirectIngestInstance
    ) -> Dict[str, DirectIngestRawFileMetadataSummary]:
        """Returns the raw file metadata summary for all file tags
        in a given state_code in the operations DB
        """
        raw_file_metadata_manager = PostgresDirectIngestRawFileMetadataManager(
            region_code=state_code.value,
            raw_data_instance=ingest_instance,
        )
        return {
            raw_file_metadata.file_tag: raw_file_metadata
            for raw_file_metadata in raw_file_metadata_manager.get_metadata_for_all_raw_files_in_region()
        }

    @staticmethod
    def get_ingest_view_summaries(
        state_code: StateCode, ingest_instance: DirectIngestInstance
    ) -> Dict[
        str,
        Union[
            int,
            Optional[datetime],
            List[Dict[str, Union[Optional[str], int]]],
        ],
    ]:
        """Returns the following dictionary with information from BigQuery:
        {
            ingestViewMaterializationSummaries: [
                {
                    ingestViewName: <str>
                    numPendingJobs: <int>
                    numCompletedJobs: <int>
                    completedJobsMaxDatetime: <datetime>
                    pendingJobsMinDatetime: <datetime>
                }
            ],
            ingestViewContentsSummaries: [
                {
                    ingestViewName: <str>
                    numUnprocessedRows: <int>
                    unprocessedRowsMinDatetime: <datetime>
                    numProcessedRows: <int>
                    processedRowsMaxDatetime: <datetime>
                }
            ]
        }
        """
        logging.info(
            "Getting instance [%s] ingest view materialization summaries",
            ingest_instance.value,
        )
        materialization_job_summaries = (
            DirectIngestViewMaterializationMetadataManagerImpl(
                state_code.value, ingest_instance
            ).get_instance_summaries()
        )

        ingest_view_contents = InstanceIngestViewContentsImpl(
            big_query_client=BigQueryClientImpl(),
            region_code=state_code.value,
            ingest_instance=ingest_instance,
            dataset_prefix=None,
        )
        logging.info(
            "Getting instance [%s] ingest view contents summaries",
            ingest_instance.value,
        )
        with futures.ThreadPoolExecutor(
            # Conservatively allow only half as many workers as allowed connections.
            # Lower this number if we see "urllib3.connectionpool:Connection pool is
            # full, discarding connection" errors.
            max_workers=int(BQ_CLIENT_MAX_POOL_SIZE / 2)
        ) as executor:
            summary_futures = [
                executor.submit(
                    ingest_view_contents.get_ingest_view_contents_summary,
                    ingest_view_name,
                )
                for ingest_view_name in materialization_job_summaries
            ]
            contents_summaries = [
                f.result() for f in futures.as_completed(summary_futures)
            ]

        logging.info(
            "Done getting operations DB metadata for instance [%s]",
            ingest_instance.value,
        )
        return {
            "ingestViewMaterializationSummaries": [
                summary.as_api_dict()
                for summary in materialization_job_summaries.values()
            ],
            "ingestViewContentsSummaries": [
                summary.as_api_dict()
                for summary in contents_summaries
                if summary is not None
            ],
        }

    def get_all_current_ingest_instance_statuses(
        self,
    ) -> Dict[StateCode, Dict[DirectIngestInstance, DirectIngestInstanceStatus]]:
        """Returns the current status of each ingest instance for states in the given project."""

        ingest_statuses = {}
        for state_code in get_direct_ingest_states_launched_in_env():
            instance_to_status_dict: Dict[
                DirectIngestInstance, DirectIngestInstanceStatus
            ] = {}
            for i_instance in DirectIngestInstance:  # new direct ingest instance
                status_manager = PostgresDirectIngestInstanceStatusManager(
                    region_code=state_code.value,
                    ingest_instance=i_instance,
                    is_ingest_in_dataflow_enabled=is_ingest_in_dataflow_enabled(
                        state_code, i_instance
                    ),
                )

                curr_status_info = status_manager.get_current_status_info()
                instance_to_status_dict[i_instance] = curr_status_info

            ingest_statuses[state_code] = instance_to_status_dict

        return ingest_statuses

    def get_all_ingest_instance_dataflow_enabled_status(
        self,
    ) -> Dict[StateCode, Dict[DirectIngestInstance, bool]]:
        """Returns whetherer dataflow is enabled for both primary and secondary instances for states
        in the given project"""

        ingest_statuses = {}
        for state_code in get_direct_ingest_states_launched_in_env():
            instance_to_status_dict: Dict[DirectIngestInstance, bool] = {}
            for i_instance in DirectIngestInstance:  # new direct ingest instance
                instance_to_status_dict[i_instance] = is_ingest_in_dataflow_enabled(
                    state_code, i_instance
                )

            ingest_statuses[state_code] = instance_to_status_dict

        return ingest_statuses
