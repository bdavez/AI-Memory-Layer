from flask import Flask, request, Response
import subprocess

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
            yield f"data: {line}\n\n"

        yield "event: done\ndata: {}\n\n"

    return Response(stream(), mimetype="text/event-stream")

app.run(host="0.0.0.0", port=9000)
