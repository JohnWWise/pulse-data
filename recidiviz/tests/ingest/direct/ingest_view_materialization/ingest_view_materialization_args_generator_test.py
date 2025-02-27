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
"""Tests for IngestViewMaterializationArgsGenerator."""
import datetime
import unittest
from typing import List, Optional

import attr
import pytest
import pytz
import sqlalchemy
from freezegun import freeze_time
from mock import Mock, patch

from recidiviz.common import attr_validators
from recidiviz.ingest.direct.direct_ingest_regions import DirectIngestRegion
from recidiviz.ingest.direct.ingest_view_materialization.ingest_view_materialization_args_generator import (
    IngestViewMaterializationArgsGenerator,
)
from recidiviz.ingest.direct.metadata.direct_ingest_view_materialization_metadata_manager import (
    DirectIngestViewMaterializationMetadataManagerImpl,
)
from recidiviz.ingest.direct.metadata.postgres_direct_ingest_file_metadata_manager import (
    PostgresDirectIngestRawFileMetadataManager,
)
from recidiviz.ingest.direct.types.cloud_task_args import IngestViewMaterializationArgs
from recidiviz.ingest.direct.types.direct_ingest_instance import DirectIngestInstance
from recidiviz.persistence.database.schema.operations import schema
from recidiviz.persistence.database.schema_type import SchemaType
from recidiviz.persistence.database.session_factory import SessionFactory
from recidiviz.persistence.database.sqlalchemy_database_key import SQLAlchemyDatabaseKey
from recidiviz.persistence.entity.operations.entities import (
    DirectIngestRawFileMetadata,
    DirectIngestViewMaterializationMetadata,
)
from recidiviz.tests.ingest.direct.fakes.fake_single_ingest_view_collector import (
    FakeSingleIngestViewCollector,
)
from recidiviz.tests.utils.fake_region import fake_region
from recidiviz.tools.postgres import local_persistence_helpers, local_postgres_helpers

_ID = 1
_DATE_1 = datetime.datetime(year=2019, month=7, day=20)
_DATE_1_UTC = datetime.datetime(year=2019, month=7, day=20, tzinfo=pytz.UTC)
_DATE_2 = datetime.datetime(year=2020, month=7, day=20)
_DATE_2_UTC = datetime.datetime(year=2020, month=7, day=20, tzinfo=pytz.UTC)
_DATE_3 = datetime.datetime(year=2021, month=7, day=20)
_DATE_3_UTC = datetime.datetime(year=2021, month=7, day=20, tzinfo=pytz.UTC)
_DATE_4 = datetime.datetime(year=2022, month=4, day=14)
_DATE_4_UTC = datetime.datetime(year=2022, month=4, day=14, tzinfo=pytz.UTC)
_DATE_5 = datetime.datetime(year=2022, month=4, day=15)
_DATE_5_UTC = datetime.datetime(year=2022, month=4, day=15, tzinfo=pytz.UTC)


@attr.s
class _IngestFileMetadata:
    file_tag: str = attr.ib()
    datetimes_contained_lower_bound_exclusive: datetime.datetime = attr.ib()
    datetimes_contained_upper_bound_inclusive: datetime.datetime = attr.ib()
    job_creation_time: datetime.datetime = attr.ib()
    export_time: Optional[datetime.datetime] = attr.ib()


@attr.s
class _RawFileMetadata:
    file_tag: str = attr.ib()
    update_datetime: datetime.datetime = attr.ib(
        validator=attr_validators.is_utc_timezone_aware_datetime
    )
    file_discovery_time: datetime.datetime = attr.ib(
        validator=attr_validators.is_utc_timezone_aware_datetime
    )
    file_processed_time: datetime.datetime = attr.ib(
        validator=attr_validators.is_utc_timezone_aware_datetime
    )


