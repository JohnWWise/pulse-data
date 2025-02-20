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
"""Tests for big_query_utils.py"""
import unittest

import pandas as pd

from recidiviz.big_query.big_query_utils import normalize_column_name_for_bq


class BigQueryUtilsTest(unittest.TestCase):
    """TestCase for BigQuery utils"""

    def setUp(self) -> None:
        self.head_whitespace = "  FIELD_NAME_532"
        self.tail_whitespace = "FIELD_NAME_532  "
        self.non_printable_characters = "FIELD_\x16NAME_532"
        self.name_with_spaces = "FIELD NAME 532"
        self.name_with_chars = "FIELD?NAME*532"
        self.valid_column_name = "FIELD_NAME_532"
        self.column_names = [
            self.head_whitespace,
            self.tail_whitespace,
            self.non_printable_characters,
            self.name_with_spaces,
            self.name_with_chars,
            self.valid_column_name,
        ]

        self.df = pd.DataFrame(
            {
                "string_col": [None, "val a", "Y"],
                "int_col": [2, 3, 10],
                "time_col": ["4:56:00", "12:34:56", None],
                "date_col": pd.Series(
                    ["2022-01-01 01:23:45", None, "2022-03-04"],
                    dtype="datetime64[ns]",
                ),
                "bool_col": [None, "Y", "N"],
            }
        )

    def test_normalize_column_name_for_bq(self) -> None:
        for column_name in self.column_names:
            normalized = normalize_column_name_for_bq(column_name)
            self.assertEqual(normalized, self.valid_column_name)

        # Handles reserved words correctly
        self.assertEqual(
            "_ASSERT_ROWS_MODIFIED",
            normalize_column_name_for_bq("ASSERT_ROWS_MODIFIED"),
        )
        self.assertEqual(
            "_TableSAmple",
            normalize_column_name_for_bq("TableSAmple"),
        )

        # Handles digits correctly
        self.assertEqual("_123_COLUMN", normalize_column_name_for_bq("123_COLUMN"))
