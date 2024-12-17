FROM python:3.11-alpine3.15

RUN apk update
RUN apk add bash gcc g++ make cmake z3

WORKDIR /flat
COPY . .

RUN pip install --upgrade pip setuptools
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install .
RUN python -m flat.py -h
CMD ["bash"]