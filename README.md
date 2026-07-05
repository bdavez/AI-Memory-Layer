# AI MEMORY LAYER

Written in python, then extended out to JavaScript with Flask for a Web Managment Interface. 

I was extremely hesitant to release some of my prototype files for this project, however I do see the advantages in this setup for my home lab. So I wanted to push it under GNU GPL and have some fun with it.

This is a memory layer written in python, it connects to worker agents then will inject a distilled memory prompt before processing agent input. Already connected to web interface "code-assistant.html". This operates off the principal of keywords while incorporating a deduping process.

*** I will update the README after I finish incorporating the deduping process, then create an official package for worker agent and control plane / scheduler system. The keyword and memory fact display system is fully working, heartbeat status updates are fully connected to API however may need to check backend as some values changes since revision 4 if graphs are not updating. Please note this is just a fun hobby project I'm temporarily holding here until an official build/release. Some files here are deprecated, while others are being finished built out. If your interested in the official release please wait and look towards the releases section for an official beta / alpha.***

### This uses both pip and python are required to be installed first

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

###Once the server is running it will display your IP address, web management interface is by default using port 8000. 

#### EXAMPLE - So to access Web Chat interface, the following URL "IPADDRESS:PORT/code-assistant.html" or "IPADDRESS:PORT/memory-debug.html" would be used. Ensure it matches up with client that is running the agent python script as well as running ollama and has models downloaded, or Web Chat will remain unpopulated. 

>[
> Next 
> ->> user authentication for profile use
> ->> Deduping Memory Facts 
> ->> Suggested Memory Keywords depending on the profiles())
>]