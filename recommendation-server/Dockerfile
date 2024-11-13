FROM debian:stable AS stage

RUN apt-get update --assume-yes       \
  && apt-get install --assume-yes git

RUN useradd -m user

USER user
WORKDIR /home/user

RUN git clone https://github.com/codex-celida/recommendation-server

FROM tiangolo/uvicorn-gunicorn-fastapi:latest

COPY --from=stage /home/user/recommendation-server/requirements.txt /
COPY --from=stage /home/user/recommendation-server/app              /app

RUN pip install -r /requirements.txt
