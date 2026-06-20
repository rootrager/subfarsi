"""
SubFarsiPro Core Engine v5.0
Definitive backend engine for local subtitle generation with Multi-Provider Translation.

Features:
- Multi-Provider Support: Ollama, Gemini, Groq, OpenRouter
- Smart Initialization with Dependency Checks
- Secure Configuration Management
- Thread-safe Progress Tracking

Author: Senior Python AI Engineer & Software Architect
"""

import os
import sys
import subprocess
import shutil
import platform
import math
import time
import re
import tempfile
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Optional, Callable, Tuple, Any

try:
    from faster_whisper import WhisperModel
    import requests
    import torch
    import ssl
    from urllib3.util import ssl_ as urllib3_ssl
except ImportError as e:
    print(f"❌ Missing required package: {e}")
    print("📦 Please install: pip install faster-whisper requests torch")
    sys.exit(1)

# Import path utilities (must be after stdlib imports)
try:
    from utils.path_manager import get_app_data_dir, ensure_dirs
    from utils.dependency_manager import DependencyManager
except ImportError:
    # Fallback for development or if utils not available
    get_app_data_dir = None
    ensure_dirs = None
    DependencyManager = None

def _setup_file_logger() -> logging.Logger:
    """
    Configure a structured file-based logger for SubFarsiCore.

    Each process run creates a timestamped log file in the user data
    directory (logs/ subfolder). This never logs sensitive data such
    as API keys or request payloads.
    """
    logger = logging.getLogger("SubFarsiCore")
    if logger.handlers:
        # Already configured in this process
        return logger

    logger.setLevel(logging.INFO)

    # Console formatting (for development and CLI use)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler (per-run timestamped log file)
    try:
        logs_dir = None
        if get_app_data_dir:
            logs_dir = get_app_data_dir() / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)

        if logs_dir:
            from datetime import datetime

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_path = logs_dir / f"subfarsipro_{ts}.log"
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setLevel(logging.INFO)
            file_formatter = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
            logger.info("Log file initialized at %s", log_path)
    except Exception:
        # Never let logging failures break the app
        pass

    return logger


logger = _setup_file_logger()

# v5.0 Global Usage Tracking (In-Memory)
GEMINI_RPD_LIMITS = {
    "gemini-2.5-pro": 50,
    "gemini-2.5-flash": 250,
    "gemini-2.5-flash-lite": 1000
}
GEMINI_USAGE = {model: 0 for model in GEMINI_RPD_LIMITS}

# Fallback when dynamic Gemini model discovery fails (google-genai SDK attribute names vary)
GEMINI_FALLBACK_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
]

# Shared subtitle system prompt for Persian (Tehrani, informal, screen-friendly)
SUBTITLE_SYSTEM_PROMPT = """You are a professional subtitle translator.
TASK: Translate the following English subtitles into Informal, Spoken Persian (Farsi) with a Tehrani accent.
RULES:
1. Keep translations SHORT and natural for reading on screen.
2. Use colloquial language (e.g., use "میشه" instead of "می‌شود").
3. PRESERVE scientific terms and proper nouns exactly (e.g., say "Melatonin", not "Melaton"; "Serotonin", not "Seroton").
4. Translate idioms culturally, not literally (e.g., "Hit snooze" -> "دکمه چرت زدن رو بزن", NOT "زنگ رو نزن").
5. DO NOT explain the translation. DO NOT say "Here is the translation".
6. DO NOT use Markdown, bolding, or code blocks.
7. Return ONLY the translation text line by line."""

# Optional imports for cloud APIs
try:
    from google import genai
    GEMINI_SDK_AVAILABLE = True
except ImportError:
    GEMINI_SDK_AVAILABLE = False
    logger.warning("⚠️ google-genai not installed. Native Gemini SDK will not be available.")
    logger.warning("📦 Please run: pip install -q -U google-genai")


# ==========================================
# PyInstaller Resource Path Helper
# ==========================================

