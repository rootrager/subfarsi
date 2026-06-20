"""
SubFarsiPro diagnostics CLI.

Usage:
    python -m subfarsi.diagnose

Prints information about the runtime environment and which
providers are configured (booleans only, never the actual keys).
"""

import platform
import sys
from typing import Dict


def _print_header(title: str) -> None:
    print("\n" + title)
    print("-" * len(title))


def _bool_icon(value: bool) -> str:
    return "✅" if value else "❌"


def _check_dependencies() -> Dict:
    # Lazy imports to avoid impacting normal app startup
    from core_v4 import SubFarsiCore

    return SubFarsiCore.check_system_dependencies()


def _check_api_keys() -> Dict[str, bool]:
    from core_v4 import ConfigManager

    cm = ConfigManager()
    providers = ["gemini", "openai", "groq", "openrouter", "nvidia"]
    results: Dict[str, bool] = {}
    for p in providers:
        key = cm.get_api_key(p)
        results[p] = bool(key)
    return results


def main() -> None:
    """Run diagnostics and print a human-friendly report."""
    _print_header("SubFarsiPro Diagnostics")
    print(f"Python version : {platform.python_version()} ({sys.executable})")
    print(f"OS / Platform  : {platform.system()} {platform.release()} ({platform.machine()})")

    # Dependencies
    deps = _check_dependencies()
    _print_header("Core Dependencies")
    ffmpeg = deps.get("ffmpeg", {})
    ollama = deps.get("ollama", {})
    print(f"FFmpeg available : {_bool_icon(bool(ffmpeg.get('available')))}  {ffmpeg.get('message', '')}")
    print(f"Ollama available : {_bool_icon(bool(ollama.get('available')))}  {ollama.get('message', '')}")

    # API keys (booleans only)
    _print_header("API Key Configuration (env or config.json)")
    api_status = _check_api_keys()
    for provider, present in api_status.items():
        print(f"{provider:<10}: {_bool_icon(present)}")

    print("\nDone. If you open a bug report, you can paste this section (it contains no secrets).")


if __name__ == "__main__":
    main()

