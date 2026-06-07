import os
import re
import json
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from mangum import Mangum

app = FastAPI(title="Phone Carrier Lookup API", version="1.0.0")
# === BT Builds Standard Middleware (auto-injected) ===
from fastapi.middleware.cors import CORSMiddleware as _BTCors
app.add_middleware(_BTCors, allow_origins=["*"], allow_methods=["*"],
    allow_headers=["*"], expose_headers=["X-RateLimit-Limit","X-RateLimit-Remaining","X-RateLimit-Reset"])

@app.middleware("http")
async def _bt_add_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Powered-By"] = "btbuilds"
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


# Load carrier database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "carriers.json")) as f:
    CARRIER_DB = json.load(f)

API_KEY = os.environ.get("API_KEY", "demo-key-change-in-production")


class PhoneLookup(BaseModel):
    phone_number: str


def verify_api_key(x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


def normalize_phone(phone: str) -> str:
    """Extract just the digits from a phone number."""
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def get_area_code(phone: str) -> str:
    """Extract area code from normalized phone number."""
    digits = normalize_phone(phone)
    if len(digits) != 10:
        return None
    return digits[:3]


@app.get("/health")
async def health():
    return {"status": "healthy", "carriers_loaded": len(CARRIER_DB)}


@app.post("/lookup")
async def lookup_carrier(data: PhoneLookup, api_key: str = Depends(verify_api_key)):
    area_code = get_area_code(data.phone_number)

    if not area_code:
        raise HTTPException(status_code=400, detail="Invalid phone number format")

    carrier = CARRIER_DB.get(area_code, "Unknown")

    return {
        "phone_number": data.phone_number,
        "normalized": normalize_phone(data.phone_number),
        "area_code": area_code,
        "carrier": carrier,
        "is_mobile": carrier in ["AT&T", "Verizon", "T-Mobile"],
        "type": "mobile" if carrier in ["AT&T", "Verizon", "T-Mobile"] else "landline"
    }


@app.post("/validate")
async def validate_phone(data: PhoneLookup, api_key: str = Depends(verify_api_key)):
    digits = normalize_phone(data.phone_number)

    if len(digits) != 10:
        raise HTTPException(status_code=400, detail="Phone number must have 10 digits")

    area_code = digits[:3]
    carrier = CARRIER_DB.get(area_code, "Unknown")

    return {
        "phone_number": data.phone_number,
        "is_valid_us": True,
        "carrier": carrier,
        "is_mobile": carrier in ["AT&T", "Verizon", "T-Mobile"],
        "area_code": area_code
    }


@app.get("/area/{area_code}")
async def lookup_by_area(area_code: str, api_key: str = Depends(verify_api_key)):
    if not area_code.isdigit() or len(area_code) != 3:
        raise HTTPException(status_code=400, detail="Area code must be 3 digits")

    carrier = CARRIER_DB.get(area_code, "Unknown")
    return {
        "area_code": area_code,
        "carrier": carrier,
        "is_mobile": carrier in ["AT&T", "Verizon", "T-Mobile"]
    }


handler = Mangum(app)