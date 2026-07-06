# backend/api_jobs.py

from flask import Blueprint, request, jsonify, Response
import logging
import requests
import uuid

from .jobs_core import (
    create_job,
    get_job,
    list_jobs_grouped,
    cancel_job,
    retry_job,
    _get_worker_url,
    refresh_all_jobs,
    refresh_job_status,
)

bp = Blueprint("jobs", __name__, url_prefix="/api/jobs")
logger = logging.getLogger(__name__)


@bp.route("", methods=["POST"])
def api_create_job():
    data = request.get_json(force=True) or {}
    job_type = data.get("type")
    model = data.get("model", "")  # compiler may not need a model
    job_input = data.get("input") or {}

    if not job_type:
        return jsonify({"error": "type required"}), 400

    try:
        job = create_job(job_type, model, job_input)
        return jsonify({"id": job["id"], "status": job["status"]}), 200
    except Exception as e:
        logger.exception("[api_jobs] create_job failed")
        return jsonify({"error": str(e)}), 500


@bp.route("/<job_id>", methods=["GET"])
def api_get_job(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    return jsonify(job), 200


@bp.route("/pending", methods=["GET"])
def api_pending():
    groups = list_jobs_grouped()
    return jsonify(list(groups.get("pending", {}).values())), 200


@bp.route("/running", methods=["GET"])
def api_running():
    groups = list_jobs_grouped()
    return jsonify(list(groups.get("running", {}).values())), 200


@bp.route("/completed", methods=["GET"])
def api_completed():
    groups = list_jobs_grouped()
    return jsonify(list(groups.get("completed", {}).values())), 200


@bp.route("/failed", methods=["GET"])
def api_failed():
    groups = list_jobs_grouped()
    return jsonify(list(groups.get("failed", {}).values())), 200


@bp.route("/all", methods=["GET"])
def api_all_jobs():
    """
    Return all jobs grouped by status.
    """
    groups = list_jobs_grouped()
    return jsonify(groups), 200


@bp.route("/refresh-all", methods=["GET"])
def api_refresh_all():
    """
    Refresh all jobs from workers and return grouped view.
    """
    refresh_all_jobs()
    groups = list_jobs_grouped()
    return jsonify(groups), 200


@bp.route("/<job_id>/refresh", methods=["GET"])
def api_refresh_job(job_id):
    job = refresh_job_status(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    return jsonify(job), 200


@bp.route("/<job_id>/progress", methods=["GET"])
def api_job_progress(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    return jsonify(
        {
            "id": job["id"],
            "status": job.get("status"),
            "progress": job.get("progress"),
        }
    ), 200


@bp.route("/<job_id>/metadata", methods=["GET"])
def api_job_metadata(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404

    meta = {
        "id": job["id"],
        "type": job.get("type"),
        "model": job.get("model"),
        "assigned_machine": job.get("assigned_machine"),
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "status": job.get("status"),
        "error": job.get("error"),
        "progress": job.get("progress"),
        "retry_count": job.get("retry_count", 0),
    }
    return jsonify(meta), 200


@bp.route("/<job_id>/cancel", methods=["POST"])
def api_cancel(job_id):
    try:
        job = cancel_job(job_id)
        return jsonify(job), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/<job_id>/retry", methods=["POST"])
def api_retry(job_id):
    try:
        job = retry_job(job_id)
        return jsonify(job), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/<job_id>/stream", methods=["GET"])
def api_stream(job_id):
    """
    Proxy SSE stream from worker /agent/jobs/<id>/stream to the UI.
    """
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404

    base = _get_worker_url(job)
    url = f"{base}/agent/jobs/{job_id}/stream"

    def proxy_stream():
        try:
            with requests.get(url, stream=True) as resp:
                for chunk in resp.iter_content(chunk_size=None):
                    if not chunk:
                        continue
                    try:
                        text = chunk.decode("utf-8")
                    except Exception:
                        continue
                    yield text
        except Exception as e:
            logger.exception(f"[api_jobs] stream proxy error for {job_id}: {e}")
            yield "event: done\ndata: {}\n\n"

    return Response(proxy_stream(), mimetype="text/event-stream")

@bp.route("/assistant/run", methods=["GET"])
def api_assistant_run():
    import uuid
    from .state import heartbeat_registry

    model = request.args.get("model")
    prompt = request.args.get("prompt")

    job_id = str(uuid.uuid4())

    # Build job object
    job = {
        "id": job_id,
        "model": model,
        "prompt": prompt,
        "assigned_machine": "uno",
    }

    # ⭐ FIX: Use worker IP instead of hostname
    worker_info = heartbeat_registry.get("uno")
    if not worker_info:
        return Response("event: error\ndata: Worker 'uno' not found\n\n", mimetype="text/event-stream")

    worker_ip = worker_info.get("primary_ip")
    worker_port = worker_info.get("agent_port", 9000)

    if not worker_ip:
        return Response("event: error\ndata: Worker IP missing\n\n", mimetype="text/event-stream")

    url = f"http://{worker_ip}:{worker_port}/agent/jobs/{job_id}/run"

    def stream():
        try:
            r = requests.post(url, json=job, stream=True)
            for chunk in r.iter_content(chunk_size=None):
                if chunk:
                    yield chunk
        except Exception as e:
            yield f"event: error\ndata: {str(e)}\n\n"

    return Response(stream(), mimetype="text/event-stream")
