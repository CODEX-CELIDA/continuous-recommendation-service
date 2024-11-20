FROM debian:stable AS stage

RUN apt-get update --assume-yes       \
  && apt-get install --assume-yes git

RUN useradd -m user

USER user
WORKDIR /home/user

COPY --chown=user execution-engine execution-engine
# RUN git clone https://github.com/codex-celida/execution-engine

RUN git clone https://github.com/DigiPOD/ee-addons.git

FROM debian:stable

ARG FHIR_BASE_URL

ARG POSTGRES_HOST
ARG POSTGRES_PORT
ARG POSTGRES_USER
ARG POSTGRES_PASSWORD
ARG POSTGRES_DB

ARG TRIGGER_HTTP_PORT

# TODO(jmoringe): staging container for python3-dev and gcc?
RUN apt-get update --assume-yes                                \
  && apt-get install --assume-yes python3-full python3-dev gcc \
  && apt-get clean

RUN useradd -m user

COPY --from=stage --chown=user /home/user/ee-addons/__init__.py             /home/user/apply-recommendations/digipod/
COPY --from=stage --chown=user /home/user/ee-addons/concepts.py             /home/user/apply-recommendations/digipod/
COPY --from=stage --chown=user /home/user/ee-addons/criterion               /home/user/apply-recommendations/digipod/criterion
COPY --from=stage --chown=user /home/user/ee-addons/recommendation          /home/user/apply-recommendations/digipod/recommendation
COPY --from=stage --chown=user /home/user/ee-addons/terminology             /home/user/apply-recommendations/digipod/terminology

COPY --from=stage --chown=user /home/user/execution-engine/requirements.txt /home/user/apply-recommendations/
COPY --from=stage --chown=user /home/user/execution-engine/setup.py         /home/user/apply-recommendations/
COPY --from=stage --chown=user /home/user/execution-engine/execution_engine /home/user/apply-recommendations/execution_engine
COPY              --chown=user apply_recommendations.py                     /home/user/apply-recommendations/
COPY              --chown=user config.py                                    /home/user/apply-recommendations/

USER user

RUN python3 -m venv ${HOME}/venv
RUN echo "pydantic-extra-types==2.10.0" >> ${HOME}/apply-recommendations/requirements.txt
RUN ${HOME}/venv/bin/pip install -r ${HOME}/apply-recommendations/requirements.txt
RUN ${HOME}/venv/bin/pip install schedule
RUN cd ${HOME}/apply-recommendations && ${HOME}/venv/bin/python setup.py build_ext --inplace

ENV CELIDA_EE_FHIR_BASE_URL=${FHIR_BASE_URL}
ENV CELIDA_EE_FHIR_TERMINOLOGY_SERVER_URL=http://tx.fhir.org/r4

ENV CELIDA_EE_TIMEZONE=Europe/Berlin
ENV CELIDA_EE_EPISODE_OF_CARE_VISIT_DETAIL=0

ENV CELIDA_EE_OMOP__USER=${POSTGRES_USER}
ENV CELIDA_EE_OMOP__PASSWORD=${POSTGRES_PASSWORD}
ENV CELIDA_EE_OMOP__HOST=${POSTGRES_HOST}
ENV CELIDA_EE_OMOP__PORT=${POSTGRES_PORT}
ENV CELIDA_EE_OMOP__DATABASE=${POSTGRES_DB}
ENV CELIDA_EE_OMOP__DATA_SCHEMA=cds_cdm
ENV CELIDA_EE_OMOP__RESULT_SCHEMA=celida

ENV CELIDA_EE_MULTIPROCESSING_USE=0
ENV CELIDA_EE_MULTIPROCESSING_POOL_SIZE=-1

ENV APPLY_RECOMMENDATIONS_TRIGGER_HTTP_ADDRESS=0.0.0.0
ENV APPLY_RECOMMENDATIONS_TRIGGER_HTTP_PORT=${TRIGGER_HTTP_PORT}

CMD "${HOME}/venv/bin/python" "${HOME}/apply-recommendations/apply_recommendations.py"
