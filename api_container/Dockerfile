FROM python:3.10.12 
WORKDIR /code/

COPY ./api_container/ /code/accounts_api/
COPY ./lib/ /code/lib/

RUN pip install --no-cache-dir --upgrade -r /code/accounts_api/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/lib/requirements.txt

CMD ["uvicorn", "accounts_api.accounts_api:app", "--port", "9212", "--host", "0.0.0.0", "--reload"]