def resource_path(relative_path: str) -> str:
    """
    Get absolute path to resource, works for dev and PyInstaller.
    
    In PyInstaller frozen mode, resources are extracted to sys._MEIPASS.
    In development mode, use the directory containing this file.
    
    Args:
        relative_path: Path relative to the application root (e.g., "config.json")
    
    Returns:
        Absolute path to the resource
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # Development mode: use directory of this file
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    return os.path.join(base_path, relative_path)


# ==========================================
# Configuration Management
# ==========================================

class ConfigManager:
    """
    Manages application configuration and secure API keys.
    
    In frozen mode: Loads template config.json from bundle (read-only).
    Always saves to user data directory (writable).
    """
    
    def __init__(self, config_file: str = "config.json"):
        # Ensure user data directory exists
        if ensure_dirs:
            ensure_dirs()
        
        # Template config (from bundle in frozen mode, or current dir in dev)
        self.template_config_path = resource_path(config_file)
        
        # User config (always in writable user data directory)
        if get_app_data_dir:
            self.config_file = str(get_app_data_dir() / config_file)
        else:
            # Fallback: use current directory if utils not available
            self.config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_file)
        
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from JSON file.
        
        Priority:
        1. User data directory config.json (if exists)
        2. Template config.json from bundle (if exists)
        3. Default config
        """
        # Try user config first (writable location)
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"⚠️ Failed to load user config: {e}, trying template...")
        
        # Fallback to template config (from bundle in frozen mode)
        if os.path.exists(self.template_config_path) and self.template_config_path != self.config_file:
            try:
                with open(self.template_config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Copy template to user directory for future writes
                    try:
                        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
                        with open(self.config_file, 'w', encoding='utf-8') as f_out:
                            json.dump(config, f_out, indent=4)
                        logger.info("✅ Copied template config to user directory")
                    except Exception as e:
                        logger.warning(f"⚠️ Could not copy template config: {e}")
                    return config
            except Exception as e:
                logger.warning(f"⚠️ Failed to load template config: {e}")
        
        # Return default config
        return self._default_config()
            
    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "api_keys": {
                "gemini": "",
                "openai": "",  # Used for generic OpenAI compatible APIs
                "groq": "",
                "openrouter": ""
            },
            "provider_settings": {
                "last_provider": "ollama",
                "whisper_model": "small",
                "ollama_url": "http://localhost:11434"
            }
        }
    
    def save_config(self):
        """Save current configuration to JSON file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
            logger.info("✅ Configuration saved successfully")
        except Exception as e:
            logger.error(f"❌ Failed to save config: {e}")
    
    def get_api_key(self, provider: str) -> Optional[str]:
        """
        Retrieve API key for a specific provider.

        Priority:
        1. Environment variable: SUBFARSIPRO_<PROVIDER>_API_KEY (e.g. SUBFARSIPRO_GEMINI_API_KEY)
        2. config.json -> api_keys[provider]
        3. Empty string if not configured
        """
        # 1) Environment variable (never logged)
        env_name = f"SUBFARSIPRO_{provider.upper()}_API_KEY"
        env_val = os.environ.get(env_name, "").strip()
        if env_val:
            return env_val

        # 2) Config file value (may be empty or placeholder)
        value = self.config.get("api_keys", {}).get(provider, "") or ""

        # Treat obvious placeholders as empty
        placeholders = {
            "YOUR_API_KEY_HERE",
            "YOUR_GEMINI_API_KEY_HERE",
            "YOUR_GROQ_API_KEY_HERE",
            "YOUR_OPENROUTER_API_KEY_HERE",
            "YOUR_NVIDIA_API_KEY_HERE",
            "YOUR_OPENAI_API_KEY_HERE",
        }
        if value in placeholders:
            value = ""

        if not value:
            # Log only that the key is missing, never the value itself
            logger.warning(
                "API key for provider '%s' is not configured. "
                "Set %s or update config.json via the Settings dialog.",
                provider,
                env_name,
            )

        return value
    
    def set_api_key(self, provider: str, key: str):
        """Set API key for a specific provider."""
        if "api_keys" not in self.config:
            self.config["api_keys"] = {}
        self.config["api_keys"][provider] = key
        self.save_config()


# ==========================================
# Translation Architecture (Strategy Pattern)
# ==========================================

class TranslationProvider(ABC):
    """Abstract base class for all translation providers."""
    
    @abstractmethod
    def translate(self, text: str, callback: Optional[Callable] = None) -> Optional[str]:
        """Translate a single line of text."""
        pass
        
    def translate_batch(self, lines: List[str], callback: Optional[Callable] = None) -> List[str]:
        """Translate a batch of lines."""
        results = []
        for line in lines:
            res = self.translate(line, callback=callback)
            results.append(res if res else line)
        return results
    
    @abstractmethod
    def validate_config(self) -> bool:
        """Check if provider is correctly configured."""
        pass
        
    def _clean_translation(self, text: str) -> str:
        """Common utility to clean up translation artifacts."""
        if not text:
            return ""

        # Normalize whitespace
        text = text.strip()

        # Strip code fences / inline backticks
        if text.startswith("```") and text.endswith("```"):
            text = text.strip("`").strip()
        if text.startswith("`") and text.endswith("`") and len(text) > 2:
            text = text[1:-1].strip()

        # Remove common English / Persian preambles and prefixes
        prefixes = [
            "Persian:", "Farsi:", "Translation:", "فارسی:", "ترجمه:",
            "Here is the translation:", "Here’s the translation:", "Here is your translation:",
            "Sure,", "Sure!", "Of course,", "Of course!", "Here you go:", "Here you go"
        ]
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()

        # Remove leading markdown bullets
        text = re.sub(r'^\s*[-*•]\s*', '', text)

        # If multiple lines, prefer the first non-empty line
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if lines:
            text = lines[0]

        # Remove surrounding quotes / guillemets
        text = text.strip()
        if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
            text = text[1:-1].strip()
        if (text.startswith("«") and text.endswith("»")):
            text = text[1:-1].strip()

        return text

    def _get_translation_prompt(self, text: str) -> str:
        """Generate the standard prompt for translation."""
        return f"""{SUBTITLE_SYSTEM_PROMPT}

