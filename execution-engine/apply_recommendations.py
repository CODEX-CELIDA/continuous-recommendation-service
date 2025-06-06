"""
This script is designed to continuously execute a set of medical
recommendations from specified URLs using the ExecutionEngine from the
execution_engine package. It works with guidelines related to COVID-19
and sepsis treatments from the 'netzwerk-universitaetsmedizin.de' FHIR
(Fast Healthcare Interoperability Resources) server.

The script defines a list of endpoint URLs for specific medical
recommendations. It then sets up a time range for the execution, using
the pendulum library for date and time handling. The execution is
carried out for each recommendation URL within the specified time
range.

The ExecutionEngine is used to load and execute each
recommendation. Logging is set up to info level so that only
high-level steps of the execution process are reported.

Attributes:
    base_url (str): Base URL for the FHIR server from where
      recommendations are fetched.
    urls (list of str): Specific endpoints for medical recommendations
      to be executed.
    start_datetime (pendulum.DateTime): Start datetime for the
      execution range.
    engine (ExecutionEngine): Instance of the ExecutionEngine used
      for executing recommendations.
    logger (logging.Logger): Logger for outputting the status and
      results of the executions.

Example:
    This script can be executed directly from the command line:
    $ python apply_recommendations.py

Note:
    - This script assumes the presence of the 'execution_engine'
      package and its ExecutionEngine class.
    - The pendulum library is required for date and time handling.
    - This script is configured to fetch data from a specific base URL
      and may need modifications to work with other servers or data
      sources.
    - The start point of the processed time range for applying
      recommendations is hardcoded and may need adjustments as per
      requirements.
    - The execution_engine package expects a couple of environment
      variables to be set (see README.md).
"""

import logging
import os
import re
import sys
import time
from typing import Any, List
from urllib.parse import quote

import pendulum
import schedule
import sqlalchemy
from config import Settings, TriggerMethod
from sqlalchemy import text

current_dir = os.path.dirname(__file__)
sys.path.insert(0, current_dir)

from execution_engine.settings import get_config, update_config  # noqa

logging.getLogger().setLevel(logging.INFO)

settings = Settings()  # Settings for this script

# enable multiprocessing with all available cores
# update_config(multiprocessing_use=True, multiprocessing_pool_size=-1)

result_schema = get_config().omop.db_result_schema

# Validate the schema name to ensure it's safe to use in the query
if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", result_schema):
    raise ValueError(f"Invalid schema name: {result_schema}")


# Since we are going to redirect the result schema to a temporary one,
# first make sure the actual result schema exists and is populated
# with recommendations, etc.
def ensure_database_exists():
    """
    Ensure that the result schema exists and is populated.
    """
    config = get_config().omop
    logging.info(
        f"Checking whether schema {result_schema} in database {config.database} exists"
    )
    connection_string = (
        "postgresql+psycopg://"
        f"{quote(config.user)}:{quote(config.password)}@"
        f"{config.host}:{config.port}"
        f"/{config.database}"
    )
    engine = sqlalchemy.create_engine(
        connection_string,
        connect_args={"options": "-csearch_path={}".format(config.db_data_schema)},
        future=True,
    )
    schema_exists = None
    with engine.begin() as connection:
        # Check whether the configured result schema exists in the
        # specified database.
        schema_exists = (
            connection.execute(
                text(
                    "SELECT count(*) FROM information_schema.schemata"
                    " WHERE schema_name = :schema_name;"
                ),
                {"schema_name": result_schema},
            ).fetchone()[0]
            > 0
        )
        # If the schema does not exist, import appropriate packages to
        # force the creation of the schema.
        if schema_exists:
            logging.info("Schema exists")
        else:
            logging.warning(
                f"Schema {result_schema} in database {config.database}"
                " does not exist. Creating it now"
            )
            # Instantiate the execution engine to ensure the result
            # schema is created.
            from init import init_execution_engine, load_recommendations

            engine = init_execution_engine()
            load_recommendations(engine)
            # Reset interpreter state by re-executing everything. This is
            # necessary because at this point in the original process, the
            # packages of the execution-engine have already been imported with
            # the "wrong" schema and the schema cannot be changed after that
            # as far as I (jmoringe) can tell.
            logging.warning(
                "Re-executing to reset database meta-data: "
                + f"{sys.executable} {sys.argv}"
            )
            os.execv(sys.executable, [sys.executable] + sys.argv)  # nosec


ensure_database_exists()

# When we reach this point, we know that the result schema exists and
# contains the required data. We "switch" to a temporary schema before
# we import or instantiate anything related to the database. After
# this point, the ORM and engine will work only with the temporary
# schema.
temp_schema = "temp"
get_config().omop.db_result_schema = temp_schema

