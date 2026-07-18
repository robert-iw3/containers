# UAT mock backend: FastAPI app whose auto-generated OpenAPI 3.0.2 spec is
# fed to the API Firewall, so the firewall validates against the exact
# contract the app publishes. Test fixture only — not a production image.
ARG repo="docker.io" \
    base_image="library/python" \
    image_hash="25976e9d34a0fab1f278cae931f34c8303d97bf0c0d7f85b6b4dcf641d7702a4"

FROM ${repo}/${base_image}@sha256:${image_hash}

RUN addgroup -g 65535 uat && \
    adduser --shell /sbin/nologin --disabled-password -h /home/uat --uid 65535 --ingroup uat uat

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py export_spec.py healthcheck.py ./

USER uat
EXPOSE 8000
CMD [ "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000" ]
