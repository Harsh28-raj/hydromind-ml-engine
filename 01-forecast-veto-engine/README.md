# Feature 1: Forecast-Aware Irrigation Veto Engine

**HydroMind** — AI-Powered Smart Irrigation System for MSMEs & Farmers

This module implements a **Deterministic Rule-Based Expert System / Dynamic Hardware Override** designed to evaluate soil moisture readings from ESP32 edge sensors alongside live weather forecasts from OpenWeatherMap (5-day / 3-hour forecast API) to decide whether to activate or veto irrigation.

---

## Key Features

- **Critical Safety Override**: Automatically turns motor **ON** if soil moisture $\le 15.0\%$ (hardware red-line safety overrides software predictions).
- **Forecast Veto Engine**: Calculates a Veto Confidence Score for moisture between $15\%$ and $35\%$:
  $$\text{Veto Score} = (\text{PoP} \times 100 \times 0.7) + (\text{Cloud Cover} \times 0.3)$$
  If Veto Score $\ge 75.0$, motor is kept **OFF** to conserve water before expected rainfall.
- **Dynamic Check Intervals**: Adjusts sensor polling rate dynamically based on temperature ($\ge 35^\circ\text{C} \rightarrow 20\text{ mins}$, else $120\text{ mins}$).
- **Hackathon Fail-Safe**: Falls back to safe mock weather data if API key is missing or network connectivity drops during live demos.

---

## Environment Setup

Create a `.env` file inside this directory or set the environment variable:

```bash
# .env file
OWM_API_KEY=your_openweathermap_api_key_here
```

Refer to `.env.example` for a template.

---

## Installation & Running Locally

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the Uvicorn development server:
   ```bash
   uvicorn main:app --reload --host 127.0.0.1 --port 8000
   ```

3. Interactive API documentation available at `http://127.0.0.1:8000/docs`.

---

## Available API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Service root status & documentation link |
| `GET` | `/health` | Service health check |
| `GET` | `/api/v1/irrigation/test-weather` | Verifies live OpenWeatherMap API connectivity and raw forecast values |
| `POST` | `/decide` / `/api/v1/irrigation/decide` | Main decision endpoint for ESP32 sensors (`{"soil_moisture_percent": float, "lat": float, "lon": float}`) |
