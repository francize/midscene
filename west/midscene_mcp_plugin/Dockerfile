FROM 10.107.103.57/common/python:3.12-slim

WORKDIR /app
RUN pip config set global.index-url https://mirrors.tencentyun.com/pypi/simple
ADD . /app
RUN pip install -r requirements.txt

# CMD ["python", "-m", "main"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]