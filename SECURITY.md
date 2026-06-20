## SubFarsiPro Security & Configuration Guide

This document explains how to configure API keys, handle secrets safely, and
collect logs without exposing sensitive data.

---

### 1. Where configuration lives

- **User config file**: `config.json`
  - Stored in a writable **user data directory**, e.g.:
    - Windows: `%LOCALAPPDATA%\SubFarsiPro\config.json`
    - Linux: `~/.local/share/subfarsipro/config.json`
    - macOS: `~/Library/Application Support/SubFarsiPro/config.json`
- **Environment variables** (recommended for secrets):
  - `SUBFARSIPRO_GEMINI_API_KEY`
  - `SUBFARSIPRO_OPENAI_API_KEY`
  - `SUBFARSIPRO_GROQ_API_KEY`
  - `SUBFARSIPRO_OPENROUTER_API_KEY`
  - `SUBFARSIPRO_NVIDIA_API_KEY`
  - Optional: `SUBFARSIPRO_OLLAMA_URL`

At runtime, SubFarsiPro loads API keys in this order:

1. **Environment variables** (never logged, highest priority)
2. `config.json` `api_keys` section
3. If still missing, the app logs a warning and the GUI shows a
   clear message asking you to set the key via Settings.

Placeholders like `YOUR_GEMINI_API_KEY_HERE` are treated as **missing**.

---

### 2. Never commit secrets

- Do **not** commit real API keys to:
  - `config.json`
  - `.env`
  - any source file or script
- Use `.env.example` as a template and create your own **local** `.env`:

```bash
cp .env.example .env
# edit .env and add your real keys (do not commit)
```

`.env` is ignored by `.gitignore` and must never be checked in.

---

### 3. Logging & privacy

- Each run creates a log file under the user data directory:
  - `logs/subfarsipro_YYYYMMDD_HHMMSS.log`
- Logs include only **metadata**, such as:
  - Provider name
  - Model name
  - Batch size
  - HTTP status codes
  - Retry attempts
- **Secrets are never logged**:
  - No API keys
  - No full request payloads

When sharing logs in bug reports, quickly scan them for anything you consider
private (file paths, video names) and redact as needed.

---

### 4. Reporting vulnerabilities

If you believe you have found a security issue in SubFarsiPro:

1. Do **not** open a public GitHub issue with sensitive details.
2. Contact the maintainer privately (e-mail / GitHub security advisory).
3. Include:
   - SubFarsiPro version
   - OS and Python version
   - A minimal description of the issue

---

### 5. Local runtime dependencies

SubFarsiPro relies on:

- `ffmpeg` (downloaded to a per-user bin directory by the Setup Wizard, or
  discovered on your system PATH)
- `Ollama` (installed and managed by the user, not bundled)

These are executed **locally**; no media is uploaded to third-party services
unless you explicitly choose a cloud translation provider (Gemini, Groq,
OpenRouter, NVIDIA, etc.).

For maximum privacy, you can:

- Use only **local** transcription (Whisper/faster-whisper)
- Use **Ollama** as the translation provider

In that mode, your video never leaves your machine.

