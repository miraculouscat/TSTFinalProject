from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import json

app = FastAPI()

# Model untuk laporan
class Report(BaseModel):
    id: int
    staf: str
    service_id: int
    description: str

# Membaca data dari file JSON
with open("report.json", "r") as read_file:
    data = json.load(read_file)
    reports = data.get("reports", [])

# Endpoint untuk membuat laporan
@app.post("/reports/", response_model=Report)
def create_report(report: Report):
    reports.append(report.dict())
    # Menulis data ke file JSON
    with open("report.json", "w") as write_file:
        json.dump({"reports": reports}, write_file)
    return report

# Endpoint untuk membaca semua laporan
@app.get("/reports/", response_model=List[Report])
def read_reports():
    return reports

# Endpoint untuk membaca laporan berdasarkan ID
@app.get("/reports/{report_id}", response_model=Report)
def read_report(report_id: int):
    for report in reports:
        if report["id"] == report_id:
            return report
    raise HTTPException(status_code=404, detail="Laporan tidak ditemukan")
