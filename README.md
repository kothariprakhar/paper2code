# Paper2Code ⚡

> Transform ML research papers into complete, runnable implementations with AI.

Paper2Code is an agentic web application that takes an arXiv paper URL (or description), generates a full implementation using Gemini 2.0 Flash, iteratively debugs it, and pushes everything to GitHub — complete with a professional README and a Colab-ready notebook.

## Features

- 🧠 **AI-Powered Code Generation** — Uses Gemini 2.0 Flash to generate complete ML paper implementations
- 🏗️ **Architecture-First Approach** — Generates a detailed architecture document before writing code
- 🔄 **Iterative Refinement** — Automatically runs code, catches errors, and asks the LLM to fix them (up to N iterations)
- 📓 **Notebook Generation** — Converts code to a Jupyter notebook with "Open in Colab" badge
- 🚀 **GitHub Integration** — Creates a repo, pushes code, architecture doc, README, and notebook
- ⚡ **Real-Time Progress** — WebSocket streaming shows every pipeline step live in the browser

## Quick Start

### 1. Set API Keys

```bash
export GEMINI_API_KEY="your-gemini-api-key"    # from https://aistudio.google.com/apikey
export GITHUB_TOKEN="your-github-pat-token"     # from https://github.com/settings/tokens
```

### 2. Install Backend

```bash
cd backend
pip install -r requirements.txt
```

### 3. Start Backend

```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```

### 4. Open Frontend

Open `frontend/index.html` in your browser, or serve it:

```bash
cd frontend
python -m http.server 3000
```

Then visit [http://localhost:3000](http://localhost:3000).

## Architecture

```
paper2code/
├── backend/
│   ├── main.py                # FastAPI server + WebSocket
│   ├── agent.py               # Pipeline orchestrator
│   ├── gemini_client.py       # Gemini API wrapper
│   ├── code_executor.py       # Safe subprocess execution
│   ├── github_client.py       # GitHub repo creation + push
│   ├── notebook_generator.py  # .ipynb generation
│   ├── models.py              # Pydantic schemas
│   └── requirements.txt
├── frontend/
│   ├── index.html             # Single-page app shell
│   ├── styles.css             # Premium dark theme
│   └── app.js                 # Client-side logic
└── README.md
```

## Pipeline

1. **Parse Paper** — Extract title, methods, architecture from arXiv URL or description
2. **Architecture Doc** — Generate a detailed implementation blueprint
3. **Generate Code** — Write complete Python implementation
4. **Execute & Refine** — Run code, capture errors, fix iteratively
5. **Generate README** — Professional GitHub README with badges
6. **Generate Notebook** — .ipynb with Colab badge
7. **Push to GitHub** — Create repo and commit everything

## License

MIT
