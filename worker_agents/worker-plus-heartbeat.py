#just wraps the agent and keeps it running; you can extend later with more supervision

from worker_agent import main as worker_main

if __name__ == "__main__":
    # Simple supervisor for now; you can add retry/backoff later.
    worker_main()