# SchoolPulse AI

SchoolPulse AI is a suite of three independent AI tools: **Aqualert AI** (Water Usage), **Compost AI** (Food Waste) and **Pulse AI Agent** (Energy Usgae and Event Forecasting) that helps schools visualize their entire environmental footprint on a unified web dashboard and delivers actionable steps for a school administration to take in order to reduce their substantial environmental footprint through an ElevenLabs voice agent. SchoolPulse AI was built for the USAII Global AI Hackathon 2026.

**Live Dashboard:** https://school-pulse-ai.vercel.app/

<br>

<table>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/c2bcfa97-5aa0-475e-b161-acdd83f60f57" alt="Footprint dashboard with action cards" width="100%"/></td>
    <td><img src="https://github.com/user-attachments/assets/5db20b72-27ad-4ff5-a78a-a05b13d13604" alt="Voice agent answering a question" width="100%"/></td>
  </tr>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/5bf15a3c-adfd-4dc6-bdcc-51a6b361d3d5" alt="Compost AI scan and sort result" width="100%"/></td>
    <td><img src="https://github.com/user-attachments/assets/a73ef0c0-6f00-4caa-a8a6-7b973ba4e604" alt="Aqualert live water leak feed" width="100%"/></td>
  </tr>
</table> 

<p align="center">
  <em>Built by Raghav Senthil Kumar, Vignesh Nagarajan, Ishaan Ranjan, Adrian Iugan and Nihal Doddagowdru.</em>
</p>


<br> 

## Tech Stack

<!--- Frontend --->
<p align="center" >
  <img src="https://img.shields.io/badge/react-%2320232a.svg?style=for-the-badge&logo=react&logoColor=%2361DAFB">
  <img src="https://img.shields.io/badge/Next.js-black.svg?style=for-the-badge&logo=next.js&logoColor=white">
  <img src="https://img.shields.io/badge/typescript-%23007ACC.svg?style=for-the-badge&logo=typescript&logoColor=white">
  <img src="https://img.shields.io/badge/tailwindcss-%2338B2AC.svg?style=for-the-badge&logo=tailwind-css&logoColor=white">
  <img src="https://img.shields.io/badge/radix%20ui-161618.svg?style=for-the-badge&logo=radix-ui&logoColor=white">
</p>

<!--- Backend --->
<p align="center" >
  <img src="https://img.shields.io/badge/FastAPI-005571.svg?style=for-the-badge&logo=fastapi">
  <img src="https://img.shields.io/badge/flask-%23000.svg?style=for-the-badge&logo=flask&logoColor=white">
  <img src="https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54">
  <img src="https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white">
  <img src="https://img.shields.io/badge/git-%23F05033.svg?style=for-the-badge&logo=git&logoColor=white">
  <img src="https://img.shields.io/badge/vercel-%23000000.svg?style=for-the-badge&logo=vercel&logoColor=white">
  <img src="https://img.shields.io/badge/sqlite-%2307405e.svg?style=for-the-badge&logo=sqlite&logoColor=white">

<!--- ML/AI --->
<p align="center" >
  <img src="https://img.shields.io/badge/Keras-D00000.svg?style=for-the-badge&logo=keras&logoColor=white">
  <img src="https://img.shields.io/badge/scikit--learn-%23F7931E.svg?style=for-the-badge&logo=scikit-learn&logoColor=white">
  <img src="https://img.shields.io/badge/opencv-%23white.svg?style=for-the-badge&logo=opencv&logoColor=white">
  <img src="https://img.shields.io/badge/google%20gemma-8E75B2?style=for-the-badge&logo=google%20gemini&logoColor=white">
  <img src="https://img.shields.io/badge/TensorFlow-%23FF6F00.svg?style=for-the-badge&logo=tensorflow&logoColor=white">
  <img src="https://img.shields.io/badge/huggingface-%23FFD21E.svg?style=for-the-badge&logo=huggingface&logoColor=white">
</p>

