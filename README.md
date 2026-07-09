# AI Memory Layer — Public Release Mode
A distributed AI memory system with worker agents, distilled prompts, heartbeat tracking,
and a web-based control plane. This is a safe, sandboxed demonstration of the architecture.

# DISCLAIMER
This project is a prototype and demonstration of architectural concepts.
It is not a production system and should not be used as one.

# ETHICAL USE NOTICE
This project is intended for educational and professional demonstration purposes only.
It must not be used for surveillance, harassment, automated decision-making about individuals,
or any harmful or unethical applications.

# AI MEMORY LAYER FOR A CONTROL PLANE
Not just an LLM memory engine — but a memory system that:

> integrates with worker agents

> injects distilled memory prompts

> tracks heartbeats

> exposes a web UI that is part of a mini AI datacenter architecture

Written in python, then extended out to JavaScript with Flask for a Web Managment Interface. 

I was extremely hesitant to release some of my prototype files for this project, however I do see the advantages in this setup for my home lab. 

> This repository exists to demonstrate my ability to design and implement AI memory systems, structured fact storage, and terminal-aware interfaces. It is intentionally limited in scope to avoid misuse.


![Homepage](img/homescreen.png)
![Agent Chat](img/code-assistant.png)
![Memory Management](img/memory-debug.png)

### Both pip and python are required to be installed first

#### Enter you GitHub Repo Folder
cd ~/AI-Memory-Layer

#### [Create venv]
python3 -m venv venv

#### [Activate venv]
source venv/bin/activate

#### [install requirements]
pip install -r requirements.txt

#### [run server]
python3 -m backend.server

### Once the server is running it will display your IP address, web management interface is by default using port 8000. 

#### EXAMPLE - So to access Web Chat interface, the following URL would be "IPADDRESS:PORT" or "IPADDRESS:PORT/code-assistant.html" or "IPADDRESS:PORT/memory-debug.html" would be used. Ensure it matches up with client that is running the agent python script as well as running ollama and has models downloaded, or Web Chat will remain unpopulated. 

### Then connect a worker agent, ensure both agent_server and worker script are running on the machine with ollama installed. Also ensure an AI model is pulled with ollama, if everything is connected properly all downloaded AI models for ollama will appear in Code Assistant Model list. 

### Acknowledgments
<p> This project was created by Brendan Davis.
Development was supported through iterative collaboration with Microsoft Copilot (Leah), used as an AI assistant for architectural guidance, code scaffolding, and documentation refinement. </p>

<p> License updated from GNU GPL to Apache 2.0 on July 9, 2026.
This change reflects the project's purpose as a portfolio demonstration rather than a production system. </p> 