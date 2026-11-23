# GAIA Agent

My final project for the [Hugging Face Agents Course](https://huggingface.co/learn/agents-course) (Unit 4): an agent that answers questions from the GAIA benchmark, which mix web research, files (Excel, images, audio, code) and multi-step reasoning.

**Score: 70% (14/20) on the course leaderboard**, with five of the six misses being questions whose attached files the course API returned as 404.

## How it works

```
questions API ──► agent.py ──► one scratch dir per task (+ attached file)
                                   │
                                   ▼
                     claude -p (headless Claude Code)
                     tools: WebSearch, WebFetch, Read (images too),
                            Bash for Python, transcription, parsing
                                   │
                                   ▼
                     "FINAL ANSWER: ..." ──► answers.json ──► submit API
```

- **Tool loop from Claude Code.** Instead of reimplementing search, fetch, file reading and a sandbox, each task runs `claude -p` in an isolated directory with an allowlist of tools.
- **GAIA answer format.** The system prompt enforces the benchmark's exact-match rules (no units, no thousands separators, minimal words), and the answer is parsed from a `FINAL ANSWER:` line.
- **Cached and resumable.** Answers are saved after each task, so failed ones can be rerun with `--only` without paying for the rest. Submission is a separate step.
- **Parallel.** Tasks run concurrently with a thread pool and a per-task timeout.
- **Auditable.** Each task directory keeps the attached file and the agent's final transcript.

## Run

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python agent.py                      # solve all questions, cache to answers.json
python agent.py --only 99c9cc74      # rerun specific tasks
python agent.py --submit --username <hf-user> --code-url <public repo url>
```

Requires the [Claude Code CLI](https://docs.claude.com/en/docs/claude-code) logged in.
