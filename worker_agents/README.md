# **README Section — Public Release vs. Archived Worker Agents**

## Worker Agents (Public Release Mode)

The `worker_agents/` directory contains **sandboxed, safe versions** of the system’s distributed worker processes.  
These workers demonstrate the architecture, heartbeat protocol, and agent lifecycle without performing any real hardware access, GPU telemetry, subprocess execution, or network operations.

In public release mode:

- GPU stats are mocked  
- Ollama model lists are mocked  
- LAN IPs are mocked  
- Heartbeats print locally instead of sending over the network  
- No subprocesses are executed  
- No real system telemetry is collected  
- No external services are contacted  

These stubs allow the UI and control plane to remain fully functional while ensuring the project is safe for public viewing.

---

## Archived Worker Agents (Original Versions)

The `worker_agents_original/` directory contains the **original, full‑capability worker implementations**.  
These files are preserved **for architectural reference only** and are **not used** in the public release build.

The original workers include:

- Real GPU telemetry via `nvidia-smi`  
- Real system metrics via `psutil`  
- Real Ollama model discovery  
- Real subprocess execution  
- Real heartbeat communication with the backend  
- Real distributed agent behavior  

These versions represent the full engineering design of the system, but they are intentionally archived to prevent misuse, protect private infrastructure, and maintain a safe public footprint.

**Do not execute the files in `worker_agents_original/` in the public release environment.**

---

## Why This Separation Exists

This project is published in a **public release mode** intended for:

- portfolio demonstration  
- architectural review  
- UI exploration  
- safe sandboxed interaction  

The original worker agents are powerful components designed for private environments.  
Archiving them while providing safe stubs demonstrates:

- responsible release management  
- security awareness  
- professional software hygiene  
- thoughtful system design  
- the full depth of the underlying architecture  

This approach preserves the integrity of the project while ensuring it is safe, portable, and appropriate for public distribution.

---

If you want, I can also generate:

- a matching section for `agent_server_original/`  
- a “Public Release Mode” banner for the top of your README  
- a short explanation for recruiters describing the architecture at a high level  

Just say the word.