from fastapi import Depends, FastAPI, HTTPException, status, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from typing import List
import json
import httpx

app = FastAPI()

SECRET_KEY = "c1811f7be816f72643c88fad3f4fe0425f7dfeaee8bc52d4462ffbb0c42e4c49"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 5000

expire = datetime.utcnow() + timedelta(minutes=15)

db = {
    "childe": {
        "username": "childe",
        "full_name": "Ajax Tartaglia",
        "email": "ajax@gmail.com",
        "hashed_password": "$2b$12$EzT2prGb.tTHHpqjMM/siuHMbr4GXG/GGsLvbY3hPYNBHsJc/aOZy",
        "disabled": False
    }
}

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None

class UserInDB(User):
    hashed_password: str

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(db, username: str):
    if username in db:
        user_data = db[username]
        return UserInDB(**user_data)

def authenticate_user(db, username:str, password:str):
    user = get_user(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credential_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credential_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credential_exception
    
    user = get_user(db, username=token_data.username)
    if user is None:
        raise credential_exception
    
    return user

async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=User)
async def read_users_me(current_user: UserInDB = Depends(get_current_active_user)):
    return current_user

@app.get("/users/me/items")
async def read_own_items(current_user: UserInDB = Depends(get_current_active_user)):
    return [{"item_id": 1, "owner": current_user.username}]

# Model untuk laporan
class Report(BaseModel):
    id: int
    staf: str
    service_id: int
    description: str

# Model untuk layanan
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
with open("report.json", "r") as read_file:
    data = json.load(read_file)
    reports = data.get("reports", [])

json_filename = "services.json"
json_filename_confirmations = "confirmation.json"

with open(json_filename, "r") as read_file:
    data = json.load(read_file)
    services_data = {service["id"]: service for service in data.get("services", [])}

with open(json_filename_confirmations, "r") as read_file:
    data = json.load(read_file)
    confirmations = {confirmation["id"]: confirmation for confirmation in data.get("confirmations", [])}

@app.get("/services/", response_model=list[Service])
def read_services(current_user: UserInDB = Depends(get_current_active_user)):
    return list(services_data.values())

@app.get("/services/{service_id}", response_model=Service)
def read_service(service_id: int, current_user: UserInDB = Depends(get_current_active_user)):
    service = services_data.get(service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Layanan tidak ditemukan")
    return service

@app.post("/services/", response_model=Service)
def create_service(service: Service, current_user: UserInDB = Depends(get_current_active_user)):
    services_data[service.id] = service.dict()
    return service

@app.put("/services/{service_id}", response_model=Service)
def update_service(service_id: int, service: Service, current_user: UserInDB = Depends(get_current_active_user)):
    if service_id not in services_data:
        raise HTTPException(status_code=404, detail="Layanan tidak ditemukan")
    services_data[service_id] = service.dict()
    return service

@app.delete("/services/{service_id}", response_model=Service)
def delete_service(service_id: int, current_user: UserInDB = Depends(get_current_active_user)):
    service = services_data.pop(service_id, None)
    if service is None:
        raise HTTPException(status_code=404, detail="Layanan tidak ditemukan")
    return service

@app.post("/confirmations/", response_model=Confirmation)
def create_confirmation(confirmation: Confirmation, current_user: UserInDB = Depends(get_current_active_user)):
    confirmations[confirmation.id] = confirmation.dict()
    return confirmation

@app.get("/confirmations/", response_model=list[Confirmation])
def read_confirmations(current_user: UserInDB = Depends(get_current_active_user)):
    return list(confirmations.values())

@app.get("/questions/{course_id}/{question_id}")
async def get_question(course_id: int, question_id: int, token: str):
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://tubeststrdt.a3h4epepd8gaf9ay.southeastasia.azurecontainer.io/questions/{course_id}/{question_id}",
            headers=headers,
        )
        if response.status_code == 200:
            return response.json()
        else:
            return None

@app.get("/confirmations/{confirmation_id}", response_model=Confirmation)
def read_confirmation(confirmation_id: int, current_user: UserInDB = Depends(get_current_active_user)):
    confirmation = confirmations.get(confirmation_id)
    if confirmation is None:
        raise HTTPException(status_code=404, detail="Konfirmasi tidak ditemukan")
    return confirmation

@app.post("/reports/", response_model=Report)
def create_report(report: Report, current_user: UserInDB = Depends(get_current_active_user)):
    reports.append(report.dict())
    with open("report.json", "w") as write_file:
        json.dump({"reports": reports}, write_file)
    return report

