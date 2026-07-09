# agent_server.py — safe mock streaming agent

from flask import Flask, request, Response
import time

app = Flask(__name__)

PUBLIC_RELEASE = True


@app.post("/agent/jobs/<job_id>/run")
def run_job(job_id):
    payload = request.json or {}
    model = payload.get("model", "mock-model")
    prompt = payload.get("prompt", "")

    def stream():
        if PUBLIC_RELEASE:
            # Safe, fake streaming output
            yield f"data: [mock] running model={model} on prompt length={len(prompt)}\n\n"
            time.sleep(0.5)
            yield "data: [mock] this is a placeholder agent response in public release mode.\n\n"
            time.sleep(0.5)
            yield "event: done\ndata: {}\n\n"
            return

        # ORIGINAL BEHAVIOR (kept for private use, but not used in public mode)
        # import subprocess
        # cmd = ["ollama", "run", model, prompt]
        # proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
        # for line in proc.stdout:
        #     yield f"data: {line}\n\n"
        # yield "event: done\ndata: {}\n\n"

    return Response(stream(), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000)
