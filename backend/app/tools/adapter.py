"""Shell-free, resource-bounded external tool execution."""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class ToolUnavailableError(RuntimeError):
    pass


class ToolExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ToolResult:
    executable: str
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def display_command(self) -> str:
        # Display only. Execution always uses create_subprocess_exec and never
        # feeds this string to a command shell.
        return subprocess.list2cmdline([self.executable, *self.args])


def resolve_executable(configured: str) -> str:
    candidate = configured.strip()
    if not candidate or "\x00" in candidate:
        raise ToolUnavailableError("External tool executable is not configured safely.")
    if Path(candidate).is_absolute():
        if not Path(candidate).is_file():
            raise ToolUnavailableError(f"Configured executable does not exist: {candidate}")
        return str(Path(candidate).resolve())
    resolved = shutil.which(candidate)
    if not resolved:
        raise ToolUnavailableError(f"'{candidate}' was not found on PATH.")
    return resolved


async def _read_limited(stream: asyncio.StreamReader, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await stream.read(65536)
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > limit:
            raise ToolExecutionError(f"External tool output exceeded the {limit}-byte safety limit.")
        chunks.append(chunk)


async def _write_input(stream: asyncio.StreamWriter, data: bytes) -> None:
    stream.write(data)
    await stream.drain()
    stream.close()
    await stream.wait_closed()


async def run_tool(
    executable: str,
    args: list[str],
    *,
    timeout_seconds: int,
    max_output_bytes: int,
    input_text: str | None = None,
    max_input_bytes: int = 5 * 1024 * 1024,
) -> ToolResult:
    resolved = resolve_executable(executable)
    if any("\x00" in arg for arg in args):
        raise ToolExecutionError("External tool argument contains a null byte.")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    input_data = input_text.encode("utf-8") if input_text is not None else None
    if input_data is not None and len(input_data) > max_input_bytes:
        raise ToolExecutionError(f"External tool input exceeded the {max_input_bytes}-byte safety limit.")
    process = await asyncio.create_subprocess_exec(
        resolved, *args,
        stdin=asyncio.subprocess.PIPE if input_data is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        creationflags=creationflags,
    )
    try:
        operations = [
            _read_limited(process.stdout, max_output_bytes),
            _read_limited(process.stderr, min(max_output_bytes, 1024 * 1024)),
        ]
        if input_data is not None:
            operations.append(_write_input(process.stdin, input_data))
        results = await asyncio.wait_for(
            asyncio.gather(*operations),
            timeout=timeout_seconds,
        )
        stdout, stderr = results[0], results[1]
        returncode = await process.wait()
    except TimeoutError as exc:
        process.kill(); await process.wait()
        raise ToolExecutionError(f"External tool timed out after {timeout_seconds} seconds.") from exc
    except Exception:
        if process.returncode is None:
            process.kill(); await process.wait()
        raise
    return ToolResult(
        executable=resolved, args=tuple(args), returncode=returncode,
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
    )


async def detect_version(executable: str) -> str | None:
    try:
        result = await run_tool(executable, ["-version"], timeout_seconds=10, max_output_bytes=64 * 1024)
    except (ToolUnavailableError, ToolExecutionError):
        return None
    text = (result.stdout or result.stderr).strip()
    return text.splitlines()[0][:200] if text else None