@app.get("/reports/", response_model=List[Report])
def read_reports(current_user: UserInDB = Depends(get_current_active_user)):
    return reports

@app.get("/reports/{report_id}", response_model=Report)
def read_report(report_id: int, current_user: UserInDB = Depends(get_current_active_user)):
    for report in reports:
        if report["id"] == report_id:
            return report
    raise HTTPException(status_code=404, detail="Laporan tidak ditemukan")




# v.0.3 success login but not all authorized
# from fastapi import Depends, FastAPI, HTTPException, status, Form
# from pydantic import BaseModel
# from typing import List
# import json
# from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
# from datetime import datetime, timedelta
# from jose import JWTError, jwt
# from passlib.context import CryptContext

# app = FastAPI()

# SECRET_KEY = "c1811f7be816f72643c88fad3f4fe0425f7dfeaee8bc52d4462ffbb0c42e4c49"
# ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 5000

# expire = datetime.utcnow() + timedelta(minutes=15)

# db = {
#     "childe": {
#         "username": "childe",
#         "full_name": "Ajax Tartaglia",
#         "email": "ajax@gmail.com",
#         "hashed_password": "$2b$12$EzT2prGb.tTHHpqjMM/siuHMbr4GXG/GGsLvbY3hPYNBHsJc/aOZy",
#         "disabled": False
#     }
# }

# class Token(BaseModel):
#     access_token: str
#     token_type: str

# class TokenData(BaseModel):
#     username: str | None = None

# class User(BaseModel):
#     username: str
#     email: str | None = None
#     full_name: str | None = None
#     disabled: bool | None = None

# class UserInDB(User):
#     hashed_password: str

# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# app = FastAPI()

# def verify_password(plain_password, hashed_password):
#     return pwd_context.verify(plain_password, hashed_password)

# def get_password_hash(password):
#     return pwd_context.hash(password)

# def get_user(db, username: str):
#     if username in db:
#         user_data = db[username]
#         return UserInDB(**user_data)

# def authenticate_user(db, username:str, password:str):
#     user = get_user(db, username)
#     if not user:
#         return False
#     if not verify_password(password, user.hashed_password):
#         return False
#     return user

# def create_access_token(data: dict, expires_delta: timedelta | None = None):
#     to_encode = data.copy()
#     if expires_delta:
#         # Fixed syntax error in the line below
#         expire = datetime.utcnow() + expires_delta
#     else:
#         expire = datetime.utcnow() + timedelta(minutes=15)
#     to_encode.update({"exp": expire})
#     encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
#     return encoded_jwt

# async def get_current_user(token: str = Depends(oauth2_scheme)):
#     credential_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         username: str = payload.get("sub")
#         if username is None:
#             raise credential_exception
#         token_data = TokenData(username=username)
#     except JWTError:
#         raise credential_exception
    
#     user = get_user(db, username=token_data.username)
#     if user is None:
#         raise credential_exception
    
#     return user

# async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)):
#     if current_user.disabled:
#         raise HTTPException(status_code=400, detail="Inactive user")
#     return current_user

# @app.post("/token", response_model=Token)
# async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
#     user = authenticate_user(db, form_data.username, form_data.password)
#     if not user:
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})
#     access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
#     access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
#     return {"access_token": access_token, "token_type": "bearer"}

# @app.get("/users/me", response_model=User)
# async def read_users_me(current_user: User = Depends(get_current_active_user)):
#     return current_user

# @app.get("/users/me/items")
# async def read_own_items(current_user: User = Depends(get_current_active_user)):
#     return [{"item_id": 1, "owner": current_user.username}]

# pwd = get_password_hash("tatang123")
# print(pwd)

# # Model untuk laporan
# class Report(BaseModel):
#     id: int
#     staf: str
#     service_id: int
#     description: str

# # Model untuk layanan
# class Service(BaseModel):
#     id: int
#     name: str
#     description: str
#     price: float

# # Model untuk konfirmasi
# class Confirmation(BaseModel):
#     id: int
#     service_id: int
#     user_id: int
#     confirmed: bool

# # Membaca data dari file JSON
# with open("report.json", "r") as read_file:
#     data = json.load(read_file)
#     reports = data.get("reports", [])

# json_filename = "services.json"
# json_filename_confirmations = "confirmation.json"

# with open(json_filename, "r") as read_file:
#     data = json.load(read_file)
#     services_data = {service["id"]: service for service in data.get("services", [])}

# with open(json_filename_confirmations, "r") as read_file:
#     data = json.load(read_file)
#     confirmations = {confirmation["id"]: confirmation for confirmation in data.get("confirmations", [])}

