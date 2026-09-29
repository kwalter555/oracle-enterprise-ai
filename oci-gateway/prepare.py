"""Patch the deployed GPT-only native adapter, not the older text-only version."""
import ast
import hashlib
from pathlib import Path

BASE_SHA256 = "7bfbdc1b11f77ead46e24d0150844ad4237a2b67640504fb399b8da7e3a799fb"
DOCKERFILE_SHA256 = "63551fb7c50e57223ac7f9b267cb4cb5f47d6933386101c306c5ca3ce4e12f23"
REQUIREMENTS_SHA256 = "02f5e586e28300fc2be472886fc0b66361a1a2cd3a228af19c233e1a41c69753"
MODELS = ("openai.gpt-oss-20b", "cohere.command-a-03-2025", "google.gemini-2.5-flash",
          "google.gemini-2.5-pro", "meta.llama-3.3-70b-instruct")
HERE = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def package_fingerprint():
    return digest(b"\n".join(p.name.encode() + b":" + digest(p.read_bytes()).encode()
                             for p in sorted(HERE.glob("*.py"))))


def candidate(source):
    if digest(source) != BASE_SHA256:
        raise ValueError("Unrecognized app.py version. Expected the active GPT-only native package.")
    text = source.decode()
    start = text.index('"""Inserted into app.py by prepare.py;')
    end = text.index('\ndef chat_call(body):', start)
    text = text[:start] + (HERE / 'native_support.py').read_text().rstrip() + '\n\n' + text[end:]
    ast.parse(text)
    return text.encode()


def packaged_app():
    expected = candidate((HERE / "baseline.py").read_bytes())
    if (HERE / "app.py").read_bytes() != expected:
        raise ValueError("app.py does not match the verified all-model patch.")
    return expected
