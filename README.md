# SchoolPrint AI

## About

This repo is the SchoolPrint AI project, the umbrella for the SchoolPulse concept built for USAII Global AI Hackathon 2026, High School Challenge 2, Direction B: My School's Hidden Footprint.

See `context/README.md` for the project brief, Google Doc synthesis, email summary, and challenge notes.

The broader system is a suite of AI tools that help a school reduce its water, energy, and food consumption. It consists of three independent edge AI tools connected by a web dashboard, which visualizes how each tool is helping reduce consumption levels for the school as a whole.

This project is open sourced under the MIT license.

## System Overview

- **Aqualert AI (water):** Aqualert AI is an acoustic edge-AI device that listens to school plumbing and detects leaks in toilets, sinks, showers, and pipes before they burst, cutting wasted water and surprise bills. A binary audio classifier runs on a Raspberry Pi Zero with a sound sensor, instantly alerting staff to leaks.  See `aqualert-ai`.

- **Compost AI (food):** Compost AI is an AI smart bin that uses computer vision to sort waste into garbage, recycling, or compost at the point of disposal, keeping contaminated loads out of landfills and routing food scraps to composting. A CNN runs on a Raspberry Pi 4 with a camera and servo motors, while a connected app logs each sorted item with its confidence level and alerts staff when a bin is full. See `Compost AI/`.

- **Pulse Agent AI / ScheduleGhost (energy + operations):** A software-heavy backend agent that reads school schedules, event history, utility-style energy logs, water alerts, and Compost AI outputs to detect after-hours energy waste, forecast event needs, retrieve project context with RAG, and turn findings into human-checkable action cards. See `pulse-agent-ai/`.

- **School Pulse (dashboard):** School Pulse is the web dashboard that unifies data from all three edge-AI tools, surfacing leak alerts with a live map of the school's pipe system, compost bin status with a sortable item database that flags low-confidence sorts, and energy metrics, so the school can see its overall footprint in one place.