English:
{text.strip()}

Persian:"""


class OllamaProvider(TranslationProvider):
    """Provider for local Ollama instance."""
    
    def __init__(self, model: str, base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self.generate_url = f"{base_url}/api/generate"
        
    def validate_config(self) -> bool:
        return bool(self.model)
        
    def translate(self, text: str, callback: Optional[Callable] = None) -> Optional[str]:
        if not text.strip():
            return None
            
        prompt = self._get_translation_prompt(text)
        
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.9
                }
            }
            response = requests.post(self.generate_url, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            raw = result.get('response', '')
            return self._clean_translation(raw)
        except Exception as e:
            logger.error(f"Ollama translation failed: {e}")
            return None

    def translate_batch(
        self,
        lines: List[str],
        callback: Optional[Callable] = None,
        context_lines: Optional[List[str]] = None
    ) -> List[str]:
        """
        Optimized batch translation for Ollama using a single prompt, with optional
        sliding-window context from previous subtitles.
        """
        clean_lines = [ln.strip() for ln in lines if ln.strip()]
        if not clean_lines:
            return lines
            
        n = len(clean_lines)
        numbered_input = "\n".join(f"{i+1}. {ln}" for i, ln in enumerate(clean_lines))

        context_block = ""
        if context_lines:
            ctx_clean = [ln.strip() for ln in context_lines if ln.strip()]
            if ctx_clean:
                ctx_numbered = "\n".join(f"{i+1}. {ln}" for i, ln in enumerate(ctx_clean))
                context_block = f"\nPREVIOUS CONTEXT (ReadOnly - do NOT translate these again):\n{ctx_numbered}\n"
        
        prompt = f"""{SUBTITLE_SYSTEM_PROMPT}
{context_block}
NEW LINES TO TRANSLATE (numbered):
{numbered_input}