<!--- Hardware --->
<p align="center" >
  <img src="https://img.shields.io/badge/Arduino%20IDE-%2300979D.svg?style=for-the-badge&logo=Arduino&logoColor=white">
  <img src="https://img.shields.io/badge/c++-%2300599C.svg?style=for-the-badge&logo=c%2B%2B&logoColor=white">
  <img src="https://img.shields.io/badge/cuda-000000.svg?style=for-the-badge&logo=nVIDIA&logoColor=green">
  <img src="https://img.shields.io/badge/-Raspberry_Pi-C51A4A?style=for-the-badge&logo=Raspberry-Pi">
</p>


## System Architecture

SchoolPulse AI is built around three independent data-collection tools that each focus on one part of a school's environmental footprint. All three feed into a single backend, **Pulse Agent AI**, which synthesizes the data, identifies the biggest problems across all three domains and generates ranked list of action cards which renders on the web dashboard.

- **Aqualert AI** monitors toilet tanks using an ultrasonic sensor. It runs a linear regression model on the ultrasonic sensor's readings and if it finds a water level decline, it sends a leak alert directly to the backend.
- **Compost AI** photographs waste items at the moment of disposal and classifies them with a deep learning model into either compost or garbage. Each classification is logged onto a databse and updates on teh dashboard.
- **Pulse Agent AI** ingests the live data from Aqualert AI and Compost AI along with synthetic data of the energy logs. It then runs a Random Forest Model on all the databases to forecast energy/food allocation for future events and it generates a priority list of action items to be resolved. Further queries about the data are processed by the voice agent. 

```
     Aqualert AI                Compost AI               Energy Loss
  (Raspberry Pi 0)           (EfficientNet-B0)         (Synthetic data)
 Ultrasonic Sensor             Arduino Uno              energy_logs.csv
        │                           │                         │
        ▼  POST /api/water/live     ▼  POST /api/waste/live   ▼  loaded at startup
  ┌───────────────────────────────────────────────────────────────────────┐
  │  Pulse Agent AI  (FastAPI)                                            │
  │    Random Forest     ──► Water + Waste + Energy + Events summaries    │
  │    Event Forecasting ──► Predicted servings & resource needs          │
  │    RAG + Gemma       ──► Voice agent answers in 6 languages           │
  │    Priority Ranking  ──► Top action cards ranked by confidence        │
  └───────────────────────────────────────────────────────────────────────┘
        │
        ▼
  Next.js dashboard (action cards | live data | event forecasting | voice agent)
```

### Predictive Modelling

- **Priority action cards:** The backend runs four random forest ML models, one each for energy, water, food waste and events, scanning the logs for anomalies such as energy spikes, open leak alerts, and low-confidence food classifications. Each finding is scored by confidence and estimated impact, and the six highest-confidence issues are surfaced on the dashboard as priority action cards. Every card includes the location, the recommended action, and supporting evidence, and always requires a human to verify before anything is acted on.
- **Event forecasting.** When a school event is approaching, the system uses a linear regression model to predict how many food servings will be needed, the expected energy load, and how much waste to prepare for, based on event type, attendance, and duration. These predictions are compiled into a reviewable event plan before anything is purchased or scheduled.


## Aqualert AI (Water Usage)

Aqualert AI detects toilet leaks from the water level inside the tank. It runs a ***linear regression model*** on data collected from an HC-SR04 Ultrasonic sensor. Specifically, the ultrasonic sensor echoes 7 times every 60 seconds, which collects distance measurements of the water level in the tank. It then plots each data point on a graph and draws a line of best fit using linear regression. If the water level decline (linear regression line of best fit) is below the set threshold, the model determines the toilet is leaking and sends an alert to the dashboard, which appears as a High Action Priority Card.

### System Design 
**A. Sensing.** An HC-SR04 ultrasonic sensor powered by a Raspberry Pi 0 measures the distance to the water surface and streams the readings over a USB serial at `115200 baud` as JSON lines, which a bridge forwards to the live csv file, which is then populated onto the database. 

**B. Measurement.** Each cycle takes **7 rapid samples** and rejects outliers with a MAD-based modified z-score, then plots a line of best fit using linear regression

**C. Detection.** A leaking tank shows a slow sawtooth: the level creeps down between flushes, and the fill valve periodically tops it back up. The detector unwraps those micro-refills into the underlying decline and feeds the result to a state machine.