from execution_engine.clients import omopdb  # noqa
from init import init_execution_engine, load_recommendations

engine = init_execution_engine()


recommendations: List[Any] = load_recommendations(engine)


def apply_recommendations():
    """
    Apply the configured configurations to the interval from
    start_time to the current time and write the results into the
    configured result schema of the database. To ensure that other
    database clients only see consistent data, use a temporary schema
    for intermediate results and atomically transfer everything to the
    actual result schema at the end of the process.
    """
    process_start_time = time.time()

    start_datetime = settings.start_time
    end_datetime = pendulum.now()

    logging.info(
        f"Applying recommendations for period {start_datetime} - {end_datetime}"
    )

    # Tables which must be copied from the temporary schema to the
    # result schema after the execution engine finishes.
    tables = ["execution_run", "result_interval"]

    # Clear the temporary schema before starting the execution engine
    # run. Note: we could probalby reset counters here as well if we
    # wanted to reset the ids for execution_runs and result_intervals.
    with omopdb.begin() as connection:
        for table in tables:
            connection.execute(
                text(f"TRUNCATE TABLE {temp_schema}.{table} CASCADE;")
            )  # nosec
        # Now reset the sequence
        connection.execute(
            text(
                f"ALTER SEQUENCE {temp_schema}.result_interval_result_id_seq RESTART WITH 1;"
            )
        )  # nosec
        # TODO(jmoringe): is the following really not possible?
        # connection.execute(
        #    text("TRUNCATE TABLE :table CASCADE;"),
        #    {"table": f"{temp_schema}.{table}"})
    # Run the execution engine. Results go into the temporary schema.
    for recommendation in recommendations:
        engine.execute(
            recommendation, start_datetime=start_datetime, end_datetime=end_datetime
        )
    # Try to atomically transfer the results from the temporary schema
    # to the result schema by locking the tables in the result schema,
    # truncating those tables and copying the rows from the temporary
    # schema in a single transaction.
    logging.info(
        f"Transferring data from temporary schema {temp_schema}"
        + f" to result schema {result_schema}"
    )
    with omopdb.begin() as connection:
        for table in tables:
            connection.execute(
                text(f"LOCK TABLE {result_schema}.{table} IN ACCESS EXCLUSIVE MODE;")
            )  # nosec
            # TODO(jmoringe): is the following really not possible?
            # connection.execute(
            #    text("LOCK TABLE :table IN ACCESS EXCLUSIVE MODE;"),
            #    {"table": f"{result_schema}.{table}"})
        for table in tables:
            connection.execute(
                text(f"TRUNCATE TABLE {result_schema}.{table} CASCADE;")
            )  # nosec
            # connection.execute(
            #    text("TRUNCATE TABLE :table CASCADE;"),
            #    {"table": f"{result_schema}.{table}"})
        for table in tables:
            connection.execute(
                text(
                    f"INSERT INTO {result_schema}.{table}"  # nosec
                    f" SELECT * FROM {temp_schema}.{table};"  # nosec
                )
            )
            # connection.execute(
            #    text("INSERT INTO :result_table SELECT * FROM :temp_table;"),
            #        {
            #            "result_table": f"{result_schema}.{table}",
            #            "temp_table": f"{temp_schema}.{table}",
            #        })
    logging.info("Transfer finished")

    process_end_time = time.time()
    runtime_seconds = process_end_time - process_start_time

    logging.info(f"Total runtime: {runtime_seconds:.2f} seconds")


def run_with_time_based_trigger(interval: pendulum.Duration):
    """
    Periodically run apply_recommendations.
    """
    # Schedule for execution at regular intervals.
    schedule.every(interval.in_seconds).seconds.do(apply_recommendations)
    # Force the initial run (would otherwise happen up to one full
    # interval later).
    apply_recommendations()
    while schedule.next_run():
        logging.info(f"Next run at {schedule.next_run()}")
        schedule.run_pending()
        time.sleep(30)


def run_with_http_trigger(address: str, port: int):
    """
    Run apply_recommendations whenever an external trigger in the
    form of an HTTP POST request occurs.
    """
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class TriggerHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            logging.info("Got POST request")
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write("Applying recommendations\n".encode("utf-8"))
            apply_recommendations()

    server = HTTPServer((address, port), TriggerHandler)
    logging.info(f"Waiting for POST requests on {address}:{port}")
    server.serve_forever()
    server.server_close()


if settings.trigger_method == TriggerMethod.timer:
    run_with_time_based_trigger(settings.trigger_run_interval)
elif settings.trigger_method == TriggerMethod.http_request:
    run_with_http_trigger(
        settings.trigger_http_address.ip.compressed, settings.trigger_http_port
    )
else:
    assert False  # unreachable
