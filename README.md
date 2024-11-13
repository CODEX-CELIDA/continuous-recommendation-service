## Introduction

This project provides a group of Docker services which periodically apply computer interpretable recommendations such as those [https://github.com/CODEX-CEDLIA/celida-recommendations](defined in the CELIDA project) to patient data in an OMOP formatted databased.  The assumed overall process consists of the following actions/actors:

1. A component outside the scope of this project acts as a source of patient data and updates the OMOP-formatted section of the databse with new records. TODO either in real-time or on a regular basis.

2. On a regular basis, the execution-engine service of this project scans the data base for records to which the defined recommendations are applicable and creates suitable output records in a different section of the database

3. A user-interface component retrieves (TODO on the fly or on a regular basis) the created records and presents the to users.

The database itself, the patient data source component and the user-interface component are outside of the scope of this project and must be set up separately.
