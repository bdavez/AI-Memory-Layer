# AI Memory Layer for Distributed System

I was extremely hesitant to release some of my prototype files for this project, however I do see the advantages in this setup for my home lab. So I wanted to push it under GNU GPL and have some fun with it.

This is a memory layer written in python, it connects to worker agents then will inject a distilled memory prompt before processing agent input. Already connected to web interface "code-assistant.html". This operates off the principal of keywords while incorporating a deduping process.

*** I will update the README after I finish incorporating the deduping process, then create an official package for worker agent and control plane / scheduler system. The keyword and memory fact display system is fully working, heartbeat status updates are fully connected to API however may need to check backend as some values changes since revision 4 if graphs are not updating. Please note this is just a fun hobby project I'm temporarily holding here until an official build/release. Some files here are deprecated, while others are being finished built out. If your interested in the official release please wait and look towards the releases section for an official beta / alpha.***

Please ensure flask module is installed for python as this uses it to offer up the management interface and memory management interface over a website interface, as well as the AI agent communication website chatbot.