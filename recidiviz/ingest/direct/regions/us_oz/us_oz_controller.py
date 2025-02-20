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
"""Direct ingest controller implementation for US_OZ."""
from typing import List

from recidiviz.common.constants.states import StateCode
from recidiviz.ingest.direct.controllers.base_direct_ingest_controller import (
    BaseDirectIngestController,
)
from recidiviz.ingest.direct.types.direct_ingest_instance import DirectIngestInstance


class UsOzController(BaseDirectIngestController):
    """Direct ingest controller implementation for US_OZ."""

    @classmethod
    def state_code(cls) -> StateCode:
        return StateCode.US_OZ

    def __init__(self, ingest_instance: DirectIngestInstance):
        super().__init__(ingest_instance)

    @classmethod
    def _get_ingest_view_rank_list(
        cls, ingest_instance: DirectIngestInstance
    ) -> List[str]:
        """Returns a list of string ingest view names in the order they should be
        processed for data we received on a particular date.
        """

        # Add ingest view names to this list as you add mappings for them.
        return [
            "internDS_initialtable",
            "internDS_table",
            "vfds_person",
            "vfds_periods",
            "nd_person_details",
            "nd_periods",
            "gloFS_person",
            "gloFS_periods",
            "eg_person",
            "eg_movements",
            "ageid_staff",
            "ageid_staff_supervisor",
            "lotr_person",
            "lotr_periods",
            "sm_person",
            "sm_periods",
        ]