**D. Telemetry.** Every decision ships over MQTT with TLS, with a REST and SQLite store-and-forward fallback so nothing is lost.

A leak is flagged only when the **upper** bound of the slope CI clears the threshold, which keeps false alarms rare, and during occupied hours a decline must sustain for **3 consecutive windows** before escalating.

| State | Meaning |
| -------- | -------- |
| `NORMAL` | Level is stable, no action needed. |
| `WATCH` | A weak but real decline is forming, monitoring continues. |
| `LEAK_SUSPECTED` | The conservative threshold cleared with corroborating evidence. |
| `SENSOR_FAULT` | Too few valid echoes to report safely. |

Each alert carries a per-day wasted-water estimate as a range, derived from the slope CI:

```json
{
  "device_id": "aqualert-dev-001",
  "state": "LEAK_SUSPECTED",
  "confidence": 0.94
}
```

## Compost AI (Food)

Compost AI is a smart-bin classifier that sorts waste into either `garbage` or `compost` at the moment of disposal. Once a user throws away an item of waste, an ultrasonic sensor detects its presence and sends a signal to the processing unit to take a picture. The processing unit is a dashboard open on an iPad. The iPad rear-view camera takes a picture of the item and runs inference on a deep convolutional neural network (***EfficientNet-B0 backbone***). 

After the neural network determines which bin the item should be sorted into, a signal is sent to the servo motor to move 60 degrees left if the item is compost or 60 degrees right if the item is classified as garbage. Finally in the dashboard, the user has the option to correct the model if it was wrong. The correct label is stored alongside the image's visual embedding in a correction memory. On future predictions, if a new item is visually similar enough to a previously corrected one, the correction automatically overrides the model's output. 

**Compost AI Live Dashboard:** https://compost-ai.vercel.app/


### Waste Classification Pipeline

