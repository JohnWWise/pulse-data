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
"""Manages acquiring and releasing the lock for the ingest process that writes
data to Postgres for a given region.
"""

from contextlib import contextmanager
from typing import Iterator, List

from recidiviz.cloud_storage.gcs_pseudo_lock_manager import GCSPseudoLockManager
from recidiviz.common.constants.states import StateCode
from recidiviz.ingest.direct.types.direct_ingest_instance import DirectIngestInstance
from recidiviz.persistence.database.bq_refresh.bq_refresh_utils import (
    postgres_to_bq_lock_name_for_schema,
)
from recidiviz.persistence.database.schema_type import SchemaType

INGEST_PROCESS_RUNNING_LOCK_PREFIX = "INGEST_PROCESS_RUNNING_"
# Ingest process running that writes to Postgres STATE tables and should block other
# processes that read from Postgres STATE tables.
# TODO(#20930): Delete this lock once ingest in Dataflow is shipped.
STATE_EXTRACT_AND_MERGE_INGEST_PROCESS_RUNNING_LOCK_PREFIX = (
    f"{INGEST_PROCESS_RUNNING_LOCK_PREFIX}STATE_"
)
RAW_FILE_IMPORT_INGEST_PROCESS_RUNNING_LOCK_PREFIX = (
    f"{INGEST_PROCESS_RUNNING_LOCK_PREFIX}RAW_FILE_"
)


class DirectIngestRegionLockManager:
    """Manages acquiring and releasing the lock for the ingest process that writes
    data to Postgres for a given region's ingest instance.
    """

    def __init__(
        self,
        region_code: str,
        ingest_instance: DirectIngestInstance,
        blocking_locks: List[str],
    ) -> None:
        """
        Args:
            region_code: The region code for the region to lock / unlock ingest for.
            blocking_locks: Any locks that, if present, mean ingest into Postgres
                cannot proceed for this region.
        """
        self.region_code = region_code
        self.ingest_instance = ingest_instance
        self.blocking_locks = blocking_locks
        self.lock_manager = GCSPseudoLockManager()

    def is_locked(self) -> bool:
        """Returns True if the ingest lock is held for the region associated with this
        lock manager.
        """
        return self.lock_manager.is_locked(self._ingest_lock_name_for_instance())

    def can_proceed(self) -> bool:
        """Returns True if ingest can proceed for the region associated with this
        lock manager.
        """
        for lock in self.blocking_locks:
            if self.lock_manager.is_locked(lock):
                return False
        return True

    def acquire_lock(self) -> None:
        self.lock_manager.lock(self._ingest_lock_name_for_instance())

    def release_lock(self) -> None:
        self.lock_manager.unlock(self._ingest_lock_name_for_instance())

    @contextmanager
    def using_region_lock(
        self,
        *,
        expiration_in_seconds: int,
    ) -> Iterator[None]:
        """A context manager for acquiring the lock for a given region. Usage:
        with lock_manager.using_region_lock(expiration_in_seconds=60):
           ... do work requiring the lock
        """
        with self.lock_manager.using_lock(
            self._ingest_lock_name_for_instance(),
            expiration_in_seconds=expiration_in_seconds,
        ):
            yield

    @contextmanager
    def using_raw_file_lock(
        self, *, raw_file_tag: str, expiration_in_seconds: int
    ) -> Iterator[None]:
        """A context manager for acquiring the lock for a given raw file. Usage:
        With lock_manager.using_raw_file_lock(raw_file_tag="my_tag", expiration_in_seconds=60):
            ... do work requiring the lock
        """
        with self.lock_manager.using_lock(
            self._ingest_lock_name_for_raw_file(raw_file_tag),
            expiration_in_seconds=expiration_in_seconds,
        ):
            yield

    @staticmethod
    def for_state_ingest(
        state_code: StateCode, ingest_instance: DirectIngestInstance
    ) -> "DirectIngestRegionLockManager":
        return DirectIngestRegionLockManager.for_direct_ingest(
            region_code=state_code.value,
            ingest_instance=ingest_instance,
        )

    @staticmethod
    def for_direct_ingest(
        region_code: str,
        ingest_instance: DirectIngestInstance,
    ) -> "DirectIngestRegionLockManager":
        return DirectIngestRegionLockManager(
            region_code=region_code,
            ingest_instance=ingest_instance,
            blocking_locks=[
                postgres_to_bq_lock_name_for_schema(SchemaType.STATE, ingest_instance),
                postgres_to_bq_lock_name_for_schema(
                    SchemaType.OPERATIONS, ingest_instance
                ),
            ],
        )

    def _ingest_lock_name_for_instance(self) -> str:
        return (
            STATE_EXTRACT_AND_MERGE_INGEST_PROCESS_RUNNING_LOCK_PREFIX
            + self.region_code.upper()
            + f"_{self.ingest_instance.name}"
        )

    def _ingest_lock_name_for_raw_file(self, raw_file_tag: str) -> str:
        return (
            RAW_FILE_IMPORT_INGEST_PROCESS_RUNNING_LOCK_PREFIX
            + self.region_code.upper()
            + f"_{self.ingest_instance.name}"
            + f"_{raw_file_tag}"
        )
