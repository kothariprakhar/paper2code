"""Execute generated Python code in a sandboxed subprocess."""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    success: bool
    stdout: str
    stderr: str
    return_code: int
    timeout: bool = False


def run_code(code: str, timeout: int = 120) -> ExecutionResult:
    """Run a Python script in a temporary directory and return the results.

    Creates a temp directory, writes the code to `main.py`, and executes it
    with the current Python interpreter. Captures stdout and stderr.
    """
    with tempfile.TemporaryDirectory(prefix="paper2code_") as tmpdir:
        script_path = os.path.join(tmpdir, "main.py")
        with open(script_path, "w") as f:
            f.write(code)

        try:
            proc = subprocess.run(
                ["python", script_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir,
                env={**os.environ, "MPLBACKEND": "Agg"},  # non-interactive matplotlib
            )
            return ExecutionResult(
                success=proc.returncode == 0,
                stdout=proc.stdout,
                stderr=proc.stderr,
                return_code=proc.returncode,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Execution timed out after {timeout} seconds.",
                return_code=-1,
                timeout=True,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                return_code=-1,
            )