An **EfficientNet-B0** backbone with ImageNet transfer learning is fine-tuned on **224x224** images. The frozen backbone feeds a trainable head with a 256-unit dense layer, L2 regularization, dropout, and a softmax over **30 waste classes**. Training uses the [Recyclable and Household Waste Classification](https://www.kaggle.com/datasets/alistairking/recyclable-and-household-waste-classification) dataset on Kaggle: **15,000+ images**, **500 per class**, split across studio-style and real-world photos.

The model predicts a fine-grained class, then maps it to a disposal pathway. The headline number is the metric that actually matters for sorting:

| Metric | Score |
| -------- | -------- |
| Disposal-pathway adjusted accuracy (3-way) | **96.36%** |
| Fine-grained accuracy (30-way) | **87.60%** |
| Quantized TFLite for deployment | **~92%** |

<br> 

<img src="https://github.com/user-attachments/assets/fec5e73a-1013-429b-b031-929597327ca6" width="49%" /> 
<img src="https://github.com/user-attachments/assets/91591bbb-5235-4af4-994a-cd77354fe237" width="49%" />

<br>

Predictions below a **0.65** confidence threshold are flagged in the dashboard for a human reviewer, and a Grad-CAM overlay shows which pixels drove the decision. When a user corrects a misclassification, the image's visual embedding is stored with the correct label. Future predictions are checked against this memory using cosine similarity, and if a new item is close enough to a stored correction, the override takes precedence. This ensures the model never makes the same mistake twice. 
 

## Pulse Agent AI (Energy and Event Forecasting)

The Pulse AI Agent is the brain of our entire AI systems It combines all the databases: `water_logs.csv`, `waste_logs.csv`, `energy_logs.csv` and `event_logs.csv` into one overview. It then runs a random forest model tofind the most critical problem areas that are actively harming a schools environmental footprint and generates actionable steps that the school administration can to solve them (e.g. address leaks, food serving surplus, wasted energy in the gym, etc.). The dashboard also runs a linear regression model on teh backend to forecast food servings and energy allocations for future events based on attendance and rooms used. Finally, it uses a Voice Agent LLM to answer queries regarding the database by fetching vectorized content using **Retrieval Augmented Generation (RAG)**.

### Reasoning Pipeline

The databses load into **SQLite**, and the project context and research sources are indexed into a **TF-IDF** matrix persisted with joblib. On a question, `RagRetriever` pulls the top matching context by cosine similarity, `AnalyticsService.overview()` computes impact totals and ranks action cards, and `PulseAgent` fuses both into an answer. If `LLM_BASE_URL` points at an OpenAI-compatible **Gemma** endpoint the agent uses it, otherwise it falls back to a deterministic, fully offline response. Every answer carries a confidence and an explicit human-verification step, and the agent never orders a purchase, repair, or schedule change on its own.

The voice agent speaks and listens in **6 languages**: English, Spanish, Hindi, Chinese, Arabic, and French, using an ElevenLabs AI to give it a realstic human touch. 

The dashboard needs the following endpoints:

| Endpoint | Returns |
| -------- | -------- |
| `GET /api/overview` | Impact totals plus the top ranked action cards. |
| `GET /api/energy` `GET /api/water` `GET /api/waste` | Per-module summaries. |
| `GET /api/water/live` `GET /api/waste/live` | Live sensor feeds for the leak and sort tables. |
| `GET /api/events` `GET /api/event-plan` | Event history and a forecasted plan for an upcoming event. |
| `POST /api/agent/query` | A grounded agent answer with action cards and citations. |
| `POST /api/voice/speak` | Synthesized speech for the answer. |

### Features

1. **Unified footprint dashboard.** Water, food, and energy waste in one black-and-white interface, with red reserved strictly for critical alerts.
2. **Voice agent.** Gemma VoiceAgent using ElevenLabs API to answer queries about the databse and event planning
3. **Priority ction cards.** Every action card is generated with evidence of an issues, the random forest model's confidence levels, the potential environmental consequences and how a human staffer can verify the matter
4. **Live edge feeds.** The water and food tables poll the real sensor endpoints and surface new leaks and low-confidence sorts as they arrive. The enrgy databses is synthetic.
5. **Event forecasting.** Runs a linear regression model to estimate servings, energy and waste for an upcoming event from past event history.
6. **Offline-resilient by default.** Layered backend and frontend fallbacks keep the whole experience working with no GPU and no backend at all.


## Getting Started

### Prerequisites

- **Python 3.9+** for the Pulse Agent backend, Aqualert and the Compost notebook. https://www.python.org/downloads/
- **Node.js 18+** for the Next.js dashboard. https://nodejs.org/
- **A CUDA GPU** to run Gemma behind an OpenAI-compatible server. 

1. **Run the Pulse Agent backend.** Build the data, index, and database once, then serve the API on port 8000, which is the port the dashboard proxies to by default.

   ```bash
   cd pulse-agent-ai
   python -m venv .venv && source .venv/bin/activate   
   pip install -r requirements.txt

   python scripts/generate_synthetic_data.py
   python scripts/init_db.py
   python scripts/build_rag_index.py
   python scripts/train_models.py

   uvicorn app.main:app --reload --port 8000
   ```

2. **Run the web dashboard.** It proxies `/api/*` to the backend from step 1.

   ```bash
   cd pulse-agent-ai/web
   npm install
   npm run dev         
   ```

   To regenerate the offline fallback data after changing the synthetic logs:

   ```bash
   npm run gen:fallback
   ```

3. **Simulate Aqualert.** No hardware and no config file are required for simulation.

   ```bash
   cd aqualert-ai
   pip install -r requirements.txt
   python scripts/simulate.py --scenario leak_slow --json   
   python -m pytest                                          
   ```

4. **Run or retrain Compost AI.** Open the notebook and run all cells, or serve the inference API directly.

   ```bash
   # Notebook: Compost-AI/Compost AI (EfficientNetB0 ~96% Accuracy).ipynb
   cd Compost-AI/inference
   pip install -r requirements.txt
   uvicorn app:app --reload         
   ```

5. **Enable Gemma.** Point the agent at any OpenAI-compatible endpoint and restart the backend. Everything else stays the same.

   ```bash
   export LLM_BASE_URL="http://YOUR_GPU_IP:8000/v1"
   export LLM_MODEL="google/gemma-4-12B-it"
   export LLM_API_KEY="EMPTY"
   ```

## License
SchoolPulse AI is open source under the MIT license.
