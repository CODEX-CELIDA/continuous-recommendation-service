#ARG POSTGRES_USER
#ARG POSTGRES_PASSWORD
#ARG POSTGRES_HOST
#ARG POSTGRES_PORT
#ARG POSTGRES_DB

#ARG FHIR_BASE_URL

FROM debian:stable AS stage

RUN apt-get update --assume-yes       \
  && apt-get install --assume-yes git

RUN useradd -m user

USER user
WORKDIR /home/user

COPY --chown=user execution-engine execution-engine
# RUN git clone https://github.com/codex-celida/execution-engine
  
FROM debian:stable

ARG POSTGRES_HOST #=${POSTGRES_HOST} # 172.17.0.1 # TODO 
ARG POSTGRES_PORT #=${POSTGRES_PORT} # 5434
ARG POSTGRES_USER #=${POSTGRES_USER} # postgres
ARG POSTGRES_PASSWORD #=${POSTGRES_PASSWORD} # yourpassword
ARG POSTGRES_DB #=${POSTGRES_DB} # ohdsi

ARG FHIR_BASE_URL

# TODO(jmoringe): staging container for python3-dev and gcc?
RUN apt-get update --assume-yes                                \
  && apt-get install --assume-yes python3-full python3-dev gcc \
  && apt-get clean

RUN useradd -m user

COPY --from=stage --chown=user /home/user/execution-engine/requirements.txt /home/user/apply-recommendations/
COPY --from=stage --chown=user /home/user/execution-engine/setup.py         /home/user/apply-recommendations/
COPY --from=stage --chown=user /home/user/execution-engine/execution_engine /home/user/apply-recommendations/execution_engine
COPY              --chown=user apply_recommendations.py                     /home/user/apply-recommendations/

USER user

RUN python3 -m venv ${HOME}/apply-recommendations/venv
RUN ${HOME}/apply-recommendations/venv/bin/pip install -r ${HOME}/apply-recommendations/requirements.txt
RUN ${HOME}/apply-recommendations/venv/bin/pip install schedule
RUN cd ${HOME}/apply-recommendations && ${HOME}/apply-recommendations/venv/bin/python setup.py build_ext --inplace

ENV CELIDA_EE_FHIR_BASE_URL=${FHIR_BASE_URL}
ENV CELIDA_EE_FHIR_TERMINOLOGY_SERVER_URL=http://tx.fhir.org/r4
ENV CELIDA_EE_TIMEZONE=Europe/Berlin
ENV CELIDA_EE_OMOP__USER=${POSTGRES_USER}
ENV CELIDA_EE_OMOP__PASSWORD=${POSTGRES_PASSWORD}
ENV CELIDA_EE_OMOP__HOST=${POSTGRES_HOST}
ENV CELIDA_EE_OMOP__PORT=${POSTGRES_PORT}
ENV CELIDA_EE_OMOP__DATABASE=${POSTGRES_DB}
ENV CELIDA_EE_OMOP__DATA_SCHEMA=cds_cdm
ENV CELIDA_EE_OMOP__RESULT_SCHEMA=celida
ENV CELIDA_EE_EPISODE_OF_CARE_VISIT_DETAIL=0
ENV CELIDA_EE_MULTIPROCESSING_USE=0
ENV CELIDA_EE_MULTIPROCESSING_POOL_SIZE=-1

CMD "${HOME}/apply-recommendations/venv/bin/python" "${HOME}/apply-recommendations/apply_recommendations.py"