# # Endpoint untuk membuat laporan
# @app.post("/reports/", response_model=Report)
# def create_report(report: Report):
#     reports.append(report.dict())
#     # Menulis data ke file JSON
#     with open("report.json", "w") as write_file:
#         json.dump({"reports": reports}, write_file)
#     return report

# # Endpoint untuk membaca semua laporan
# @app.get("/reports/", response_model=List[Report])
# def read_reports():
#     return reports

# # Endpoint untuk membaca laporan berdasarkan ID
# @app.get("/reports/{report_id}", response_model=Report)
# def read_report(report_id: int):
#     for report in reports:
#         if report["id"] == report_id:
#             return report
#     raise HTTPException(status_code=404, detail="Laporan tidak ditemukan")

# # Read (GET) - Membaca semua layanan
# @app.get("/services/", response_model=list[Service])
# def read_services():
#     return list(services_data.values())

# # Read (GET) - Membaca layanan berdasarkan ID
# @app.get("/services/{service_id}", response_model=Service)
# def read_service(service_id: int):
#     service = services_data.get(service_id)
#     if service is None:
#         raise HTTPException(status_code=404, detail="Layanan tidak ditemukan")
#     return service

# # Create (POST) - Membuat layanan baru
# @app.post("/services/", response_model=Service)
# def create_service(service: Service):
#     services_data[service.id] = service.dict()
#     return service

# # Update (PUT) - Memperbarui layanan
# @app.put("/services/{service_id}", response_model=Service)
# def update_service(service_id: int, service: Service):
#     if service_id not in services_data:
#         raise HTTPException(status_code=404, detail="Layanan tidak ditemukan")
#     services_data[service_id] = service.dict()
#     return service

# # Delete (DELETE) - Menghapus layanan
# @app.delete("/services/{service_id}", response_model=Service)
# def delete_service(service_id: int):
#     service = services_data.pop(service_id, None)
#     if service is None:
#         raise HTTPException(status_code=404, detail="Layanan tidak ditemukan")
#     return service

# # Endpoint untuk membuat konfirmasi
# @app.post("/confirmations/", response_model=Confirmation)
# def create_confirmation(confirmation: Confirmation):
#     confirmations[confirmation.id] = confirmation.dict()
#     return confirmation

# # Endpoint untuk membaca semua konfirmasi
# @app.get("/confirmations/", response_model=list[Confirmation])
# def read_confirmations():
#     return list(confirmations.values())

# # Endpoint untuk membaca konfirmasi berdasarkan ID
# @app.get("/confirmations/{confirmation_id}", response_model=Confirmation)
# def read_confirmation(confirmation_id: int):
#     confirmation = confirmations.get(confirmation_id)
#     if confirmation is None:
#         raise HTTPException(status_code=404, detail="Konfirmasi tidak ditemukan")
#     return confirmation

# v.0.2 gagal authorize
# from fastapi import FastAPI, HTTPException, Depends, status, Form
# from pydantic import BaseModel
# from typing import List
# import json
# from datetime import datetime, timedelta
# from jose import JWTError, jwt
# from passlib.context import CryptContext
# from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

# app = FastAPI()

# class Report(BaseModel):
#     id: int
#     staf: str
#     service_id: int
#     description: str

# class Service(BaseModel):
#     id: int
#     name: str
#     description: str
#     price: float

# class Confirmation(BaseModel):
#     id: int
#     service_id: int
#     user_id: int
#     confirmed: bool

# class Token(BaseModel):
#     access_token: str
#     token_type: str

# class TokenData(BaseModel):
#     username: str | None = None

# class User(BaseModel):
#     username: str
#     email: str | None = None
#     full_name: str | None = None
#     disabled: bool | None = None

# class UserInDB(User):
#     hashed_password: str

# # Membaca data dari file JSON
# with open("report.json", "r") as read_file:
#     data = json.load(read_file)
#     reports = data.get("reports", [])

# json_filename = "services.json"
# json_filename_confirmations = "confirmation.json"

# with open(json_filename, "r") as read_file:
#     data = json.load(read_file)
#     services_data = {service["id"]: service for service in data.get("services", [])}

# with open(json_filename_confirmations, "r") as read_file:
#     data = json.load(read_file)
#     confirmations = {confirmation["id"]: confirmation for confirmation in data.get("confirmations", [])}

# SECRET_KEY = "c1811f7be816f72643c88fad3f4fe0425f7dfeaee8bc52d4462ffbb0c42e4c49"
# ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 5000

# expire = datetime.utcnow() + timedelta(minutes=15)

