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
"""Contains logic for US_XX specific entity matching overrides.

TODO(#20930): Delete this file once we have shipped ingest in Dataflow and deleted the
legacy implementation of entity matching.
"""
from recidiviz.common.constants.states import StateCode
from recidiviz.common.ingest_metadata import IngestMetadata
from recidiviz.persistence.entity_matching.legacy.state.state_specific_entity_matching_delegate import (
    StateSpecificEntityMatchingDelegate,
)


class UsXxMatchingDelegate(StateSpecificEntityMatchingDelegate):
    """Class that contains matching logic specific to US_XX."""

    def __init__(self, ingest_metadata: IngestMetadata):
        super().__init__(StateCode.US_XX.value.lower(), ingest_metadata)
