"""
HydroMind - Smart Irrigation Veto Engine (Feature 1)
MSME Hackathon Project

FastAPI backend service that processes soil moisture readings from ESP32 sensors
and applies forecast-aware veto logic to prevent unnecessary irrigation.

NOTE ON ARCHITECTURE:
This module implements a Deterministic Rule-Based Expert System / Dynamic Hardware Override
for ultra-fast, predictable, and fail-safe field operation on edge devices (ESP32).
Machine Learning models (e.g., Random Forest classifier/regressor) are implemented in
separate secondary predictive analytics modules, not in this decision veto engine.
"""

import os
import logging
from typing import Dict, Any
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field

# Load environment variables from .env file if available
load_dotenv()

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("hydromind")

app = FastAPI(
    title="HydroMind API - Smart Irrigation Veto Engine",
    description="Deterministic Rule-Based Expert System with Live Weather API & Dynamic Hardware Override.",
    version="1.2.0"
)


class IrrigationRequest(BaseModel):
    soil_moisture_percent: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Soil moisture level percentage measured by hardware sensor (0.0 to 100.0%)",
        example=22.5
    )
    lat: float = Field(
        default=28.6790,
        ge=-90.0,
        le=90.0,
        description="Latitude for live weather forecast (-90 to 90, default: AKGEC Ghaziabad)",
        example=28.6790
    )
    lon: float = Field(
        default=77.5062,
        ge=-180.0,
        le=180.0,
        description="Longitude for live weather forecast (-180 to 180, default: AKGEC Ghaziabad)",
        example=77.5062
    )


class IrrigationResponse(BaseModel):
    motor_status: str = Field(..., description="Target status for irrigation pump motor: 'ON' or 'OFF'")
    veto_applied: bool = Field(..., description="True if software veto overrode normal watering recommendation")
    reason: str = Field(..., description="Detailed explanation of the decision logic")
    confidence_score: float = Field(..., description="Calculated veto confidence score based on weather forecast")
    next_check_mins: int = Field(..., description="Recommended duration (in minutes) before next sensor check")


def get_weather_data(lat: float = 28.6790, lon: float = 77.5062) -> Dict[str, Any]:
    """
    Fetches real-time weather forecast parameters from OpenWeatherMap 5-day / 3-hour Forecast API.
    Extracts native 'pop' (Probability of Precipitation) directly from the upcoming forecast block.
    
    Includes a Hackathon Fail-Safe try-except block with Python logging to fall back to safe mock data
    if the API key is unconfigured, rate-limited, or network connectivity is unavailable.
    """
    api_key = os.getenv("OWM_API_KEY", "YOUR_OWM_API_KEY_HERE")
    url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}&units=metric"

    try:
        if not api_key or api_key in ["YOUR_OWM_API_KEY_HERE", "your_key_here"]:
            raise ValueError("OpenWeatherMap API key is unconfigured (using default placeholder).")

        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        # Extract upcoming 3-hour forecast block
        first_block = data["list"][0]

        # OWM 5-day forecast API natively returns 'pop' (Probability of Precipitation: 0.0 to 1.0)
        pop = float(first_block.get("pop", 0.0))
        temp_c = float(first_block["main"]["temp"])
        humidity = int(first_block["main"]["humidity"])
        cloud_cover = int(first_block["clouds"]["all"])

        return {
            "pop": pop,
            "temp_c": temp_c,
            "humidity": humidity,
            "cloud_cover": cloud_cover,
            "source": "live_openweathermap_api"
        }

    except Exception as e:
        logger.warning("OpenWeatherMap API call failed (%s). Utilizing hackathon fail-safe fallback weather data.", str(e))
        # Fail-Safe Mock Fallback Data (ensures hardware never crashes during live pitch/demo)
        return {
            "pop": 0.85,        # 85% rain probability fallback
            "temp_c": 42.0,     # Temperature in Celsius (hot day)
            "humidity": 70,     # Relative humidity %
            "cloud_cover": 90,  # Cloud cover %
            "source": "fail_safe_fallback_mock"
        }


