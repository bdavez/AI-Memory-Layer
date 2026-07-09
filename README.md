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

I was extremely hesitant to release some of my prototype files for this project, however I do see the advantages in this setup for my home lab. So I wanted to push it under GNU GPL and have some fun with it.

This is a memory layer written in python, it connects to worker agents then will inject a distilled memory prompt before processing agent input. Already connected to web interface "code-assistant.html". This operates off the principal of keywords while incorporating a deduping process.

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

Next Implementations:

> ->> Implement ANSI Escape codes to chatbox in Web UI

> ->> Implement Tensor Parallelism to incorperate multi GPU support for worker agent node scheduler

> ->> Add Plotly or Matplotlib graphs to homescreen (ControlplaneIP:port/) - [index.html]

> ->> incorperate automated counter/timer for processing memory facts && add a web UI for editing prompts containing automated distilled memory injection for AI model profile

> ->> user authentication for profile use

> ->> Deduping Memory Facts 

> ->> Suggested Memory Keywords depending on the profiles(s)
