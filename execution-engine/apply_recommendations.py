"""
This script is designed to execute a set of medical recommendations from specified URLs
using the ExecutionEngine from the execution_engine package. It works with guidelines
related to COVID-19 and sepsis treatments from the 'netzwerk-universitaetsmedizin.de'
FHIR (Fast Healthcare Interoperability Resources) server.

The script defines a list of endpoint URLs for specific medical recommendations. It then
sets up a time range for the execution, using the pendulum library for date and time
handling. The execution is carried out for each recommendation URL within the specified
time range.

The ExecutionEngine is used to load and execute each recommendation. Logging is set up
to debug level for detailed information about the execution process.

Attributes:
    base_url (str): Base URL for the FHIR server from where recommendations are fetched.
    urls (list of str): Specific endpoints for medical recommendations to be executed.
    start_datetime (pendulum.DateTime): Start datetime for the execution range.
    end_datetime (pendulum.DateTime): End datetime for the execution range.
    e (ExecutionEngine): Instance of the ExecutionEngine used for executing recommendations.
    logger (logging.Logger): Logger for outputting the status and results of the executions.

Example:
    This script can be executed directly from the command line:
    $ python apply_recommendations.py

Note:
    - This script assumes the presence of the 'execution_engine' package and its ExecutionEngine class.
    - The pendulum library is required for date and time handling.
    - This script is configured to fetch data from a specific base URL and may need modifications
      to work with other servers or data sources.
    - The time range for execution is hardcoded and may need adjustments as per requirements.
    - The execution_engine package expects a couple of environment variables to be set (see README.md).
"""

from typing import List
from urllib.parse import quote
import schedule
import time
import logging
import os
import re
import sys
import pendulum
from sqlalchemy import text
import sqlalchemy

current_dir = os.path.dirname(__file__)
sys.path.insert(0, current_dir)

from execution_engine.settings import get_config, update_config

logging.getLogger().setLevel(logging.INFO)

# enable multiprocessing with all available cores
update_config(multiprocessing_use=True, multiprocessing_pool_size=-1)

result_schema = get_config().omop.db_result_schema

# Validate the schema name to ensure it's safe to use in the query
if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", result_schema):
    raise ValueError(f"Invalid schema name: {result_schema}")

base_url = "https://www.netzwerk-universitaetsmedizin.de/fhir/codex-celida/guideline/"
recommendation_package_version = "v1.5.2"

urls = [
    "covid19-inpatient-therapy/recommendation/no-therapeutic-anticoagulation",
    "sepsis/recommendation/ventilation-plan-ards-tidal-volume",
    "covid19-inpatient-therapy/recommendation/ventilation-plan-ards-tidal-volume",
    "covid19-inpatient-therapy/recommendation/covid19-ventilation-plan-peep",
    "covid19-inpatient-therapy/recommendation/prophylactic-anticoagulation",
    "covid19-inpatient-therapy/recommendation/therapeutic-anticoagulation",
    "covid19-inpatient-therapy/recommendation/covid19-abdominal-positioning-ards",
]

# Since we are going to redirect the result schema to a temporary one,
# first make sure the actual result schema exists and is populated
# with recommendations, etc.
def ensure_database_exists():
    config = get_config().omop
    logging.info(f"Checking whether schema {result_schema} in database {config.database} exists")
    connection_string = f"postgresql+psycopg://{quote(config.user)}:{quote(config.password)}@{config.host}:{config.port}/{config.database}"
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
                    "SELECT count(*) FROM information_schema.schemata WHERE schema_name = :schema_name;"
                ),
                {"schema_name": result_schema},
            ).fetchone()[0] > 0
        )
        # If the schema does not exist, import appropriate packages to
        # force the creation of the schema.
        if schema_exists:
            logging.info("Schema exists")
        else:
            logging.warning(f"Schema {result_schema} in database {config.database} does not exist. Creating it now")
            # Instantiate the execution engine to ensure the result
            # schema is created.
            from execution_engine.execution_engine import ExecutionEngine
            engine = ExecutionEngine()
            logging.info("Loading recommendations")
            for recommendation_url in urls:
                engine.load_recommendation(
                        base_url + recommendation_url,
                        recommendation_package_version=recommendation_package_version
                )
            # Reset interpreter state by re-executing everything. This is
            # necessary because at this point in the original process, the
            # packages of the execution-engine have already been imported with
            # the "wrong" schema and the schema cannot be changed after that
            # as far as I (jmoringe) can tell.
            logging.warning(f"Re-executing to reset database meta-data: {sys.executable} {sys.argv}")
            os.execv(sys.executable, [sys.executable] + sys.argv)