# db = {
#     "childe": {
#         "username": "childe",
#         "full_name": "Ajax Tartaglia",
#         "email": "ajax@gmail.com",
#         "hashed_password": "$2b$12$EzT2prGb.tTHHpqjMM/siuHMbr4GXG/GGsLvbY3hPYNBHsJc/aOZy",
#         "disabled": False
#     }
# }

# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# # Function to create an access token
# def create_access_token(data: dict, expires_delta: timedelta | None = None):
#     to_encode = data.copy()
#     if expires_delta:
#         expire = datetime.utcnow() + expires_delta
#     else:
#         expire = datetime.utcnow() + timedelta(minutes=15)
#     to_encode.update({"exp": expire})
#     encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
#     return encoded_jwt

# # Function to verify the password
# def verify_password(plain_password, hashed_password):
#     return pwd_context.verify(plain_password, hashed_password)

# # Function to get a user from the database
# def get_user(db, username: str):
#     if username in db:
#         user_data = db[username]
#         return UserInDB(**user_data)

# # Function to authenticate a user
# def authenticate_user(db, username:str, password:str):
#     user = get_user(db, username)
#     if not user:
#         return False
#     if not verify_password(password, user.hashed_password):
#         return False
#     return user

# # Dependency to get the current user
# async def get_current_user(token: str = Depends(oauth2_scheme)):
#     credential_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         username: str = payload.get("sub")
#         if username is None:
#             raise credential_exception
#         token_data = TokenData(username=username)
#     except JWTError:
#         raise credential_exception
    
#     user = get_user(db, username=token_data.username)
#     if user is None:
#         raise credential_exception
    
#     return user

# # Dependency to get the current active user
# async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)):
#     if current_user.disabled:
#         raise HTTPException(status_code=400, detail="Inactive user")
#     return current_user

# # --- End Authentication Code ---

# # Endpoint untuk membuat laporan
# @app.post("/reports/", response_model=Report)
# def create_report(report: Report, current_user: User = Depends(get_current_active_user)):
#     reports.append(report.dict())
#     # Menulis data ke file JSON
#     with open("report.json", "w") as write_file:
#         json.dump({"reports": reports}, write_file)
#     return report

# # Endpoint untuk membaca semua laporan
# @app.get("/reports/", response_model=List[Report])
# def read_reports(current_user: User = Depends(get_current_active_user)):
#     return reports

# # Endpoint untuk membaca laporan berdasarkan ID
# @app.get("/reports/{report_id}", response_model=Report)
# def read_report(report_id: int, current_user: User = Depends(get_current_active_user)):
#     for report in reports:
#         if report["id"] == report_id:
#             return report
#     raise HTTPException(status_code=404, detail="Laporan tidak ditemukan")

# # Read (GET) - Membaca semua layanan
# @app.get("/services/", response_model=list[Service])
# def read_services(current_user: User = Depends(get_current_active_user)):
#     return list(services_data.values())

# # Read (GET) - Membaca layanan berdasarkan ID
# @app.get("/services/{service_id}", response_model=Service)
# def read_service(service_id: int, current_user: User = Depends(get_current_active_user)):
#     service = services_data.get(service_id)
#     if service is None:
#         raise HTTPException(status_code=404, detail="Layanan tidak ditemukan")
#     return service

# # Create (POST) - Membuat layanan baru
# @app.post("/services/", response_model=Service)
# def create_service(service: Service, current_user: User = Depends(get_current_active_user)):
#     services_data[service.id] = service.dict()
#     return service

# # Update (PUT) - Memperbarui layanan
# @app.put("/services/{service_id}", response_model=Service)
# def update_service(service_id: int, service: Service, current_user: User = Depends(get_current_active_user)):
#     if service_id not in services_data:
#         raise HTTPException(status_code=404, detail="Layanan tidak ditemukan")
#     services_data[service_id] = service.dict()
#     return service

# # Delete (DELETE) - Menghapus layanan
# @app.delete("/services/{service_id}", response_model=Service)
# def delete_service(service_id: int, current_user: User = Depends(get_current_active_user)):
#     service = services_data.pop(service_id, None)
#     if service is None:
#         raise HTTPException(status_code=404, detail="Layanan tidak ditemukan")
#     return service

# # Endpoint untuk membuat konfirmasi
# @app.post("/confirmations/", response_model=Confirmation)
# def create_confirmation(confirmation: Confirmation, current_user: User = Depends(get_current_active_user)):
#     confirmations[confirmation.id] = confirmation.dict()
#     return confirmation

