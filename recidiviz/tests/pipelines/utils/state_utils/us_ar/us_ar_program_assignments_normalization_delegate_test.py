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
"""Tests us_ar_program_assignments_normalization_delegate.py."""
import unittest

from recidiviz.common.constants.states import StateCode
from recidiviz.pipelines.utils.state_utils.us_ar.us_ar_program_assignment_normalization_delegate import (
    UsArProgramAssignmentNormalizationDelegate,
)

_STATE_CODE = StateCode.US_AR.value


class TestUsArProgramAssignmentNormalizationDelegate(unittest.TestCase):
    """Tests functions in UsArProgramAssignmentNormalizationDelegate."""

    def setUp(self) -> None:
        self.delegate = UsArProgramAssignmentNormalizationDelegate()

    # ~~ Add new tests here ~~
