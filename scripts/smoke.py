"""Live HTTP test. Start API and worker first; does not mock any service."""
import io
import json
import time
import uuid
import zipfile
from pathlib import Path
import httpx
from pypdf import PdfReader

with httpx.Client(base_url="http://localhost:8000", timeout=10) as client:
    assert client.get("/ready").status_code == 200
    payload = json.loads((Path(__file__).parent.parent / "examples/batch.json").read_text())
    response = client.post("/api/v1/jobs", json=payload, headers={"Idempotency-Key": str(uuid.uuid4())})
    assert response.status_code == 201, response.text
    job_id = response.json()["id"]
    for _ in range(120):
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        if job["status"] == "completed":
            break
        time.sleep(.5)
    assert job["status"] == "completed", job
    rows = client.get(f"/api/v1/jobs/{job_id}/recipients").json()["items"]
    for row in rows:
        pdf = client.get(f"/api/v1/recipients/{row['id']}/certificate")
        assert pdf.status_code == 200
        assert row["name"] in PdfReader(io.BytesIO(pdf.content)).pages[0].extract_text()
    archive = client.get(f"/api/v1/jobs/{job_id}/download")
    assert archive.status_code == 200
    assert len(zipfile.ZipFile(io.BytesIO(archive.content)).namelist()) == 2
    print("PASS: live API -> durable job -> separate worker -> 2 readable PDFs -> ZIP", job_id)