# TODO(#7843): Debug and write test for edge case crash while uploading many raw data
#  files while queues are unpaused.
@pytest.mark.uses_db
class TestIngestViewMaterializationArgsGenerator(unittest.TestCase):
    """Tests for IngestViewMaterializationArgsGenerator."""

    # Stores the location of the postgres DB for this test run
    temp_db_dir: Optional[str]

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_db_dir = local_postgres_helpers.start_on_disk_postgresql_database()

    def setUp(self) -> None:
        self.metadata_patcher = patch("recidiviz.utils.metadata.project_id")
        self.mock_project_id_fn = self.metadata_patcher.start()
        self.mock_project_id = "recidiviz-456"
        self.mock_project_id_fn.return_value = self.mock_project_id

        self.database_key = SQLAlchemyDatabaseKey.for_schema(SchemaType.OPERATIONS)
        local_persistence_helpers.use_on_disk_postgresql_database(self.database_key)

        self.ingest_database_name = "ingest_database_name"
        self.ingest_instance = DirectIngestInstance.PRIMARY

    def tearDown(self) -> None:
        self.metadata_patcher.stop()
        local_persistence_helpers.teardown_on_disk_postgresql_database(
            self.database_key
        )

    @classmethod
    def tearDownClass(cls) -> None:
        local_postgres_helpers.stop_and_clear_on_disk_postgresql_database(
            cls.temp_db_dir
        )

    def create_args_generator(
        self,
        region: DirectIngestRegion,
        materialize_raw_data_table_views: bool = False,
        ingest_view_name: Optional[str] = None,
    ) -> IngestViewMaterializationArgsGenerator:
        raw_file_metadata_manager = PostgresDirectIngestRawFileMetadataManager(
            region.region_code, DirectIngestInstance.PRIMARY
        )
        ingest_view_name = ingest_view_name or "ingest_view"
        return IngestViewMaterializationArgsGenerator(
            region=region,
            raw_file_metadata_manager=raw_file_metadata_manager,
            metadata_manager=DirectIngestViewMaterializationMetadataManagerImpl(
                region.region_code, self.ingest_instance
            ),
            view_collector=FakeSingleIngestViewCollector(  # type: ignore[arg-type]
                region,
                ingest_view_name=ingest_view_name or "ingest_view",
                materialize_raw_data_table_views=materialize_raw_data_table_views,
            ),
            launched_ingest_views=[ingest_view_name],
        )

    def test_getIngestViewExportTaskArgs_happy(self) -> None:
        # Arrange
        region = fake_region(environment="production")
        args_generator = self.create_args_generator(region)
        args_generator.metadata_manager.get_most_recent_registered_job = Mock(  # type: ignore
            return_value=DirectIngestViewMaterializationMetadata(
                region_code=region.region_code,
                ingest_view_name="ingest_view",
                instance=self.ingest_instance,
                materialization_time=_DATE_1,
                is_invalidated=False,
                job_creation_time=_DATE_1,
                lower_bound_datetime_exclusive=_DATE_1,
                upper_bound_datetime_inclusive=_DATE_1,
            )
        )
        args_generator.raw_file_metadata_manager.get_metadata_for_raw_files_discovered_after_datetime = Mock(  # type: ignore
            return_value=[
                DirectIngestRawFileMetadata(
                    file_id=2,
                    region_code=region.region_code,
                    file_tag="my_raw_file",
                    file_discovery_time=_DATE_2_UTC,
                    normalized_file_name="unprocessed_2015-01-02T03:03:03:000003_raw_file_tag.csv",
                    file_processed_time=None,
                    update_datetime=_DATE_2_UTC,
                    raw_data_instance=DirectIngestInstance.PRIMARY,
                )
            ]
        )

        # Act
        args = args_generator.get_ingest_view_materialization_task_args()

        # Assert
        self.assertListEqual(
            args,
            [
                IngestViewMaterializationArgs(
                    ingest_view_name="ingest_view",
                    ingest_instance=self.ingest_instance,
                    lower_bound_datetime_exclusive=_DATE_1,
                    upper_bound_datetime_inclusive=_DATE_2,
                )
            ],
        )

    def test_getIngestViewExportTaskArgs_rawFileOlderThanLastExport(self) -> None:
        # Arrange
        region = fake_region(environment="production")
        args_generator = self.create_args_generator(region)
        args_generator.metadata_manager.get_most_recent_registered_job = Mock(  # type: ignore
            return_value=DirectIngestViewMaterializationMetadata(
                region_code=region.region_code,
                ingest_view_name="ingest_view",
                instance=self.ingest_instance,
                materialization_time=_DATE_2,
                is_invalidated=False,
                job_creation_time=_DATE_2,
                lower_bound_datetime_exclusive=_DATE_2,
                upper_bound_datetime_inclusive=_DATE_2,
            )
        )
        args_generator.raw_file_metadata_manager.get_metadata_for_raw_files_discovered_after_datetime = Mock(  # type: ignore
            return_value=[
                DirectIngestRawFileMetadata(
                    file_id=2,
                    region_code=region.region_code,
                    file_tag="ingest_view",
                    file_discovery_time=_DATE_1_UTC,
                    normalized_file_name="unprocessed_2015-01-02T03:03:03:000003_raw_file_tag.csv",
                    file_processed_time=None,
                    update_datetime=_DATE_1_UTC,
                    raw_data_instance=DirectIngestInstance.PRIMARY,
                )
            ]
        )

        # Act
        with self.assertRaisesRegex(
            ValueError, r"upper bound date.*before the last valid export"
        ):
            args_generator.get_ingest_view_materialization_task_args()

    def test_getIngestViewExportTaskArgs_rawCodeTableOlderThanLastExport(self) -> None:
        # Arrange
        CODE_TABLE_TAG = "RECIDIVIZ_REFERENCE_ingest_view"
        region = fake_region(environment="production")
        args_generator = self.create_args_generator(
            region, ingest_view_name=CODE_TABLE_TAG
        )
        args_generator.metadata_manager.get_most_recent_registered_job = Mock(  # type: ignore
            return_value=DirectIngestViewMaterializationMetadata(
                region_code=region.region_code,
                ingest_view_name="ingest_view_using_code_table",
                instance=self.ingest_instance,
                materialization_time=_DATE_2,
                is_invalidated=False,
                job_creation_time=_DATE_2,
                lower_bound_datetime_exclusive=(_DATE_2 - datetime.timedelta(days=7)),
                upper_bound_datetime_inclusive=_DATE_2,
            )
        )
        args_generator.raw_file_metadata_manager.get_metadata_for_raw_files_discovered_after_datetime = Mock(  # type: ignore
            return_value=[
                DirectIngestRawFileMetadata(
                    file_id=2,
                    region_code=region.region_code,
                    file_tag=CODE_TABLE_TAG,
                    file_discovery_time=_DATE_1_UTC,
                    normalized_file_name="unprocessed_2015-01-02T03:03:03:000003_raw_file_tag.csv",
                    file_processed_time=None,
                    update_datetime=_DATE_1_UTC,
                    raw_data_instance=DirectIngestInstance.PRIMARY,
                )
            ]
        )

        # Act
        args = args_generator.get_ingest_view_materialization_task_args()

        # Assert
        # New code tables are backdated but don't need to be re-ingested, so ignore them.
        self.assertListEqual(args, [])

    def test_ingest_view_export_job_created_between_raw_file_discoveries_with_same_datetime(
        self,
    ) -> None:
        """Exhibits behavior in a scenario where a set of identically dated raw files
        are slow to upload and an ingest view task gets generated between two uploads
        for raw file dependencies of this view. All timestamps are generated from
        real-world crash.

        It is not the responsibility of the export manager to handle this scenario -
        instead, users of the export manager must take measures to ensure that we don't
        attempt to schedule ingest view export jobs while a batch raw data import is
        in progress.
        """
        ingest_view_name = "ingest_view"
        file_tag_1 = "file_tag_first"
        file_tag_2 = "tagFullHistoricalExport"

        raw_file_datetimes = [
            # <Assume there are also raw files from 2021-07-24 (the day before here)>
            # This raw file was discovered at the same time, but uploaded 10 min earlier
            _RawFileMetadata(
                file_tag=file_tag_1,
                update_datetime=datetime.datetime(
                    2021, 7, 25, 9, 2, 24, tzinfo=pytz.UTC
                ),
                file_discovery_time=datetime.datetime(
                    2021, 7, 25, 9, 29, 33, tzinfo=pytz.UTC
                ),
                file_processed_time=datetime.datetime(
                    2021, 7, 25, 9, 31, 17, tzinfo=pytz.UTC
                ),
            ),
            # This raw file took 10 extra minutes to upload and is also a dependency of
            # movement_facility_location_offstat_incarceration_periods
            _RawFileMetadata(
                file_tag=file_tag_2,
                update_datetime=datetime.datetime(
                    2021, 7, 25, 9, 2, 24, tzinfo=pytz.UTC
                ),
                file_discovery_time=datetime.datetime(
                    2021, 7, 25, 9, 29, 37, tzinfo=pytz.UTC
                ),
                file_processed_time=datetime.datetime(
                    2021, 7, 25, 9, 41, 15, tzinfo=pytz.UTC
                ),
            ),
        ]

        ingest_file_metadata = [
            # This job was created between discovery of files 1 and 2, task was likely queued immediately.
            _IngestFileMetadata(
                file_tag=ingest_view_name,
                datetimes_contained_lower_bound_exclusive=datetime.datetime.fromisoformat(
                    "2021-07-24 09:02:44"
                ),
                datetimes_contained_upper_bound_inclusive=datetime.datetime.fromisoformat(
                    "2021-07-25 09:02:24"
                ),
                job_creation_time=datetime.datetime.fromisoformat(
                    "2021-07-25 09:29:35.195456"
                ),
                # Also crashes if export time is set
                export_time=None,
            ),
        ]

        with self.assertRaisesRegex(
            sqlalchemy.exc.IntegrityError,
            r"\(psycopg2.errors.CheckViolation\) new row for relation.*",
        ):
            self.run_get_args_test(
                ingest_view_name=ingest_view_name,
                committed_raw_file_metadata=raw_file_datetimes,
                committed_ingest_materialization_metadata=ingest_file_metadata,
            )

    def run_get_args_test(
        self,
        ingest_view_name: str,
        committed_raw_file_metadata: List[_RawFileMetadata],
        committed_ingest_materialization_metadata: List[_IngestFileMetadata],
    ) -> List[IngestViewMaterializationArgs]:
        """Runs test to generate ingest view materialization args given provided DB state."""
        region = fake_region(environment="production")

        with SessionFactory.using_database(self.database_key) as session:
            for i, ingest_file_datetimes in enumerate(
                committed_ingest_materialization_metadata
            ):
                metadata = schema.DirectIngestViewMaterializationMetadata(
                    job_id=i,
                    region_code=region.region_code.upper(),
                    instance=self.ingest_instance.value,
                    ingest_view_name=ingest_view_name,
                    is_invalidated=False,
                    lower_bound_datetime_exclusive=ingest_file_datetimes.datetimes_contained_lower_bound_exclusive,
                    upper_bound_datetime_inclusive=ingest_file_datetimes.datetimes_contained_upper_bound_inclusive,
                    job_creation_time=ingest_file_datetimes.job_creation_time,
                    materialization_time=ingest_file_datetimes.export_time,
                )
                session.add(metadata)

        with SessionFactory.using_database(self.database_key) as session:
            for i, raw_file_datetimes_item in enumerate(committed_raw_file_metadata):
                raw_file_metadata = schema.DirectIngestRawFileMetadata(
                    file_id=i,
                    region_code=region.region_code.upper(),
                    file_tag=raw_file_datetimes_item.file_tag,
                    normalized_file_name=f"{raw_file_datetimes_item.file_tag}_{i}_raw",
                    update_datetime=raw_file_datetimes_item.update_datetime,
                    file_discovery_time=raw_file_datetimes_item.file_discovery_time,
                    file_processed_time=raw_file_datetimes_item.file_processed_time.replace(
                        tzinfo=pytz.UTC
                    ),
                    raw_data_instance=DirectIngestInstance.PRIMARY.value,
                    is_invalidated=False,
                )
                session.add(raw_file_metadata)

        # Act
        with freeze_time(_DATE_4.isoformat()):
            args_generator = self.create_args_generator(region)
        with freeze_time(_DATE_5.isoformat()):
            args = args_generator.get_ingest_view_materialization_task_args()

        return args
