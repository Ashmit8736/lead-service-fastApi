# Smart Lead Scoring API (Python AI Service)

## Overview
This is the AI microservice for the **Smart Lead Scoring System**, built using **FastAPI (Python)**. Its sole responsibility is to receive lead data from the primary Java service, analyze the natural language intent and context using **Google Gemini AI**, and return an intelligent score.

## Architecture
This service acts as an independent, stateless ML node:
1. Receives a REST HTTP POST request containing an array of lead objects from the Java backend.
2. Interacts with the **Google Gemini API** to generate a contextual score (0-100), category (HOT/WARM/COLD), and a logical reason.
3. Returns the batch response to the Java service for database persistence and client delivery.

## Tech Stack
- **Framework:** FastAPI (Python 3.10+)
- **AI Provider:** Google Gemini (Generative AI)
- **Server:** Uvicorn
- **Environment Management:** python-dotenv

## Setup Instructions

### 1. Prerequisites
- Python 3.10 or higher
- pip (Python package installer)

### 2. Environment Configuration
Create a `.env` file in the root of the project with your Gemini API Key:
```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
```
*Note: The `.env` file is ignored in version control for security.*

### 3. Installation
Install the required dependencies using the `requirements.txt` file:
```bash
pip install -r requirements.txt
```

### 4. Running the Application
Start the FastAPI server locally using Uvicorn:
```bash
uvicorn main:app --reload --port 8000
```
The server will start on `http://localhost:8000`.

## API Documentation

### Batch Scoring Endpoint
**POST** `/api/ai/score/batch`

**Request:** (Array of Leads)
```json
[
  {
    "id": "1",
    "message": "Looking for enterprise software immediately.",
    "budget": 50000.0
  }
]
```

**Response:** (Array of Scored Leads)
```json
[
  {
    "id": "1",
    "score": 95,
    "category": "HOT",
    "reason": "High intent and urgency indicated by 'immediately' and large budget."
  }
]
```

## AI Approach & Future Improvements
- **Approach:** The integration uses **Google Gemini Pro** via the official Python SDK. We engineered a specific system prompt that forces the AI to return structured JSON responses containing a score between 0-100 and a categorized intent. If the Gemini API key is missing or the external service fails, the system automatically falls back to a deterministic Mock Scoring function so the overarching application does not crash.
- **Why this approach:** Gemini is extremely capable of understanding nuance in natural language. By keeping the AI logic isolated in this Python microservice, the heavy JVM (Java) is freed from holding AI models or SDKs, allowing both services to scale independently.
- **Future Improvements:** Given more time, we would implement **Batch Processing Optimization** at the AI level (sending multiple leads to Gemini in a single prompt to save latency and tokens). We would also add a caching layer (Redis) to immediately return scores for completely identical messages without hitting the Gemini API again.
