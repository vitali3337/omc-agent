# 🤖 OMC Agent — oh-my-claudecode lite

Multi-agent orchestration powered by Claude API. No subscription needed — works with your Anthropic API key.

## Agents
- 🚀 **Autopilot** — full autonomous step-by-step execution
- 📋 **Planner** — deep project planning and breakdown
- 🔄 **Ralph** — persistent mode, never gives up
- 🔍 **Researcher** — deep research and analysis
- 💻 **Coder** — production code writing
- ⚡ **Ecomode** — fast and token-efficient

## Deploy to Railway

1. Push this folder to GitHub
2. New project on Railway → Deploy from GitHub
3. Add environment variable: `ANTHROPIC_API_KEY=your_key`
4. Done! Access via Railway URL

## Run locally

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key
uvicorn main:app --reload --port 8000
# Open http://localhost:8000
```