# # Endpoint untuk membaca semua konfirmasi
# @app.get("/confirmations/", response_model=list[Confirmation])
# def read_confirmations(current_user: User = Depends(get_current_active_user)):
#     return list(confirmations.values())

# # Endpoint untuk membaca konfirmasi berdasarkan ID
# @app.get("/confirmations/{confirmation_id}", response_model=Confirmation)
# def read_confirmation(confirmation_id: int, current_user: User = Depends(get_current_active_user)):
#     confirmation = confirmations.get(confirmation_id)
#     if confirmation is None:
#         raise HTTPException(status_code=404, detail="Konfirmasi tidak ditemukan")
#     return confirmation


# v.0.1 sebelum ada login
# from fastapi import FastAPI, HTTPException
# from pydantic import BaseModel
# from typing import List
# import json

# app = FastAPI()

# # Model untuk laporan
# class Report(BaseModel):
#     id: int
#     staf: str
#     service_id: int
#     description: str

# # Model untuk layanan
# class Service(BaseModel):
#     id: int
#     name: str
#     description: str
#     price: float

# # Model untuk konfirmasi
# class Confirmation(BaseModel):
#     id: int
#     service_id: int
#     user_id: int
#     confirmed: bool

# # Membaca data dari file JSON
# with open("report.json", "r") as read_file:
#     data = json.load(read_file)
#     reports = data.get("reports", [])

# json_filename = "services.json"
# json_filename_confirmations = "confirmation.json"

# with open(json_filename, "r") as read_file:
#     data = json.load(read_file)
#     services_data = {service["id"]: service for service in data.get("services", [])}

# with open(json_filename_confirmations, "r") as read_file:
#     data = json.load(read_file)
#     confirmations = {confirmation["id"]: confirmation for confirmation in data.get("confirmations", [])}

# # Endpoint untuk membuat laporan
# @app.post("/reports/", response_model=Report)
# def create_report(report: Report):
#     reports.append(report.dict())
#     # Menulis data ke file JSON
#     with open("report.json", "w") as write_file:
#         json.dump({"reports": reports}, write_file)
#     return report

# # Endpoint untuk membaca semua laporan
# @app.get("/reports/", response_model=List[Report])
# def read_reports():
#     return reports

# # Endpoint untuk membaca laporan berdasarkan ID
# @app.get("/reports/{report_id}", response_model=Report)
# def read_report(report_id: int):
#     for report in reports:
#         if report["id"] == report_id:
#             return report
#     raise HTTPException(status_code=404, detail="Laporan tidak ditemukan")

# # Read (GET) - Membaca semua layanan
# @app.get("/services/", response_model=list[Service])
# def read_services():
#     return list(services_data.values())

# # Read (GET) - Membaca layanan berdasarkan ID
# @app.get("/services/{service_id}", response_model=Service)
# def read_service(service_id: int):
#     service = services_data.get(service_id)
#     if service is None:
#         raise HTTPException(status_code=404, detail="Layanan tidak ditemukan")
#     return service

# # Create (POST) - Membuat layanan baru
# @app.post("/services/", response_model=Service)
# def create_service(service: Service):
#     services_data[service.id] = service.dict()
#     return service

# # Update (PUT) - Memperbarui layanan
# @app.put("/services/{service_id}", response_model=Service)
# def update_service(service_id: int, service: Service):
#     if service_id not in services_data:
#         raise HTTPException(status_code=404, detail="Layanan tidak ditemukan")
#     services_data[service_id] = service.dict()
#     return service

# # Delete (DELETE) - Menghapus layanan
# @app.delete("/services/{service_id}", response_model=Service)
# def delete_service(service_id: int):
#     service = services_data.pop(service_id, None)
#     if service is None:
#         raise HTTPException(status_code=404, detail="Layanan tidak ditemukan")
#     return service

# # Endpoint untuk membuat konfirmasi
# @app.post("/confirmations/", response_model=Confirmation)
# def create_confirmation(confirmation: Confirmation):
#     confirmations[confirmation.id] = confirmation.dict()
#     return confirmation

# # Endpoint untuk membaca semua konfirmasi
# @app.get("/confirmations/", response_model=list[Confirmation])
# def read_confirmations():
#     return list(confirmations.values())

# # Endpoint untuk membaca konfirmasi berdasarkan ID
# @app.get("/confirmations/{confirmation_id}", response_model=Confirmation)
# def read_confirmation(confirmation_id: int):
#     confirmation = confirmations.get(confirmation_id)
#     if confirmation is None:
#         raise HTTPException(status_code=404, detail="Konfirmasi tidak ditemukan")
#     return confirmation