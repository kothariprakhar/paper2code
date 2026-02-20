"""Convert generated code + docs into a Jupyter notebook (.ipynb)."""

from __future__ import annotations

import json
import re
from typing import List, Set

import nbformat


def generate_notebook(
    paper_info: str,
    architecture_doc: str,
    code: str,
    repo_name: str,
    github_username: str = "your-username",
) -> str:
    """Build a .ipynb notebook and return it as a JSON string.

    Structure:
    1. Colab badge + title
    2. Paper summary (markdown)
    3. Architecture overview (markdown)
    4. pip install cell
    5. Code cells (split on section-comment markers)
    """
    nb = nbformat.v4.new_notebook()
    nb.metadata["colab"] = {"name": f"{repo_name}.ipynb"}
    nb.metadata["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }

    # ── Cell 1: Colab badge + title ──────────────────────────────────────
    colab_url = (
        f"https://colab.research.google.com/github/"
        f"{github_username}/{repo_name}/blob/main/notebook.ipynb"
    )
    badge = (
        f"[![Open In Colab](https://colab.research.google.com/assets/"
        f"colab-badge.svg)]({colab_url})"
    )
    nb.cells.append(
        nbformat.v4.new_markdown_cell(f"# {repo_name}\n\n{badge}")
    )

    # ── Cell 2: Paper info ───────────────────────────────────────────────
    nb.cells.append(
        nbformat.v4.new_markdown_cell(f"## Paper Summary\n\n{paper_info}")
    )

    # ── Cell 3: Architecture ─────────────────────────────────────────────
    nb.cells.append(
        nbformat.v4.new_markdown_cell(
            f"## Architecture\n\n{architecture_doc}"
        )
    )

    # ── Cell 4: Install dependencies ─────────────────────────────────────
    # Quick-parse imports to guess pip packages
    imports = _extract_pip_packages(code)
    if imports:
        install_line = "!pip install -q " + " ".join(sorted(imports))
        nb.cells.append(nbformat.v4.new_code_cell(install_line))

    # ── Cell 5: Colab runtime / GPU check ────────────────────────────────
    gpu_check = (
        "# ── Runtime check ──────────────────────────────────────────\n"
        "import torch\n"
        "device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')\n"
        "print(f'Using device: {device}')\n"
        "if device.type == 'cuda':\n"
        "    print(f'GPU: {torch.cuda.get_device_name(0)}')\n"
        "    print(f'Memory: {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB')\n"
        "else:\n"
        "    print('⚠️ No GPU detected. Go to Runtime > Change runtime type > GPU.')"
    )
    nb.cells.append(nbformat.v4.new_code_cell(gpu_check))

    # ── Cell 6: Matplotlib inline magic ──────────────────────────────────
    nb.cells.append(nbformat.v4.new_code_cell("%matplotlib inline"))

    # ── Cells 7+: Code split on section comments ────────────────────────
    sections = _split_code_sections(code)
    for section in sections:
        nb.cells.append(nbformat.v4.new_code_cell(section))

    return json.dumps(nbformat.writes(nb))  # double-encode for safe JSON storage


# ── Helpers ──────────────────────────────────────────────────────────────────

_COMMON_PACKAGES = {
    "torch": "torch",
    "torchvision": "torchvision",
    "tensorflow": "tensorflow",
    "keras": "keras",
    "numpy": "numpy",
    "matplotlib": "matplotlib",
    "sklearn": "scikit-learn",
    "scipy": "scipy",
    "pandas": "pandas",
    "tqdm": "tqdm",
    "PIL": "Pillow",
    "cv2": "opencv-python",
    "transformers": "transformers",
    "datasets": "datasets",
}


def _extract_pip_packages(code: str) -> Set[str]:
    """Guess pip packages from import statements."""
    pkgs: Set[str] = set()
    for line in code.splitlines():
        m = re.match(r"^\s*(?:import|from)\s+(\w+)", line)
        if m:
            mod = m.group(1)
            if mod in _COMMON_PACKAGES:
                pkgs.add(_COMMON_PACKAGES[mod])
    return pkgs


def _split_code_sections(code: str) -> List[str]:
    """Split code on section-comment markers like `# === Section ===` or `# --- Section ---`."""
    pattern = re.compile(r"^#\s*[=\-]{3,}.*$", re.MULTILINE)
    parts = pattern.split(code)
    headers = pattern.findall(code)

    sections: List[str] = []
    for i, part in enumerate(parts):
        stripped = part.strip()
        if not stripped:
            continue
        if i > 0 and i - 1 < len(headers):
            stripped = headers[i - 1].strip() + "\n" + stripped
        sections.append(stripped)

    return sections if sections else [code]