ensure_database_exists()

# When we reach this point, we know that the result schema exists and
# contains the required data. We "switch" to a temporary schema before
# we import or instantiate anything related to the database. After
# this point, the ORM and engine will work only with the temporary
# schema.
temp_schema = 'temp'
get_config().omop.db_result_schema = temp_schema

from execution_engine.clients import omopdb
from execution_engine.execution_engine import ExecutionEngine

start_datetime = pendulum.parse("2024-10-01 00:00:00+01:00")

engine = ExecutionEngine()

def load_recommendations():
    logging.info("Loading recommendations")
    return [
    engine.load_recommendation(
            base_url + recommendation_url,
            recommendation_package_version=recommendation_package_version,
            force_reload=True # HACK(jmoringe): until restoring from database is fixed
    ) for recommendation_url in urls ]

recommendations = [] # load_recommendations() TODO: use this to load only once


def apply_recommendations():
    # HACK(jmoringe): until restoring from database is fixed
    recommendations = load_recommendations()

    end_datetime = pendulum.now()
    logging.info(f"Applying recommendations for period {start_datetime} - {end_datetime}")

    # Tables which must be copied from the temporary schema to the
    # result schema after the execution engine finishes.
    tables = ['execution_run', 'result_interval']

    # Clear the temporary schema before starting the execution engine
    # run. Note: we could probalby reset counters here as well if we
    # wanted to reset the ids for execution_runs and result_intervals.
    with omopdb.begin() as con:
        con.execute(text('\n'.join(f"TRUNCATE TABLE {temp_schema}.{table} CASCADE;"
                                   for table in tables)))
    # Run the execution engine. Results go into the temporary schema.
    for recommendation in recommendations:
        engine.execute(recommendation, start_datetime=start_datetime, end_datetime=end_datetime)
    # Try to atomically transfer the results from the temporary schema
    # to the result schema by locking the tables in the result schema,
    # truncating those tables and copying the rows from the temporary
    # schema in a single transaction.
    # TODO(jmoringe): no longer | We also truncate the tables in
    # the temporary schema but that step is not essential.
    logging.info(f"Transferring data from temporary schema {temp_schema} to result schema {result_schema}")
    with omopdb.begin() as con:
        con.execute(text('\n'.join(f"LOCK TABLE {result_schema}.{table} IN ACCESS EXCLUSIVE MODE;"
                                   for table in tables)
                         + '\n'.join(f"TRUNCATE TABLE {result_schema}.{table} CASCADE;"
                                     for table in tables)
                         + '\n'.join(f"INSERT INTO {result_schema}.{table} SELECT * FROM {temp_schema}.{table};"
                                     for table in tables)
                         #+ '\n'.join(f"TRUNCATE TABLE {temp_schema}.{table} CASCADE;"
                         #            for table in tables)
                         ))
    logging.info(f"Transfer finished")

def run_with_time_based_trigger():
    # Schedule for execution at regular intervals.
    schedule.every(5).minutes.do(apply_recommendations)
    # Force the initial run (would otherwise happen up to one full interval later).
    apply_recommendations()
    while schedule.next_run():
        logging.info(f"Next run at {schedule.next_run()}")
        schedule.run_pending()
        time.sleep(30)

def run_with_http_trigger():
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class TriggerHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            logging.info(F"Got POST request")
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write("Applying recommendations\n".encode('utf-8'))
            apply_recommendations()
    server = HTTPServer(('localhost', 12345), TriggerHandler)
    server.serve_forever()
    server.server_close()

# TODO(jmoringe): make this selectable via commandline options?
# run_with_time_based_trigger()
run_with_http_trigger()
