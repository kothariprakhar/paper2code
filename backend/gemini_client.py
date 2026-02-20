"""Gemini API wrapper for all LLM calls in the Paper2Code pipeline."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import textwrap

import google.generativeai as genai

logger = logging.getLogger(__name__)

_configured = False


def _ensure_configured():
    global _configured
    if not _configured:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable is not set.")
        genai.configure(api_key=api_key)
        _configured = True


def _model():
    _ensure_configured()
    return genai.GenerativeModel("gemini-2.0-flash")


_MAX_RETRIES = 5
_BASE_DELAY = 15  # seconds


async def _call_with_retry(prompt: str) -> str:
    """Call the Gemini API with automatic retry + exponential backoff on 429."""
    model = _model()
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = await model.generate_content_async(prompt)
            return resp.text.strip()
        except Exception as exc:
            err_str = str(exc)
            is_rate_limit = "429" in err_str or "Resource" in err_str
            if not is_rate_limit or attempt == _MAX_RETRIES:
                raise

            # Try to parse server-suggested delay
            delay = _BASE_DELAY * (2 ** (attempt - 1))
            import re as _re
            m = _re.search(r'retry.*?(\d+(?:\.\d+)?)\s*s', err_str, _re.IGNORECASE)
            if m:
                delay = max(delay, float(m.group(1)))

            logger.warning(
                "Gemini rate-limited (attempt %d/%d). Retrying in %.0fs…",
                attempt, _MAX_RETRIES, delay,
            )
            await asyncio.sleep(delay)

    # Should never reach here, but just in case
    raise RuntimeError("Gemini API retries exhausted.")


def _strip_fences(text: str, lang: str = "") -> str:
    """Remove markdown code fences if present."""
    pattern = rf"```{lang}\s*\n?(.*?)```"
    m = re.search(pattern, text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # also try generic fences
    m = re.search(r"```\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


# ── Public API ───────────────────────────────────────────────────────────────

async def parse_paper(paper_input: str) -> str:
    """Extract structured information from an arXiv URL or free-text description.

    Returns a markdown summary with: title, authors, abstract, key contributions,
    model architecture overview, dataset, and evaluation metrics.
    """
    prompt = textwrap.dedent(f"""\
        You are an expert ML research analyst.

        Given the following paper input (either an arXiv URL or a description),
        produce a structured summary in **Markdown** with these sections:
        - **Title**
        - **Authors** (if known)
        - **Abstract / Summary**
        - **Key Contributions** (bullet list)
        - **Model Architecture** (brief technical description)
        - **Dataset(s)**
        - **Evaluation Metrics**

        If the input is an arXiv URL, use your knowledge to fill in the details.
        If it is a free-text description, extract as much structure as possible.

        Paper input:
        {paper_input}
    """)
    return await _call_with_retry(prompt)


async def generate_architecture(paper_info: str, framework: str = "pytorch") -> str:
    """Generate a detailed architecture document for implementing the paper.

    Returns a markdown architecture doc with module descriptions, shapes, and
    a training loop outline.
    """
    prompt = textwrap.dedent(f"""\
        You are a senior ML engineer writing an architecture document for implementing
        the following paper. The implementation will use **{framework}**.

        Paper summary:
        {paper_info}

        Produce a detailed **Architecture Document** in Markdown covering:

        1. **Overview** — one-paragraph summary of the implementation approach
        2. **Module Breakdown** — each class/module with:
           - Name
           - Purpose
           - Key parameters
           - Input/output tensor shapes
        3. **Training Pipeline**
           - Data loading strategy
           - Loss function(s)
           - Optimizer & scheduler
           - Training loop pseudocode
        4. **Evaluation**
           - Metrics to compute
           - Visualization (plots, sample outputs)
        5. **File Structure** — suggested single-file layout with section markers

        Be specific about tensor shapes and layer configurations.
        Use realistic hyperparameter defaults.
    """)
    return await _call_with_retry(prompt)


async def generate_code(
    paper_info: str,
    architecture_doc: str,
    framework: str = "pytorch",
) -> str:
    """Generate a complete, runnable Python implementation.

    Returns raw Python source code (no markdown fences).
    """
    prompt = textwrap.dedent(f"""\
        You are an expert ML engineer. Generate a **complete, runnable Python script**
        that implements the paper described below, following the architecture document
        precisely.

        **Requirements:**
        - Framework: {framework}
        - Must run end-to-end in a single file
        - Include all imports
        - Include data loading (use torchvision/tensorflow_datasets or synthetic data
          if the real dataset is not freely available)
        - Include model definition exactly as specified in the architecture doc
        - Include training loop (use a small number of epochs like 2-3 for demo)
        - Include evaluation and print metrics
        - Include a matplotlib visualization at the end (save to 'results.png')
        - Add clear section comments
        - Handle the case where CUDA is not available (fall back to CPU)
        - Print progress during training

        **Paper summary:**
        {paper_info}

        **Architecture document:**
        {architecture_doc}

        Return ONLY the Python code, no explanations or markdown.
    """)
    result = await _call_with_retry(prompt)
    return _strip_fences(result, "python")


async def refine_code(
    code: str,
    error: str,
    architecture_doc: str,
    framework: str = "pytorch",
) -> str:
    """Fix code based on execution errors while maintaining architecture adherence.

    Returns corrected Python source code (no markdown fences).
    """
    prompt = textwrap.dedent(f"""\
        You are an expert ML engineer debugging code.

        The following Python ({framework}) code produced an error when executed.
        Fix the code so it runs without errors. Maintain adherence to the architecture
        document. Return ONLY the fixed Python code, no explanations or markdown.

        **Error output (last 80 lines):**
        {error[-4000:]}

        **Current code:**
        ```python
        {code}
        ```

        **Architecture document:**
        {architecture_doc}
    """)
    result = await _call_with_retry(prompt)
    return _strip_fences(result, "python")


async def generate_readme(
    paper_info: str,
    architecture_doc: str,
    code: str,
    repo_name: str,
    github_username: str = "your-username",
) -> str:
    """Generate a professional GitHub README."""
    prompt = textwrap.dedent(f"""\
        Generate a **professional GitHub README.md** for this ML paper implementation.

        Repository: {github_username}/{repo_name}

        **Include these sections:**
        1. Title with a brief tagline
        2. Badges (Python 3.10+, License MIT, Open in Colab)
           - Colab badge URL: https://colab.research.google.com/github/{github_username}/{repo_name}/blob/main/notebook.ipynb
        3. Overview — what this project does, link to original paper
        4. Architecture — include a mermaid diagram of the model
        5. Quick Start — installation and usage instructions
        6. Results — placeholder table for metrics
        7. Project Structure — file tree
        8. Citation — BibTeX format
        9. License — MIT

        **Paper summary:**
        {paper_info}

        **Architecture document:**
        {architecture_doc}

        Return only the README markdown, nothing else.
    """)
    return await _call_with_retry(prompt)
