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
"""Defines routes for the Data Freshness API the admin panel."""
import datetime
from http import HTTPStatus
from typing import Tuple, Union

from flask import Blueprint, Response, jsonify

from recidiviz.admin_panel.admin_stores import get_ingest_data_freshness_store
from recidiviz.common.constants.states import StateCode


def add_data_freshness_routes(admin_panel_blueprint: Blueprint) -> None:
    """Adds the relevant Data Freshness API routes to an input Blueprint."""
    # Data freshness
    @admin_panel_blueprint.route(
        "/api/ingest_metadata/data_freshness", methods=["POST"]
    )
    def fetch_ingest_data_freshness() -> Tuple[Response, HTTPStatus]:
        return (
            jsonify(get_ingest_data_freshness_store().data_freshness_results),
            HTTPStatus.OK,
        )

    @admin_panel_blueprint.route(
        "/api/ingest_metadata/get_all_bq_refresh_timestamps/<state_code_str>"
    )
    def _get_refresh_timestamps(
        state_code_str: str,
    ) -> Tuple[Union[str, Response], HTTPStatus]:
        try:
            state_code = StateCode(state_code_str)
        except ValueError:
            return "Invalid input data", HTTPStatus.BAD_REQUEST

        timestamps = get_ingest_data_freshness_store().get_refresh_timestamps_for_schema_and_state_since(
            state_code, datetime.datetime.now() - datetime.timedelta(days=180)
        )
        return (
            jsonify([timestamp.isoformat() for timestamp in timestamps]),
            HTTPStatus.OK,
        )
