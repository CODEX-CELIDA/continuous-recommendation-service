## Introduction

This project provides a group of Docker services which periodically apply computer interpretable recommendations such as those [defined in the CELIDA project](https://github.com/CODEX-CEDLIA/celida-recommendations) to patient data in an OMOP formatted databased.  The assumed overall process consists of the following actions/actors:

1. A component outside the scope of this project acts as a source of patient data and updates the OMOP-formatted section of the databse with new records. TODO either in real-time or on a regular basis.

2. In response to some trigger, the execution-engine service of this project scans the database for records to which the defined recommendations are applicable and creates suitable output records in a different section of the database. The trigger can be either:

   1. The database scan of the execution-engine is started on a regular basis, such as every five minutes.

   2. The data source component mentioned above or some other component notifies the execution-engine via an HTTP request of new records in the database.

3. A user-interface component retrieves (TODO on the fly or on a regular basis) the created records and presents them to users.

The database itself, the patient data source component and the user-interface component are outside of the scope of this project and must be set up separately.

## Usage

1. Copy `celida.env.sample` to `celida.env` and adjust the configuration. Details can be found in the [README of the execution-engine](https://github.com/CODEX-CELIDA/execution-engine/blob/main/README.md).

2. Copy `apply_recommendations.env.sample` to `apply_recommendations.env` and adjust the configuration.

3. Start the services with `docker-compose up`

4. Trigger recommendation processing with the equivalent of `curl -d '' http://localhost:55555` (or similar, depending on the configuration)

5. Retrieve recommentation results from the `result_interval` and `execution_run` tables of the configured result schema of the database (typically `celida`)
