"""Over-the-air update utilities."""
import os
import subprocess
import sys
from importlib import metadata
from typing import Optional


def in_virtual_env() -> bool:
    """Detect venvs (venv/virtualenv), pipx venvs, and conda envs."""
    # venv/virtualenv
    if getattr(sys, "real_prefix", None):  # virtualenv sets this
        return True
    if sys.prefix != getattr(sys, "base_prefix", sys.prefix):  # python -m venv
        return True
    # conda
    if os.environ.get("CONDA_PREFIX"):
        return True
    # pipx typically sets these and runs inside a venv too
    if os.environ.get("PIPX_BIN_DIR") or os.environ.get("PIPX_HOME"):
        return True
    # fallback: VIRTUAL_ENV env var
    return bool(os.environ.get("VIRTUAL_ENV"))


def _dist_for_import_name(import_name: str) -> str:
    """Map a top-level import name (module) to its distribution name for pip.

    Falls back to the import name if we can't find a better match.
    """
    try:
        # e.g. {"requests": ["requests"]} or {"Pillow": ["PIL"]}
        mapping = metadata.packages_distributions()
        top = import_name.split(".")[0]
        dists = mapping.get(top, [])
        return dists[0] if dists else top
    except Exception:
        return import_name.split(".")[0]


def self_update(
    import_name: str,
    version_spec: Optional[str] = None,
    allow_system: bool = False,
    pre: bool = False,
    index_url: Optional[str] = None,
    extra_index_url: Optional[str] = None,
) -> int:
    """Update the installed package that provides `import_name` using pip.

    Returns the pip exit code. Re-raises CalledProcessError on failure.

    - If not in a venv/conda and `allow_system` is False, install with --user.
    - Use `version_spec` (e.g., '==2.1.0' or '>=2.1,<3') to pin.
    - Set `pre=True` to allow pre-releases.
    """
    dist = _dist_for_import_name(import_name)
    requirement = dist + (version_spec or "")

    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", requirement, "--upgrade-strategy", "only-if-needed"]
    if pre:
        cmd.append("--pre")
    if index_url:
        cmd += ["--index-url", index_url]
    if extra_index_url:
        cmd += ["--extra-index-url", extra_index_url]

    if not in_virtual_env() and not allow_system:
        # Avoid modifying a global Python; prefer per-user install.
        cmd.append("--user")

    # On some locked-down images pip might be missing; ensurepip can help.
    try:
        return subprocess.call(cmd)
    except FileNotFoundError:
        # Try bootstrapping pip, then retry once.
        import ensurepip
        ensurepip.bootstrap()
        return subprocess.call(cmd)
