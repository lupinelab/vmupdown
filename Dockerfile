FROM python:3.11-alpine

RUN apk add awake

RUN ln -s $(which awake) /usr/bin/wakeonlan

RUN adduser -u 1000 -D vmupdown

USER vmupdown

WORKDIR /vmupdown

COPY requirements.txt .

RUN pip3 install -r requirements.txt

COPY vmupdown/ .

ENTRYPOINT [ "gunicorn", "vmupdown:app" ]