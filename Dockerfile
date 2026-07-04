FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt server.py search.py index.html logo.png render.yaml ./
RUN pip install --no-cache-dir -r requirements.txt
ENV PORT=10000
ENV HOST=0.0.0.0
EXPOSE 10000
CMD ["python", "server.py"]
