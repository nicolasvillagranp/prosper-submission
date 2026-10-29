"""The Docker worker: does the slow work the web page asks for, plus the daily morning job.

    python -m worker

- Audio briefings: the page inserts a row in `briefings` (status "requested"); the worker
  claims it, makes the mp3 (pipeline/briefing.py) and marks it "ready" (or "failed").
- First topics: a user who just finished onboarding gets topics right away (checked every
  `worker.new_user_check_seconds`), instead of waiting for the next morning.
- Morning job: once a day at `worker.morning_hour` (config/config.yaml), in a background
  thread so briefings keep flowing while it runs. Also at start-up if today's run is missing;
  users who already have today's topics are skipped, so restarting is harmless.
"""
