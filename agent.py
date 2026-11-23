"""GAIA agent for the Hugging Face Agents Course (Unit 4).

Each question runs in its own scratch directory through Claude Code in
headless mode (`claude -p`), which supplies the tool loop: web search,
page fetching, file reading (including images) and Python via Bash.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

API = "https://agents-course-unit4-scoring.hf.space"
ROOT = Path(__file__).parent
WORK = ROOT / "work"
ANSWERS = ROOT / "answers.json"

SYSTEM = """You are a general AI assistant solving a GAIA benchmark question.
Use your tools: search the web, fetch pages, read attached files and run Python to verify.
Do not guess when you can check. Attached files are in the current directory.
For audio, transcribe it first (e.g. pip install openai-whisper, then run whisper).
For YouTube videos, look for transcripts, descriptions or pages that quote them.

Finish with one line exactly in this format:
FINAL ANSWER: <answer>
The answer is a number, as few words as possible, or a comma separated list.
Numbers: no thousands separators, no units unless asked. Strings: no articles, no abbreviations.
Follow any formatting the question asks for (order, case, rounding)."""


def fetch_questions():
    r = requests.get(f"{API}/questions", timeout=30)
    r.raise_for_status()
    return r.json()


def download_file(task_id, name, dest):
    r = requests.get(f"{API}/files/{task_id}", timeout=60)
    r.raise_for_status()
    (dest / name).write_bytes(r.content)


def solve(q, model, timeout):
    task_id = q["task_id"]
    dest = WORK / task_id
    dest.mkdir(parents=True, exist_ok=True)
    prompt = q["question"]
    if q.get("file_name"):
        try:
            download_file(task_id, q["file_name"], dest)
            prompt += f"\n\nAttached file: ./{q['file_name']}"
        except requests.RequestException:
            prompt += f"\n\n(The attached file {q['file_name']} could not be downloaded.)"

    cmd = [
        "claude", "-p", prompt,
        "--model", model,
        "--output-format", "json",
        "--append-system-prompt", SYSTEM,
        "--allowedTools", "WebSearch", "WebFetch", "Read", "Glob", "Grep", "Bash", "Write",
        "--permission-mode", "acceptEdits",
    ]
    try:
        out = subprocess.run(cmd, cwd=dest, capture_output=True, text=True, timeout=timeout)
        text = json.loads(out.stdout).get("result", "")
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        text = f"ERROR: {e}"
    (dest / "transcript.txt").write_text(text)
    m = re.findall(r"FINAL ANSWER:\s*(.+)", text)
    if m:
        return m[-1].strip().strip("*`").strip()
    lines = text.strip().splitlines()
    return lines[-1] if lines else ""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="sonnet")
    p.add_argument("--only", nargs="*", help="task_id prefixes to (re)run")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--timeout", type=int, default=900)
    p.add_argument("--submit", action="store_true", help="submit cached answers")
    p.add_argument("--username", default=os.getenv("HF_USERNAME"))
    p.add_argument("--code-url", default=os.getenv("AGENT_CODE_URL"))
    a = p.parse_args()

    answers = json.loads(ANSWERS.read_text()) if ANSWERS.exists() else {}

    if a.submit:
        if not a.username or not a.code_url:
            sys.exit("Need --username and --code-url (public link to this code).")
        payload = {
            "username": a.username,
            "agent_code": a.code_url,
            "answers": [{"task_id": k, "submitted_answer": v} for k, v in answers.items()],
        }
        r = requests.post(f"{API}/submit", json=payload, timeout=120)
        print(r.status_code, json.dumps(r.json(), indent=2))
        return

    qs = fetch_questions()
    todo = [q for q in qs if (a.only and any(q["task_id"].startswith(o) for o in a.only))
            or (not a.only and q["task_id"] not in answers)]
    print(f"Solving {len(todo)} of {len(qs)} questions with {a.model}...")

    def run(q):
        ans = solve(q, a.model, a.timeout)
        print(f"[{q['task_id'][:8]}] {q['question'][:60]!r} -> {ans}", flush=True)
        return q["task_id"], ans

    with ThreadPoolExecutor(a.workers) as ex:
        for tid, ans in ex.map(run, todo):
            answers[tid] = ans
            ANSWERS.write_text(json.dumps(answers, indent=2))
    print(f"Saved {len(answers)} answers to {ANSWERS.name}. Submit with --submit.")


if __name__ == "__main__":
    main()