def calculate_irrigation_decision(
    soil_moisture: float,
    lat: float = 28.6790,
    lon: float = 77.5062
) -> IrrigationResponse:
    """
    Evaluates a Deterministic Rule-Based Expert System / Dynamic Hardware Override logic
    to derive motor status, veto decision, dynamic check intervals, and confidence scores based on
    soil moisture and live/fallback weather data.
    
    (Note: Machine Learning models like Random Forest are utilized in separate predictive analytics modules.)
    """
    # Fetch weather forecast parameters for target location
    weather = get_weather_data(lat=lat, lon=lon)
    pop = weather.get("pop", 0.10)
    temp_c = weather.get("temp_c", 30.0)
    cloud_cover = weather.get("cloud_cover", 20)

    # Rule 2: Veto Confidence Score Formula
    # (PoP * 100 * 0.7) + (Cloud Cover * 0.3)
    veto_score = round((pop * 100.0 * 0.7) + (cloud_cover * 0.3), 2)

    # -------------------------------------------------------------------------
    # RULE 1: Hardware Override (Critical Red-Line)
    # If moisture <= 15.0%, hardware safety overrides software predictions.
    # -------------------------------------------------------------------------
    if soil_moisture <= 15.0:
        return IrrigationResponse(
            motor_status="ON",
            veto_applied=False,
            reason=f"CRITICAL SAFETY OVERRIDE: Soil moisture is {soil_moisture:.1f}% (<= 15.0% critical threshold). Hardware safety activated.",
            confidence_score=0.0,
            next_check_mins=10
        )

    # RULE 4: Dynamic Self-Correction (Wait Time)
    # If temp_c >= 35.0 -> check in 20 mins (hot day), else check in 120 mins.
    next_check = 20 if temp_c >= 35.0 else 120

    # -------------------------------------------------------------------------
    # RULE 2 & 3: Veto Score & Decision for Moderate Moisture (15% - 35%)
    # -------------------------------------------------------------------------
    if 15.0 < soil_moisture <= 35.0:
        if veto_score >= 75.0:
            return IrrigationResponse(
                motor_status="OFF",
                veto_applied=True,
                reason=f"VETO APPLIED: Rain expected soon (Veto Score: {veto_score:.2f} >= 75.0, PoP: {int(pop*100)}%, Clouds: {cloud_cover}%). Motor kept OFF to conserve water.",
                confidence_score=veto_score,
                next_check_mins=next_check
            )
        else:
            return IrrigationResponse(
                motor_status="ON",
                veto_applied=False,
                reason=f"IRRIGATION APPROVED: Low rain probability (Veto Score: {veto_score:.2f} < 75.0). Motor turned ON.",
                confidence_score=veto_score,
                next_check_mins=next_check
            )

    # -------------------------------------------------------------------------
    # OPTIMAL MOISTURE (> 35.0%)
    # Soil is already sufficiently moist. No watering required.
    # -------------------------------------------------------------------------
    return IrrigationResponse(
        motor_status="OFF",
        veto_applied=False,
        reason=f"NO IRRIGATION NEEDED: Soil moisture is optimal at {soil_moisture:.1f}% (> 35.0%). Motor kept OFF.",
        confidence_score=veto_score,
        next_check_mins=next_check
    )


@app.get("/")
def read_root():
    return {
        "service": "HydroMind Smart Irrigation Veto Engine",
        "type": "Deterministic Rule-Based Expert System / Hardware Override",
        "status": "Online",
        "docs_url": "/docs"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/api/v1/irrigation/test-weather")
def test_weather(
    lat: float = Query(default=28.6790, ge=-90.0, le=90.0, description="Latitude (-90 to 90)"),
    lon: float = Query(default=77.5062, ge=-180.0, le=180.0, description="Longitude (-180 to 180)")
):
    """
    GET testing endpoint to directly verify OpenWeatherMap API connectivity and raw forecast values.
    Returns the fetched weather dictionary (including 'source' field: live_openweathermap_api vs fail_safe_fallback_mock).
    """
    return get_weather_data(lat=lat, lon=lon)


@app.post("/decide", response_model=IrrigationResponse)
@app.post("/api/v1/irrigation/decide", response_model=IrrigationResponse)
def decide_irrigation(payload: IrrigationRequest):
    """
    POST endpoint for ESP32 hardware sensor to request an irrigation decision.
    Accepts JSON: {"soil_moisture_percent": float, "lat": float (optional), "lon": float (optional)}
    """
    try:
        return calculate_irrigation_decision(
            soil_moisture=payload.soil_moisture_percent,
            lat=payload.lat,
            lon=payload.lon
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while calculating irrigation decision: {str(e)}"
        )
