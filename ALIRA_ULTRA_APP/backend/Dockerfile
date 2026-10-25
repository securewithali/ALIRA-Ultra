FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Firebase JSON yahan copy karo — IMAGE MEIN NAHI, volume mount se do
# docker run -v /host/path/creds.json:/secure/speen-to-earn-firebase-adminsdk.json ...

ENV GOOGLE_APPLICATION_CREDENTIALS=/secure/speen-to-earn-firebase-adminsdk.json
ENV ALIRA_ADMIN_SECRET=change-this-secret
ENV SESSION_TTL_HOURS=720

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
