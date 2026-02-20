"""Core orchestration agent — runs the full Paper2Code pipeline."""

from __future__ import annotations

import asyncio
from typing import Callable, Optional

from models import ProgressEvent, RunDetail, RunStatus
from gemini_client import (
    generate_architecture,
    generate_code,
    generate_readme,
    parse_paper,
    refine_code,
)
from code_executor import run_code
from github_client import get_authenticated_username, push_to_github
from notebook_generator import generate_notebook


async def run_pipeline(
    run: RunDetail,
    on_progress: Optional[Callable[[ProgressEvent], None]] = None,
) -> RunDetail:
    """Execute the full paper → code → GitHub pipeline.

    Mutates `run` in place and returns it.  Calls `on_progress` at each step
    so the WebSocket layer can stream updates to the client.
    """

    def emit(status: RunStatus, message: str, iteration: int | None = None):
        run.status = status
        run.logs.append(message)
        if on_progress:
            evt = ProgressEvent(
                run_id=run.id,
                status=status,
                message=message,
                iteration=iteration,
            )
            on_progress(evt)

    try:
        # ── Step 1: Parse paper ──────────────────────────────────────────
        emit(RunStatus.PARSING_PAPER, "📄 Parsing paper and extracting key information…")
        run.paper_info = await parse_paper(run.paper_input)
        emit(RunStatus.PARSING_PAPER, "✅ Paper parsed successfully.")

        # ── Step 2: Generate architecture doc ────────────────────────────
        emit(
            RunStatus.GENERATING_ARCHITECTURE,
            "🏗️ Generating architecture document…",
        )
        run.architecture_doc = await generate_architecture(
            run.paper_info, run.framework
        )
        emit(RunStatus.GENERATING_ARCHITECTURE, "✅ Architecture document generated.")

        # ── Step 3: Generate initial code ────────────────────────────────
        emit(RunStatus.GENERATING_CODE, "💻 Generating initial implementation…")
        run.generated_code = await generate_code(
            run.paper_info, run.architecture_doc, run.framework
        )
        emit(RunStatus.GENERATING_CODE, "✅ Initial code generated.")

        # ── Step 4: Execute & refine loop ────────────────────────────────
        for i in range(1, run.max_iterations + 1):
            run.current_iteration = i
            emit(
                RunStatus.EXECUTING_CODE,
                f"▶️ Executing code (iteration {i}/{run.max_iterations})…",
                iteration=i,
            )

            result = await asyncio.to_thread(run_code, run.generated_code)

            if result.success:
                emit(
                    RunStatus.EXECUTING_CODE,
                    f"✅ Code executed successfully on iteration {i}!",
                    iteration=i,
                )
                if result.stdout:
                    emit(RunStatus.EXECUTING_CODE, f"📊 Output:\n{result.stdout[-2000:]}")
                break

            # Execution failed — refine
            error_text = result.stderr or result.stdout or "Unknown error"
            emit(
                RunStatus.REFINING_CODE,
                f"❌ Execution failed (iteration {i}). Error:\n{error_text[-1000:]}",
                iteration=i,
            )

            if i < run.max_iterations:
                emit(
                    RunStatus.REFINING_CODE,
                    f"🔄 Asking Gemini to fix the code…",
                    iteration=i,
                )
                run.generated_code = await refine_code(
                    run.generated_code,
                    error_text,
                    run.architecture_doc,
                    run.framework,
                )
                emit(
                    RunStatus.REFINING_CODE,
                    f"✅ Code refined. Retrying execution…",
                    iteration=i,
                )
            else:
                emit(
                    RunStatus.REFINING_CODE,
                    f"⚠️ Max iterations reached. Proceeding with last version.",
                    iteration=i,
                )

        # ── Step 5: Generate README ──────────────────────────────────────
        emit(RunStatus.GENERATING_README, "📝 Generating professional README…")
        try:
            github_username = get_authenticated_username()
        except Exception:
            github_username = "your-username"

        run.readme = await generate_readme(
            run.paper_info,
            run.architecture_doc,
            run.generated_code,
            run.repo_name,
            github_username,
        )
        emit(RunStatus.GENERATING_README, "✅ README generated.")

        # ── Step 6: Generate notebook ────────────────────────────────────
        emit(RunStatus.GENERATING_NOTEBOOK, "📓 Generating Jupyter notebook…")
        run.notebook_json = generate_notebook(
            run.paper_info,
            run.architecture_doc,
            run.generated_code,
            run.repo_name,
            github_username,
        )
        emit(RunStatus.GENERATING_NOTEBOOK, "✅ Notebook generated.")

        # ── Step 7: Push to GitHub ───────────────────────────────────────
        emit(RunStatus.PUSHING_TO_GITHUB, "🚀 Creating GitHub repository and pushing files…")

        import json
        notebook_content = json.loads(run.notebook_json)  # un-double-encode

        files = {
            "main.py": run.generated_code,
            "docs/architecture.md": run.architecture_doc,
            "README.md": run.readme,
            "notebook.ipynb": notebook_content,
        }

        run.github_url = push_to_github(
            repo_name=run.repo_name,
            files=files,
            description=f"ML paper implementation — generated by Paper2Code",
        )

        run.colab_url = (
            f"https://colab.research.google.com/github/"
            f"{github_username}/{run.repo_name}/blob/main/notebook.ipynb"
        )

        emit(RunStatus.PUSHING_TO_GITHUB, f"✅ Pushed to GitHub: {run.github_url}")
        emit(RunStatus.COMPLETED, "🎉 Pipeline completed successfully!")

    except Exception as e:
        run.error = str(e)
        emit(RunStatus.FAILED, f"💥 Pipeline failed: {e}")

    return run
