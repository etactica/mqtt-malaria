FROM ubuntu:14.04

WORKDIR /app

RUN apt-get update &&\
    apt-get install -y git python2.7-dev python-virtualenv fuse

ADD . /app

RUN virtualenv .env && \
    . .env/bin/activate

RUN pip install .

ENTRYPOINT [ "/app/malaria" ]
