# Tailor as a website. Build and run with:
#   docker build -t tailor .
#   docker run -p 8080:8080 -e GEMINI_API_KEY=your-key tailor
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV HOST=0.0.0.0 PORT=8080 TRUST_PROXY=1 TAILOR_NO_BROWSER=1
EXPOSE 8080
RUN useradd --create-home tailor
USER tailor
CMD ["python", "app.py"]