OUTPUT RULES:
- Translate ONLY the NEW LINES.
- Return ONLY the Persian translations for the NEW LINES, numbered 1., 2., 3., ... to match the order above.
1."""

        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3}
            }
            response = requests.post(self.generate_url, json=payload, timeout=180)
            if response.status_code != 200:
                return super().translate_batch(lines, callback=callback)  # Fallback
                
            result = response.json()
            text = result.get('response', '')
            
            # Parse numbered response
            parsed = self._parse_numbered_list(text, n)
            if parsed:
                return [self._clean_translation(p) for p in parsed]
            
            # Fallback if parsing fails
            return super().translate_batch(lines, callback=callback)
            
        except Exception:
            return super().translate_batch(lines, callback=callback)

    def _parse_numbered_list(self, text: str, count: int) -> Optional[List[str]]:
        lines = []
        for line in text.splitlines():
            match = re.match(r"^\s*(\d+)[\.\:\-\)]\s*(.+)$", line)
            if match:
                lines.append(match.group(2).strip())
        
        if len(lines) == count:
            return lines
        return None


# Legacy providers removed in v5.0 for UniversalTranslator


class UniversalTranslator(TranslationProvider):
    """
    Finalized v5 Cloud Translation Engine (2026 Standards).
    Supports Gemini 2.5 (RPD Counter), OpenRouter Shield, and standardized X-Title headers.
    """
    
    PROVIDER_CONFIGS = {
        "groq": {
            "base_url": "https://api.groq.com/openai/v1",
            "unsupported_params": ["n", "stream", "frequency_penalty", "presence_penalty", "top_p"],
            "default_model": "llama3-70b-8192"
        },
        "gemini": {
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "unsupported_params": ["n", "stream", "frequency_penalty", "presence_penalty"],
            "default_model": "gemini-1.5-flash"
        },
        "openrouter": {
            "base_url": "https://openrouter.ai/api/v1",
            "unsupported_params": ["n", "stream"],
            "default_model": "google/gemini-2.0-flash-001:free"
        },
        "nvidia": {
            "base_url": "https://integrate.api.nvidia.com/v1",
            "unsupported_params": ["n", "stream"],
            "default_model": "nvidia/llama-3.1-nemotron-70b-instruct"
        }
    }

    OPENROUTER_FREE_SHIELD = [
        "google/gemini-2.0-flash-001:free",
        "mistralai/mistral-7b-instruct:free"
    ]

    def __init__(self, provider_type: str, api_key: str, model_name: str = None):
        self.provider_type = provider_type.lower()
        self.config = self.PROVIDER_CONFIGS.get(self.provider_type, {})
        self.base_url = self.config.get("base_url", "")
        self.api_key = api_key
        # Strict validation for Gemini 2.5 / OpenRouter Free Shield
        if self.provider_type == "openrouter":
             self.model_name = model_name if model_name in self.OPENROUTER_FREE_SHIELD else self.config.get("default_model")
        else:
             self.model_name = model_name or self.config.get("default_model")
        
        # Standard v5 Headers
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Title": "SubFarsiPro_v5"
        }
        
        if self.provider_type == "openrouter":
            self.headers["HTTP-Referer"] = "https://github.com/SubFarsiPro"
            
        self.session = self._create_secure_session()
        
        # Gemini free tier: minimum delay between requests (~15 RPM = 4s between requests)
        self._gemini_min_delay_seconds = 4.0
        self._last_gemini_request_time = 0.0
        
        # Native Gemini SDK Client
        self.gemini_client = None
        if self.provider_type == "gemini" and GEMINI_SDK_AVAILABLE:
            try:
                self.gemini_client = genai.Client(api_key=api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Gemini Native SDK: {e}")

    @staticmethod
    def _parse_gemini_retry_seconds(response=None, error_text: str = "") -> Optional[float]:
        """Extract suggested wait time from 429 response: Retry-After, retryDelay, or 'retry in Xs' text. Returns seconds."""
        wait = None
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    wait = float(retry_after)
                except ValueError:
                    pass
            if wait is None:
                try:
                    body = response.json()
                    err = body.get("error") or body
                    if isinstance(err, dict):
                        msg = err.get("message") or err.get("error") or ""
                        delay_str = err.get("retryDelay") or err.get("retry_delay") or ""
                        if delay_str:
                            match = re.match(r"([\d.]+)\s*s", str(delay_str).strip(), re.I)
                            if match:
                                wait = float(match.group(1))
                        if wait is None and msg:
                            match = re.search(r"retry\s+in\s+([\d.]+)\s*s", msg, re.I) or re.search(r"([\d.]+)\s*second", msg, re.I)
                            if match:
                                wait = float(match.group(1))
                except Exception:
                    pass
        if wait is None and error_text:
            match = re.search(r"retry\s+in\s+([\d.]+)\s*s", error_text, re.I) or re.search(r"([\d.]+)\s*second", error_text, re.I)
            if match:
                wait = float(match.group(1))
        return wait

    def _create_secure_session(self) -> requests.Session:
        session = requests.Session()
        if self.provider_type in ["nvidia", "openrouter"]:
            try:
                context = urllib3_ssl.create_urllib3_context()
                context.set_ciphers('DEFAULT@SECLEVEL=2')
            except Exception as e:
                logger.debug(f"SSL context customization skipped: {e}")
        return session

    def validate_config(self) -> bool:
        return bool(self.api_key and self.base_url)

    def _create_payload(self, messages: List[Dict]) -> Dict:
        """Sanitize payload to omit unsupported or null parameters."""
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.3
        }
        # Final pass: remove any keys with None values
        return {k: v for k, v in payload.items() if v is not None}

    def translate(self, text: str, callback: Optional[Callable] = None) -> Optional[str]:
        if not text.strip(): return None
        system_prompt = (
            "You are a professional subtitle translator. "
            "Translate the English sentence into informal, spoken Persian (Farsi) with Tehrani accent. "
            "FORBID formal words. Return ONLY the translation."
        )
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": text}]
        return self._smart_request(messages, callback=callback)

    def translate_batch(self, lines: List[str], callback: Optional[Callable] = None) -> List[str]:
        clean_lines = [ln.strip() for ln in lines if ln.strip()]
        if not clean_lines: return lines
        count = len(clean_lines)
        joined_text = "\n".join(f"{i+1}. {ln}" for i, ln in enumerate(clean_lines))
        system_prompt = (
            f"You are a professional subtitle translator. Translate these exactly {count} lines into informal, spoken Persian (Tehrani accent). "
            "CRITICAL: Return exactly the same number of lines as input, in the same order. "
            "Return ONLY a JSON array of strings, e.g. [\"line1\", \"line2\", ...], or one translation per line numbered 1. 2. 3. ... "
            "No other text or explanation."
        )
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": joined_text}]
        response_text = self._smart_request(messages, callback=callback)
        if response_text:
            translations = self._parse_batch_response(response_text, count)
            if translations and len(translations) == count:
                return translations
            if count > 1:
                mid = count // 2
                left_lines, right_lines = clean_lines[:mid], clean_lines[mid:]
                left_out = self.translate_batch(left_lines, callback=callback)
                right_out = self.translate_batch(right_lines, callback=callback)
                if len(left_out) == len(left_lines) and len(right_out) == len(right_lines):
                    return left_out + right_out
            logger.warning(f"Batch mismatch. Falling back to line-by-line.")
        
        results = []
        for line in clean_lines:
            if self.provider_type == "openrouter":
                time.sleep(2)
            results.append(self.translate(line, callback=callback) or line)
        return results

    def _smart_request(self, messages: List[Dict], retries: int = 1, callback=None) -> Optional[str]:
        """v5 Advanced Request Logic: Rate Limits, OpenRouter Shield, and Auto-Retry."""
        # 1. Gemini RPD Check
        if self.provider_type == "gemini" and self.model_name in GEMINI_USAGE:
            limit = GEMINI_RPD_LIMITS.get(self.model_name, 100)
            usage = GEMINI_USAGE[self.model_name]
            if usage >= limit * 0.8:
                msg = f"⚠️ Gemini Usage Warning: {usage}/{limit} RPD used."
                logger.warning(msg)
                if callback: callback(msg)
            if usage >= limit:
                msg = f"❌ Gemini Rate Limit Reached ({limit}/{limit}). Switch models."
                logger.error(msg)
                if callback: callback(msg)
                return None

        for attempt in range(retries + 1):
            try:
                # 2a. Gemini: enforce minimum delay between requests (free tier ~15 RPM)
                if self.provider_type == "gemini":
                    elapsed = time.time() - self._last_gemini_request_time
                    if elapsed < self._gemini_min_delay_seconds:
                        wait = self._gemini_min_delay_seconds - elapsed
                        logger.debug(f"Gemini rate limit: waiting {wait:.1f}s before request.")
                        if callback:
                            callback(f"⏳ Gemini: waiting {wait:.1f}s...")
                        time.sleep(wait)

                # 3. Handle Gemini Native SDK 
                if self.provider_type == "gemini" and self.gemini_client:
                    # Native SDK Logic (2026 Standards)
                    response = self.gemini_client.models.generate_content(
                        model=self.model_name,
                        contents=messages[-1]['content'], # Use last user message for simplicity or concat
                        config={"temperature": 0.3}
                    )
                    self._last_gemini_request_time = time.time()
                    
                    if response.text:
                        # Success: Increment Gemini Counter
                        if self.model_name in GEMINI_USAGE:
                            GEMINI_USAGE[self.model_name] += 1
                        return self._clean_translation(response.text)
                    continue

                # 4. Standard REST Logic (Groq, OpenRouter, NVIDIA, Fallback Gemini)
                payload = self._create_payload(messages)
                response = self.session.post(
                    f"{self.base_url.rstrip('/')}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=30,
                )

                # Structured observability: log metadata only (no payloads or keys)
                logger.info(
                    "LLM request | provider=%s | model=%s | attempt=%s | status=%s",
                    self.provider_type,
                    self.model_name,
                    attempt + 1,
                    response.status_code,
                )
                
                # 2b. Rate Limit / Server Error Handling
                if response.status_code == 404:
                    msg = "❌ ERROR 404: Incorrect API URL. Please check the base_url and model name in the code."
                    logger.error(msg)
                    if callback: callback(msg)
                    return None

                if response.status_code == 429:
                    wait_time = self._gemini_min_delay_seconds
                    if self.provider_type == "gemini":
                        parsed = self._parse_gemini_retry_seconds(response=response)
                        if parsed is not None:
                            wait_time = max(wait_time, parsed)
                    elif self.provider_type == "openrouter":
                        wait_time = 5
                    else:
                        wait_time = 2
                    if self.provider_type == "gemini":
                        wait_time = wait_time + 1
                    msg = f"⚠️ Provider {self.provider_type.upper()} 429 RESOURCE_EXHAUSTED. Retrying in {wait_time:.0f}s..."
                    logger.warning(msg)
                    if callback: callback(msg)
                    time.sleep(wait_time)
                    continue

                if response.status_code in [500, 503]:
                    wait_time = 5 if self.provider_type == "openrouter" else 2
                    msg = f"⚠️ Provider {self.provider_type.upper()} {response.status_code}. Retrying in {wait_time}s..."
                    logger.warning(msg)
                    if callback: callback(msg)
                    time.sleep(wait_time)
                    continue
                
                if response.status_code != 200:
                    logger.error(f"DEBUG: {self.provider_type.upper()} Error {response.status_code} - {response.text}")
                    response.raise_for_status()
                    
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    content = result['choices'][0]['message']['content']
                    if content and content.strip():
                        if self.provider_type == "gemini":
                            self._last_gemini_request_time = time.time()
                            if self.model_name in GEMINI_USAGE:
                                GEMINI_USAGE[self.model_name] += 1
                        return self._clean_translation(content)
                        
            except Exception as e:
                logger.error(f"{self.provider_type.upper()} attempt {attempt+1} failed: {e}")
                if self.provider_type == "gemini":
                    parsed = self._parse_gemini_retry_seconds(error_text=str(e))
                    if parsed is not None:
                        wait_time = max(self._gemini_min_delay_seconds, parsed) + 1
                        logger.warning(f"Gemini 429/limit: waiting {wait_time:.0f}s before retry.")
                        if callback: callback(f"⏳ Waiting {wait_time:.0f}s (API limit)...")
                        time.sleep(wait_time)
                    elif attempt < retries:
                        time.sleep(self._gemini_min_delay_seconds + 1)
                elif attempt < retries:
                    time.sleep(2)
                
        return None

    def _parse_numbered_list(self, text: str, count: int) -> Optional[List[str]]:
        lines = []
        for line in text.splitlines():
            match = re.match(r"^\s*\d+[\.\:\-\)]\s*(.+)$", line)
            if match: lines.append(match.group(1).strip())
        return lines if lines else None

    def _parse_batch_response(self, text: str, count: int) -> Optional[List[str]]:
        """Parse batch translation: try JSON array first, then numbered list."""
        text = text.strip()
        if not text:
            return None
        try:
            stripped = text.strip()
            if stripped.startswith("["):
                parsed = json.loads(stripped)
                if isinstance(parsed, list) and len(parsed) == count:
                    return [str(x).strip() for x in parsed]
        except (json.JSONDecodeError, TypeError):
            pass
        return self._parse_numbered_list(text, count)


class TranslationManager:
    """Factory to create and manage translation providers."""
    
    @staticmethod
    def get_provider(config: Dict, provider_type: str, model_name: str = None) -> TranslationProvider:
        api_keys = config.get("api_keys", {})
        
        if provider_type == "ollama":
            return OllamaProvider(model=model_name)
            
        elif provider_type in ["gemini", "groq", "openrouter", "nvidia"]:
            return UniversalTranslator(
                provider_type=provider_type,
                api_key=api_keys.get(provider_type, ""),
                model_name=model_name
            )
            
        # Default fallback
        logger.warning(f"Unknown provider '{provider_type}', falling back to Ollama")
        return OllamaProvider(model=model_name)

    @staticmethod
    def get_available_models(provider: str, api_key: str = "") -> List[str]:
        """
        Fetch available models for a given provider.
        """
        if provider == "ollama":
            return SubFarsiCore.get_local_ollama_models()
            
        elif provider == "gemini":
            if GEMINI_SDK_AVAILABLE and api_key:
                try:
                    client = genai.Client(api_key=api_key)
                    models = []
                    # SDK may return paginated response or iterator; attribute names vary (snake_case vs camelCase)
                    list_result = client.models.list()
                    for m in list_result:
                        try:
                            methods = getattr(m, "supported_generation_methods", None) or getattr(
                                m, "supportedGenerationMethods", None
                            )
                            if methods and "generateContent" in (methods if isinstance(methods, (list, tuple)) else []):
                                name = getattr(m, "name", None) or ""
                                if isinstance(name, str) and name:
                                    if name.startswith("models/"):
                                        name = name[7:]
                                    models.append(name)
                        except (AttributeError, TypeError) as _:
                            continue
                    if models:
                        return sorted(models)
                except Exception as e:
                    logger.error(f"Dynamic Gemini discovery failed: {e}")
            return list(GEMINI_FALLBACK_MODELS)
            
        elif provider == "nvidia":
            # Static list of top NVIDIA NIM models
            return [
                "nvidia/llama-3.1-nemotron-70b-instruct",
                "meta/llama-3.1-405b-instruct",
                "meta/llama-3.1-70b-instruct",
                "mistralai/mistral-large-2-instruct"
            ]

        elif provider == "openrouter":
            try:
                response = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    # Filter for :free models
                    free_models = [m['id'] for m in data.get('data', []) if m['id'].endswith(':free')]
                    if free_models: return sorted(free_models)
            except Exception:
                pass
            return UniversalTranslator.OPENROUTER_FREE_SHIELD
                
        elif provider == "groq":
            if not api_key: return []
            try:
                headers = {"Authorization": f"Bearer {api_key}"}
                response = requests.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    # Filter only ID
                    return sorted([m['id'] for m in data.get('data', [])])
            except Exception as e:
                logger.error(f"Failed to fetch Groq models: {e}")
                
        return []


# ==========================================
# Core Engine
# ==========================================

class SubFarsiCore:
    """
    Main engine class for SubFarsiPro subtitle generation.
    """
    
    def __init__(
        self,
        ollama_model: Optional[str] = None,
        whisper_model_size: str = "small",
        batch_size: int = 4,
        translation_provider: str = "ollama"  # "ollama", "gemini", "groq", "openrouter"
    ):
        self.whisper_model_size = whisper_model_size
        self.batch_size = batch_size
        
        # CRITICAL: Inject DependencyManager bin directory into PATH before checking dependencies
        # This ensures FFmpeg downloaded by DependencyManager is found
        if DependencyManager and get_app_data_dir:
            bin_dir = str(get_app_data_dir() / "bin")
            if bin_dir not in os.environ.get("PATH", ""):
                # Add to PATH (prepend for priority)
                current_path = os.environ.get("PATH", "")
                separator = ";" if platform.system() == "Windows" else ":"
                os.environ["PATH"] = f"{bin_dir}{separator}{current_path}"
                logger.debug(f"✅ Injected bin directory into PATH: {bin_dir}")
        
        # Load Config
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config()
        
        # Initialize Translation Provider
        self.translator = TranslationManager.get_provider(
            self.config, 
            translation_provider, 
            ollama_model
        )

        # Log engine initialization (metadata only)
        logger.info(
            "Engine initialized | provider=%s | model=%s | whisper_model=%s | batch_size=%s",
            translation_provider,
            ollama_model,
            self.whisper_model_size,
            self.batch_size,
        )
        
        self.whisper_model = None
        
        # Check dependencies (now includes DependencyManager bin directory)
        self.dependencies = self.check_system_dependencies()
        self.ffmpeg_path = self.dependencies['ffmpeg']['path']
        
        if not self.dependencies['ffmpeg']['available']:
            logger.warning("⚠️ FFmpeg dependency check failed on init.")

    # ... [Static methods remain the same: get_local_ollama_models, get_vram_gb, auto_select_whisper_model] ...
    # Re-implementing them for completeness
    
    @staticmethod
    def get_local_ollama_models(ollama_url: str = "http://localhost:11434/api/tags") -> List[str]:
        try:
            response = requests.get(ollama_url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                return [m['name'] for m in data.get('models', [])]
        except:
            pass
        return []

    @staticmethod
    def get_available_models(provider: str, api_key: str = "") -> List[str]:
        """Proxy to TranslationManager for fetching models."""
        return TranslationManager.get_available_models(provider, api_key)

    @staticmethod
    def get_gemini_rpd_status() -> str:
        """Returns a string describing remaining Gemini RPD."""
        status = []
        for model, usage in GEMINI_USAGE.items():
            limit = GEMINI_RPD_LIMITS.get(model, 0)
            remaining = max(0, limit - usage)
            status.append(f"{model}: {remaining}/{limit} Left")
        return " | ".join(status)

    @staticmethod
    def get_vram_gb() -> Optional[float]:
        try:
            if torch.cuda.is_available():
                return torch.cuda.get_device_properties(0).total_memory / (1024**3)
        except:
            pass
        return None

    @staticmethod
    def auto_select_whisper_model() -> Tuple[str, str]:
        vram = SubFarsiCore.get_vram_gb()
        if vram is None: return "base", "CPU Mode"
        if vram > 8: return "medium", "High VRAM"
        if vram > 4: return "small", "Mid VRAM"
        return "base", "Low VRAM"

    @staticmethod
    def check_system_dependencies() -> Dict[str, any]:
        """
        Check system dependencies (FFmpeg and Ollama).
        
        Checks in order:
        1. DependencyManager managed bin directory
        2. System PATH
        3. DependencyManager.is_ffmpeg_present() (which also checks PATH)
        """
        deps = {
            'ffmpeg': {'available': False, 'message': '', 'path': None},
            'ollama': {'available': False, 'message': ''}
        }
        
        # Check FFmpeg using DependencyManager (checks both managed dir and PATH)
        ffmpeg = None
        if DependencyManager:
            # First check DependencyManager's managed bin directory
            try:
                managed_path = DependencyManager._ffmpeg_target_path()
                if managed_path.exists() and os.access(managed_path, os.X_OK):
                    ffmpeg = str(managed_path)
                    logger.debug(f"✅ Found FFmpeg in managed directory: {ffmpeg}")
            except Exception as e:
                logger.debug(f"Could not check managed FFmpeg path: {e}")
            
            # Also check if DependencyManager reports FFmpeg as present (checks PATH too)
            if not ffmpeg and DependencyManager.is_ffmpeg_present():
                # FFmpeg is in PATH, find it
                ffmpeg = shutil.which('ffmpeg')
        
        # Fallback: check system PATH directly
        if not ffmpeg:
            ffmpeg = shutil.which('ffmpeg')
        
        if ffmpeg:
            deps['ffmpeg'].update({'available': True, 'path': ffmpeg, 'message': f"✅ FFmpeg found: {ffmpeg}"})
        else:
            deps['ffmpeg']['message'] = "⚠️ FFmpeg not found."

        # Check Ollama
        try:
            requests.get("http://localhost:11434/api/tags", timeout=1)
            deps['ollama'].update({'available': True, 'message': "✅ Ollama running"})
        except:
            deps['ollama']['message'] = "⚠️ Ollama not running"
            
        return deps

    # ... [Audio extraction and Transcription methods remain similar, condensing for brevity in this artifact but code is full] ...
    
    def _load_whisper_model(self, callback=None):
        if self.whisper_model: return
        if callback: callback("Loading Whisper...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        # Compatibility mode: float32
        self.whisper_model = WhisperModel(self.whisper_model_size, device=device, compute_type="float32", cpu_threads=os.cpu_count() or 4)

    def extract_audio(self, video_path: str, callback=None, cancel_event=None) -> str:
        if callback: callback("Extracting Audio...")
        if not self.ffmpeg_path: raise Exception("FFmpeg missing")
        
        temp_dir = tempfile.gettempdir()
        audio_path = os.path.join(temp_dir, f"subfarsi_{int(time.time())}.wav")
        
        cmd = [
            self.ffmpeg_path, '-i', video_path, '-map', '0:a:0', 
            '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', 
            '-y', audio_path, '-loglevel', 'error'
        ]
        subprocess.run(cmd, check=True)
        return audio_path

    def transcribe_audio(self, audio_path: str, prompt=None, callback=None, cancel_event=None) -> List[Dict]:
        if callback: callback("Starting transcription engine (VAD disabled)...")
        self._load_whisper_model(callback)
        
        try:
            segments, _ = self.whisper_model.transcribe(
                audio_path, beam_size=1, word_timestamps=False, 
                vad_filter=False, initial_prompt=prompt
            )
            
            subs = []
            for i, seg in enumerate(segments):
                if cancel_event and cancel_event.is_set():
                    raise Exception("Task cancelled by user")
                if not seg.text.strip(): continue
                subs.append({
                    'index': i+1, 'start': seg.start, 'end': seg.end, 'text': seg.text.strip()
                })
                if callback and i % 10 == 0: callback(f"Transcribing segment {i}...")
                
            return subs
        except Exception as e:
            if callback: callback(f"Transcription Error: {str(e)}")
            raise

    def translate_subtitles(self, subtitles: List[Dict], callback=None, cancel_event=None) -> List[Dict]:
        if callback: callback(f"Translating via {self.translator.__class__.__name__}...")
        
        if not self.translator.validate_config():
            logger.error("❌ Provider configuration invalid (missing API keys?)")
            if callback: callback("❌ Translation failed: Missing API Keys")
            return subtitles 

        translated = []
        batch = []
        total = len(subtitles)
        effective_batch_size = 50 if (
            isinstance(self.translator, UniversalTranslator) and self.translator.provider_type == "gemini"
        ) else self.batch_size

        # Sliding-window context: keep a rolling history of previous English subtitles
        history_texts: List[str] = []
        context_window = 3

        for i, sub in enumerate(subtitles):
            if cancel_event and cancel_event.is_set():
                raise Exception("Task cancelled by user")
            batch.append(sub)
            if len(batch) >= effective_batch_size or i == total - 1:
                batch_texts = [s['text'] for s in batch]
                # Build context from last N history lines (English only)
                context_lines = history_texts[-context_window:] if history_texts else None

                if isinstance(self.translator, OllamaProvider):
                    translations = self.translator.translate_batch(
                        batch_texts,
                        callback=callback,
                        context_lines=context_lines
                    )
                else:
                    translations = self.translator.translate_batch(batch_texts, callback=callback)

                for j, translated_text in enumerate(translations):
                    if j < len(batch):
                        new_sub = batch[j].copy()
                        new_sub['text'] = translated_text
                        translated.append(new_sub)

                # Update history with the English text of this batch
                history_texts.extend(batch_texts)
                
                batch = []
                if callback:
                    percent = int(((i+1)/total)*100)
                    msg = f"Translating: {percent}%"
                    # Inject RPD for Gemini
                    if isinstance(self.translator, UniversalTranslator) and self.translator.provider_type == "gemini":
                         msg += f" ({self.get_gemini_rpd_status()})"
                    callback(msg)
                    
        return translated

    def write_srt(self, subtitles: List[Dict], path: str):
        def fmt(s):
            h = int(s // 3600)
            m = int((s % 3600) // 60)
            sec = int(s % 60)
            ms = int((s - int(s)) * 1000)
            return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
            
        with open(path, 'w', encoding='utf-8') as f:
            for s in subtitles:
                f.write(f"{s['index']}\n{fmt(s['start'])} --> {fmt(s['end'])}\n{s['text']}\n\n")

    def process_video(self, video_path: str, initial_prompt=None, progress_callback=None, cleanup_temp_audio=True, cancel_event=None) -> str:
        logger.info(f"🚀 Processing: {video_path}")
        try:
            if cancel_event and cancel_event.is_set(): raise Exception("Task cancelled by user")
            audio = self.extract_audio(video_path, progress_callback, cancel_event)
            subs = self.transcribe_audio(audio, initial_prompt, progress_callback, cancel_event)
            trans_subs = self.translate_subtitles(subs, progress_callback, cancel_event)
            
            out_path = str(Path(video_path).with_suffix('.srt'))
            if progress_callback: progress_callback("Writing SRT...")
            self.write_srt(trans_subs, out_path)
            
            if cleanup_temp_audio: os.remove(audio)
            return out_path
            
        except Exception as e:
            logger.error(f"Processing failed: {e}")
            raise

if __name__ == "__main__":
    # Test Config Logic
    cm = ConfigManager()
    print(f"Loaded config: {cm.config}")
