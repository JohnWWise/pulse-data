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
"""Direct ingest controller implementation for US_ME."""
from typing import List

from recidiviz.common.constants.states import StateCode
from recidiviz.ingest.direct.controllers.base_direct_ingest_controller import (
    BaseDirectIngestController,
)
from recidiviz.ingest.direct.types.direct_ingest_instance import DirectIngestInstance


class UsMeController(BaseDirectIngestController):
    """Direct ingest controller implementation for US_ME."""

    @classmethod
    def state_code(cls) -> StateCode:
        return StateCode.US_ME

    def __init__(self, ingest_instance: DirectIngestInstance):
        super().__init__(ingest_instance)

    @classmethod
    def _get_ingest_view_rank_list(
        cls, ingest_instance: DirectIngestInstance
    ) -> List[str]:
        """Returns a list of string ingest view names in the order they should be
        processed for data we received on a particular date.
        """
        return [
            "CLIENT",
            "CURRENT_STATUS_incarceration_periods_v2",
            "supervision_periods",
            "assessments",
            "supervision_violations",
            "incarceration_sentences",
            "supervision_sentences",
            "supervision_staff",
            "supervision_staff_role_period",
        ]
