# Recidiviz - a data platform for criminal justice reform
# Copyright (C) 2019 Recidiviz, Inc.
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
"""Defines types used for direct ingest."""
import abc
import datetime
from typing import Any, Dict, Optional, Type

import attr
import cattr

from recidiviz.cloud_storage.gcsfs_path import GcsfsFilePath
from recidiviz.common import serialization
from recidiviz.common.date import snake_case_datetime
from recidiviz.ingest.direct.gcs.filename_parts import filename_parts_from_path
from recidiviz.ingest.direct.types.direct_ingest_instance import DirectIngestInstance
from recidiviz.ingest.direct.types.direct_ingest_instance_factory import (
    DirectIngestInstanceFactory,
)
from recidiviz.utils.types import ClsT


@attr.s(frozen=True)
class CloudTaskArgs:
    @abc.abstractmethod
    def task_id_tag(self) -> Optional[str]:
        """Tag to add to the name of an associated cloud task."""

    def to_serializable(self) -> Dict[str, Any]:
        converter = serialization.with_datetime_hooks(cattr.Converter())
        return converter.unstructure(self)

    @classmethod
    def from_serializable(cls: Type[ClsT], serializable: Dict[str, Any]) -> ClsT:
        converter = serialization.with_datetime_hooks(cattr.Converter())
        return converter.structure(serializable, cls)


# TODO(#20930): Delete this class when ingest in Dataflow is fully shipped.
@attr.s(frozen=True)
class ExtractAndMergeArgs(CloudTaskArgs):
    # The time this extract and merge task was scheduled.
    ingest_time: datetime.datetime = attr.ib()

    ingest_view_name: str = attr.ib()
    ingest_instance: DirectIngestInstance = attr.ib()

    upper_bound_datetime_inclusive: datetime.datetime = attr.ib()
    batch_number: int = attr.ib()

    def task_id_tag(self) -> str:
        return (
            f"extract_and_merge_{self.ingest_view_name}_"
            f"{self.upper_bound_datetime_inclusive.date().isoformat()}_"
            f"batch_{self.batch_number}"
        )

    def job_tag(self) -> str:
        return f"{self.ingest_instance.value}_{self.task_id_tag()}: {self.ingest_time}"


@attr.s(frozen=True)
class GcsfsRawDataBQImportArgs(CloudTaskArgs):
    raw_data_file_path: GcsfsFilePath = attr.ib()

    def task_id_tag(self) -> str:
        parts = filename_parts_from_path(self.raw_data_file_path)
        return f"raw_data_import_{parts.stripped_file_name}_{parts.date_str}"

    def file_id(self) -> str:
        parts = filename_parts_from_path(self.raw_data_file_path)
        return f"{parts.file_tag}_{parts.utc_upload_datetime_str}"

    def ingest_instance(self) -> DirectIngestInstance:
        return DirectIngestInstanceFactory.for_ingest_bucket(
            self.raw_data_file_path.bucket_path
        )


# TODO(#20930): Delete this class when ingest in Dataflow is fully shipped.
@attr.s(frozen=True)
class IngestViewMaterializationArgs(CloudTaskArgs):
    """Arguments for an ingest view materialization job."""

    # The file tag of the ingest view to export. Used to determine which query to run
    # to generate the exported file.
    ingest_view_name: str = attr.ib()

    # The lower bound date for updates this query should include. Any rows that have not
    # changed since this date will not be included.
    lower_bound_datetime_exclusive: Optional[datetime.datetime] = attr.ib()

    # The upper bound date for updates this query should include. Updates will only
    # reflect data received up until this date.
    upper_bound_datetime_inclusive: datetime.datetime = attr.ib()

    # The instance the ingest view is being generated in.
    ingest_instance: DirectIngestInstance = attr.ib()

    def lower_bound_datetime_exclusive_for_query(self) -> datetime.datetime:
        """Temporary workaround to manage recovery from https://go/pull/21230.
        This function returns a lower bound datetime with milliseconds stripped
        which should be used as the temporary lower bound for ingest view diff
        queries to make sure we don't create a gap in ingested data.
        TODO(#21230): Remove this and use the actual datetime with milliseconds once
         every ingest view has run at least once with fresh data for every state.
        """
        if not self.lower_bound_datetime_exclusive:
            raise ValueError(
                "The lower_bound_datetime_exclusive is None. Should only be called for "
                "args with a nonnull lower_bound_datetime_exclusive."
            )
        dt = self.lower_bound_datetime_exclusive
        return datetime.datetime(
            dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second
        )

    def task_id_tag(self) -> str:
        tag = (
            f"ingest_view_materialization_{self.ingest_view_name}-"
            f"{self.ingest_instance.value}"
        )
        if self.lower_bound_datetime_exclusive:
            tag += f"-{snake_case_datetime(self.lower_bound_datetime_exclusive)}"
        else:
            tag += "-None"
        tag += f"-{snake_case_datetime(self.upper_bound_datetime_inclusive)}"
        return tag
