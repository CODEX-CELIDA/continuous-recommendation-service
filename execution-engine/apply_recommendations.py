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
    $ python execute.py

Note:
    - This script assumes the presence of the 'execution_engine' package and its ExecutionEngine class.
    - The pendulum library is required for date and time handling.
    - This script is configured to fetch data from a specific base URL and may need modifications
      to work with other servers or data sources.
    - The time range for execution is hardcoded and may need adjustments as per requirements.
    - The execution_engine package expects a couple of environment variables to be set (see README.md).
"""

import schedule
import time
import logging
import os
import re
import sys
import pendulum

current_dir = os.path.dirname(__file__)
sys.path.insert(0, current_dir)

from execution_engine.execution_engine import ExecutionEngine
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

recommendations = load_recommendations()

def apply_recommendations():
    # HACK(jmoringe): until restoring from database is fixed
    recommendations = load_recommendations()

    end_datetime = pendulum.now()
    logging.info(f"Applying recommendations for period {start_datetime} - {end_datetime}")
    for recommendation in recommendations:
        logging.info(f"  Applying {recommendation}")
        engine.execute(recommendation, start_datetime=start_datetime, end_datetime=end_datetime)

# Schedule for execution at regular intervals.
schedule.every(5).minutes.do(apply_recommendations)
# Force the initial run (would otherwise happen up to one full interval later).
apply_recommendations()
while schedule.next_run():
    logging.info(f"Next run at {schedule.next_run()}")
    schedule.run_pending()
    time.sleep(30)
