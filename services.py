from fastapi import FastAPI, HTTPException
import json
from pydantic import BaseModel

app = FastAPI()

class Service(BaseModel):
    id: int
    name: str
    description: str
    price: float

# Model untuk konfirmasi
class Confirmation(BaseModel):
    id: int
    service_id: int
    user_id: int
    confirmed: bool

# Membaca data dari file JSON
json_filename = "services.json"
json_filename_confirmations = "confirmation.json"

with open(json_filename, "r") as read_file:
    data = json.load(read_file)
    services_data = {service["id"]: service for service in data.get("services", [])}

with open(json_filename_confirmations, "r") as read_file:
    data = json.load(read_file)
    confirmations = {confirmation["id"]: confirmation for confirmation in data.get("confirmations", [])}

# Read (GET) - Membaca semua layanan
@app.get("/services/", response_model=list[Service])
def read_services():
    return list(services_data.values())

# Read (GET) - Membaca layanan berdasarkan ID
@app.get("/services/{service_id}", response_model=Service)
def read_service(service_id: int):
    service = services_data.get(service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Layanan tidak ditemukan")
    return service

# Create (POST) - Membuat layanan baru
@app.post("/services/", response_model=Service)
def create_service(service: Service):
    services_data[service.id] = service.dict()
    return service

# Update (PUT) - Memperbarui layanan
@app.put("/services/{service_id}", response_model=Service)
def update_service(service_id: int, service: Service):
    if service_id not in services_data:
        raise HTTPException(status_code=404, detail="Layanan tidak ditemukan")
    services_data[service_id] = service.dict()
    return service

# Delete (DELETE) - Menghapus layanan
@app.delete("/services/{service_id}", response_model=Service)
def delete_service(service_id: int):
    service = services_data.pop(service_id, None)
    if service is None:
        raise HTTPException(status_code=404, detail="Layanan tidak ditemukan")
    return service

# Endpoint untuk membuat konfirmasi
@app.post("/confirmations/", response_model=Confirmation)
def create_confirmation(confirmation: Confirmation):
    confirmations[confirmation.id] = confirmation.dict()
    return confirmation

# Endpoint untuk membaca semua konfirmasi
@app.get("/confirmations/", response_model=list[Confirmation])
def read_confirmations():
    return list(confirmations.values())

# Endpoint untuk membaca konfirmasi berdasarkan ID
@app.get("/confirmations/{confirmation_id}", response_model=Confirmation)
def read_confirmation(confirmation_id: int):
    confirmation = confirmations.get(confirmation_id)
    if confirmation is None:
        raise HTTPException(status_code=404, detail="Konfirmasi tidak ditemukan")
    return confirmation
