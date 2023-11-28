FROM python:3.11-alpine

RUN apk add awake

RUN ln -s $(which awake) /usr/bin/wakeonlan

RUN adduser -u 1000 -D vmupdown

WORKDIR /vmupdown

RUN pip3 install pip-tools

COPY requirements.txt .

RUN pip-sync

COPY vmupdown/ .

RUN chown -R vmupdown:vmupdown /vmupdown

USER vmupdown

ENTRYPOINT [ "gunicorn", "--bind", "0.0.0.0:8000", "vmupdown:app" ]