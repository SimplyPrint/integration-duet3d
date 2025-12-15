"""Over-the-air update utilities."""
import asyncio
import logging
import os
import subprocess
import sys
import tempfile
from importlib import metadata
from typing import Optional, TYPE_CHECKING

import aiohttp

from simplyprint_duet3d.gcode import GCodeCommand

if TYPE_CHECKING:
    from simplyprint_duet3d.printer import DuetPrinter


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

    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        requirement,
        "--upgrade-strategy",
        "only-if-needed",
    ]
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


# External (optional) components that can be updated via OTA.
# Map of component name to shell command to install/update it.
SUPPORTED_COMPONENTS = {
    "ooo":
    "https://download.simplyprint.io/ooo/install.sh",
    "webcam":
    ("https://raw.githubusercontent.com/SimplyPrint/"
     "integration-duet3d/refs/heads/main/install-mjpeg-streamer.sh"),
}


async def _download_script(
    logger: logging.Logger,
    url: str,
    script_path: str,
) -> bool:
    """Download a script from a URL and save it to the specified path."""
    logger.info(f"Downloading installer from {url}...")
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                logger.error(
                    f"Download failed with HTTP Status: {response.status}",
                )
                return False

            content = await response.read()
            with open(script_path, 'wb') as f:
                f.write(content)

    os.chmod(script_path, 0o700)
    return True


async def _execute_script(
    logger: logging.Logger,
    script_path: str,
    component_name: str,
) -> bool:
    """Execute a script with sudo privileges and stream logs."""
    logger.info("Executing installer with sudo privileges...")

    process = await asyncio.create_subprocess_exec(
        "sudo",
        "bash",
        script_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    async def log_stream_reader(stream):
        while process.returncode is None:
            line = await stream.readline()
            if not line:
                break
            clean_line = line.decode('utf-8', errors='replace').strip()
            if clean_line:
                logger.info(f"[{component_name}] {clean_line}")

    try:
        await asyncio.wait_for(
            asyncio.gather(process.wait(), log_stream_reader(process.stdout)),
            timeout=300,
        )
    except asyncio.TimeoutError:
        logger.error("Update timed out after 300 seconds. Killing process.")
        try:
            process.kill()
            await process.wait()
        except ProcessLookupError:
            pass
        return False

    if process.returncode == 0:
        logger.info(f"Successfully updated {component_name}.")
        return True

    logger.error(
        f"Update failed. Script exited with code {process.returncode}.",
    )
    return False


async def update_external_component(
    logger: logging.Logger,
    component_name: str,
) -> bool:
    """
    Asynchronously download a script and execute it via sudo.

    Non-blocking network and process execution.
    """
    url = SUPPORTED_COMPONENTS.get(component_name)

    if not url:
        logger.error(
            f"Component '{component_name}' not defined in SUPPORTED_COMPONENTS.",
        )
        return False

    logger.info(f"Starting update process for component: {component_name}")

    fd, script_path = tempfile.mkstemp(suffix=".sh")
    os.close(fd)

    try:
        if not await _download_script(logger, url, script_path):
            return False
        return await _execute_script(logger, script_path, component_name)
    except aiohttp.ClientError as e:
        logger.error(f"Network error during download: {e}")
        return False
    except Exception as e:
        logger.exception(
            f"Unexpected error during update of {component_name}",
            exc_info=e,
        )
        return False
    finally:
        if os.path.exists(script_path):
            try:
                os.remove(script_path)
                logger.debug(f"Cleaned up temporary file: {script_path}")
            except OSError as e:
                logger.warning(f"Failed to remove temp file {script_path}: {e}")


async def process_m997_command(
    client: "DuetPrinter",
    command: GCodeCommand,
) -> bool:
    """Process an M997 GCode command for OTA component updates."""
    s_param = next(filter(lambda p: p.startswith("S"), command.parameters), None)
    if not s_param:
        client.logger.error("M997 command missing S parameter.")
        return False
    component_name = s_param[1:]  # Remove 'S' prefix
    component_name = component_name.strip('"').lower()

    if component_name == "self" or component_name == "simplyprint_duet3d":
        return await client.perform_self_upgrade()

    if component_name not in SUPPORTED_COMPONENTS:
        client.logger.error(f"Component '{component_name}' is not supported for OTA updates.")
        return False

    return await update_external_component(client.logger, component_name)
