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

"""Entrypoint for the application."""
import datetime
import gc
import logging
from http import HTTPStatus
from typing import Optional, Tuple

import zope.event.classhandler
from flask import Flask, redirect, request
from flask_smorest import Api
from gevent import events
from opentelemetry.metrics import set_meter_provider
from opentelemetry.sdk.trace.sampling import Sampler, TraceIdRatioBased
from opentelemetry.trace import set_tracer_provider
from werkzeug import Response

from recidiviz.auth.auth_endpoint import auth_endpoint_blueprint
from recidiviz.monitoring.flask_insrumentation import instrument_flask_app
from recidiviz.monitoring.providers import (
    create_monitoring_meter_provider,
    create_monitoring_tracer_provider,
)
from recidiviz.monitoring.trace import CompositeSampler
from recidiviz.persistence.database.schema_type import SchemaType
from recidiviz.server_blueprint_registry import (
    default_blueprints_with_url_prefixes,
    flask_smorest_api_blueprints_with_url_prefixes,
)
from recidiviz.server_config import initialize_engines, initialize_scoped_sessions
from recidiviz.utils import environment, metadata, structured_logging
from recidiviz.utils.auth.gae import requires_gae_auth
from recidiviz.utils.environment import GCPEnvironment, in_gunicorn

structured_logging.setup()

logging.info("[%s] Running server.py", datetime.datetime.now().isoformat())

app = Flask(__name__)

# Set up instrumentation libraries prior to initializing our various clients (i.e. gRPC, SQLAlchemy, etc)
instrument_flask_app(app=app)

# TODO(#24741): Remove once admin panel migration is completed
api = Api(
    app,
    # These are needed for flask-smorests OpenAPI generation. We don't use this right now, so these
    # values can be set to ~anything
    spec_kwargs={
        "title": "default",
        "version": "1.0.0",
        "openapi_version": "3.1.0",
    },
)
service_type = environment.get_service_type()

if service_type is environment.ServiceType.DEFAULT:
    for blueprint, url_prefix in default_blueprints_with_url_prefixes:
        app.register_blueprint(blueprint, url_prefix=url_prefix)
    for blueprint, url_prefix in flask_smorest_api_blueprints_with_url_prefixes:
        api.register_blueprint(blueprint, url_prefix=url_prefix)
else:
    raise ValueError(f"Unsupported service type: {service_type}")


# OpenTelemetry's MeterProvider and `CloudMonitoringMetricsExporter` are compatible with gunicorn's
# forking mechanism and can be instantiated pre-fork.
meter_provider = create_monitoring_meter_provider()
set_meter_provider(meter_provider)


def initialize_worker_process() -> None:
    """OpenTelemetry's BatchSpanProcessor is not compatible with gunicorn's forking mechanism,
     so our providers must be instantiated per-worker in post_fork. For more information see:
    https://opentelemetry-python.readthedocs.io/en/latest/examples/fork-process-model/README.html
    """
    sampler: Optional[Sampler] = None
    if environment.in_gcp():
        sampler = CompositeSampler(
            {
                "/direct/extract_and_merge": TraceIdRatioBased(rate=100 / 100),
            },
            # For other requests, trace 1 in 20.
            default_sampler=TraceIdRatioBased(rate=1 / 20),
        )

    tracer_provider = create_monitoring_tracer_provider(sampler=sampler)
    set_tracer_provider(tracer_provider)


# Called by the configured hook in `gunicorn.conf.py` and `gunicorn.gthread.conf.py`
app.initialize_worker_process = initialize_worker_process  # type: ignore

# Call manually running via the `flask` command and not `gunicorn`
if not in_gunicorn():
    initialize_worker_process()


@auth_endpoint_blueprint.before_request
@requires_gae_auth
def authorization_middleware() -> None:
    pass


if environment.in_development():
    # We set the project to recidiviz-staging
    metadata.set_development_project_id_override(environment.GCP_PROJECT_STAGING)

    initialize_scoped_sessions(app)
    initialize_engines(schema_types=[SchemaType.OPERATIONS])
elif environment.in_gcp():
    initialize_scoped_sessions(app)
    initialize_engines(schema_types=set(SchemaType))


@app.route("/health")
def health() -> Tuple[str, HTTPStatus]:
    """This just returns 200, and is used by Docker and GCP uptime checks to verify that the flask workers are
    up and serving requests."""
    return "", HTTPStatus.OK


@app.route("/admin", defaults={"path": ""})
@app.route("/admin/<path:path>")
def fallback(path: Optional[str] = None) -> Response:
    gcp_env = environment.get_gcp_environment()

    if gcp_env == GCPEnvironment.STAGING.value:
        new_host = "admin-panel-staging.recidiviz.org"
    elif gcp_env == GCPEnvironment.PRODUCTION.value:
        new_host = "admin-panel-prod.recidiviz.org"
    else:
        raise RuntimeError("Admin Panel no longer lives in this app")

    return redirect(
        f"https://{new_host}/admin/{path}", code=HTTPStatus.MOVED_PERMANENTLY.value
    )


@zope.event.classhandler.handler(events.MemoryUsageThresholdExceeded)
def memory_condition_handler(event: events.MemoryUsageThresholdExceeded) -> None:
    logging.warning(
        "Memory usage %d is more than limit of %d, forcing gc",
        event.mem_usage,
        event.max_allowed,
    )
    gc.collect()


@zope.event.classhandler.handler(events.EventLoopBlocked)
def blocked_condition_handler(event: events.EventLoopBlocked) -> None:
    logging.warning(
        "Worker blocked for more than %d seconds [greenlet: %s]:\n%s",
        event.blocking_time,
        str(event.greenlet),
        "\n".join(event.info),
    )


@app.before_request
def log_request_entry() -> None:
    logging.getLogger(structured_logging.RECIDIVIZ_BEFORE_REQUEST_LOG).info(
        "%s %s", request.method, request.full_path
    )
