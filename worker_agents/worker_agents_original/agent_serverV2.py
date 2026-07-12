import re
import subprocess
from flask import Flask, request, Response

ANSI_ESCAPE_RE = re.compile(r'\x1b\[[0-9;?]*[A-Za-z]')

def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE_RE.sub('', text)

ansi_log = []

app = Flask(__name__)

@app.post("/agent/jobs/<job_id>/run")
def run_job(job_id):
    payload = request.json or {}
    model = payload.get("model")
    prompt = payload.get("prompt")

    def stream():
        cmd = ["ollama", "run", model, prompt]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)

        for line in proc.stdout:
            # 1. Log raw ANSI + text
            ansi_log.append(line)

            # 2. Strip ANSI for chatbox
            clean_line = strip_ansi(line)

            # 3. Send stripped text to the chatbox
            yield f"data: {clean_line}\n\n"

        yield "event: done\ndata: {}\n\n"


    return Response(stream(), mimetype="text/event-stream")

@app.get("/ansi-log")
def get_ansi_log():
    return {"log": ansi_log}

@app.post("/ansi-log/reset")
def reset_worker_ansi():
    global ansi_log
    ansi_log = []
    return {"status": "cleared"}


app.run(host="0.0.0.0", port=9000)