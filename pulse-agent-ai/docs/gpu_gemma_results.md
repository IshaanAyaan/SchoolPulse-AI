# GPU Gemma Smoke Test Results

Generated: 2026-06-17T19:34:03.254764+00:00

## Environment

- Hostname: `129-146-117-154`
- Python: `3.10.12 (main, Jan 26 2026, 14:55:28) [GCC 11.4.0]`
- Platform: `Linux-6.8.0-1046-nvidia-x86_64-with-glibc2.35`
- GPU: `NVIDIA A100-SXM4-40GB, 40960 MiB, 580.105.08`
- GPU memory after model load: `34955 MiB, 5487 MiB, 0 %`
- vLLM models endpoint: passed.

## Model Server

- Base URL: `http://127.0.0.1:8000/v1`
- Model: `google/gemma-4-12B-it`
- Direct chat status: passed.
- Direct chat latency: 0.74 seconds.
- Prompt tokens: 47
- Completion tokens: 30
- Total tokens: 77

Direct chat answer:

> SchoolPrint AI should automatically schedule the powering down of lights and HVAC systems in unoccupied areas of the gymnasium and locker rooms immediately following the volleyball game.

## Pulse Agent With Gemma 4

All Pulse Agent queries returned `used_llm=True`, preserved analytics action cards, and included RAG citations.

The FastAPI endpoint `POST /api/agent/query` was also checked with the backend connected to the same local Gemma 4 server. It returned `used_llm=true`, RAG citations, and six dashboard action cards.

### What should we fix first before Friday volleyball?

- Latency: 4.12 seconds.
- Used local LLM: `True`
- Action cards: 6
- Top citations: context/source-notes/google-doc-final-idea.md, context/source-notes/google-doc-final-idea.md, context/source-notes/google-doc-final-idea.md

Answer excerpt:

> Based on the current analytics, the most important action to address before Friday's volleyball event is the **After-hours energy spike in the Gym**.  **Recommended Action:** Check the room schedule, lights, HVAC setpoint, and event teardown checklist to ensure all systems are powered down correctly.  **Reasoning:** *   **Priority:** High *   **Confidence:** 98% *   **Evidence:** The system detected 33.5 kWh actual usage against an expected 14.5 kWh, indicating approximately 19.0 kWh of waste in a single hour. *   **Human Verification:** Facilities staff must confirm if the room was occupied before adjusting controls.

### Plan a sports event for 250 people and reduce energy and food waste.

- Latency: 6.93 seconds.
- Used local LLM: `True`
- Action cards: 6
- Top citations: pulse-agent-ai/docs/data_strategy.md, pulse-agent-ai/docs/data_strategy.md, README.md

Answer excerpt:

> To plan a sports event for 250 people while minimizing waste, I recommend the following strategy based on SchoolPulse analytics:  ### **Energy Reduction** *   **HVAC & Lighting:** Schedule the venue (e.g., Gym or Auditorium) to activate only during the event window. Use a "teardown checklist" to ensure all lights and climate controls are powered down immediately following the conclusion. *   **Zone Management:** Limit cooling/heating to the specific zones required for the 250 attendees rather than the entire wing.  ### **Food Waste Reduction** *   **Precision Ordering:** Based on historical data (e.g., Math Competition/Guest Speaker trends), order food based on a confirmed RSVP count rather than a maximum capacity estimate. *   **Waste Tracking:** Implement a post-event waste log to compare predicted vs. actual attendance and food waste to refine future orders.  ### **Logistics** *   **T

### Explain why this is more than a dashboard for the judges.

- Latency: 4.81 seconds.
- Used local LLM: `True`
- Action cards: 6
- Top citations: info/email-summary.md, pulse-agent-ai/docs/architecture.md, context/source-notes/google-doc-final-idea.md

Answer excerpt:

> Pulse Agent AI is more than a dashboard because it provides an **AI reasoning layer** rather than just data visualization. While the dashboard shows the results, the Pulse Agent AI actively:  *   **Retrieves and Reasons:** It analyzes live logs and retrieves specific context to understand the "why" behind the data. *   **Prioritizes:** It ranks incidents based on what matters most to school operations. *   **Explains Uncertainty:** It provides confidence scores and evidence for every alert. *   **Facilitates Human Oversight:** It converts complex data into "human-checkable action cards," ensuring a custodian or staff member verifies the AI's findings before any physical repairs or changes are made.  **Most Important Next Action:** Facilities staff must confirm the "Possible leak at B-Wing Bathroom Toilet 3" (Confidence: 87.4%) to verify the 95-minute continuous-flow pattern before escala

## Interpretation

The A100 can run the Pulse Agent backend plus `google/gemma-4-12B-it` locally. Gemma is best used as the explanation and voice-agent layer; the structured prediction models and RAG retrieval should stay separate so the system remains testable, grounded, and judge-friendly.
