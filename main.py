import os, json, asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import anthropic

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY",""))

AGENTS = {
    "autopilot": {
        "name": "🚀 Autopilot", "color": "#00ff8c",
        "system": "You are Autopilot — a fully autonomous execution agent. Break the task into clear numbered steps and execute each one. Format: **STEP N:** description → **RESULT:** outcome. End with **COMPLETE:** final summary."
    },
    "planner": {
        "name": "📋 Planner", "color": "#4db8ff",
        "system": "You are the Planner agent. Produce detailed implementation plans with: **GOAL**, **BREAKDOWN** (numbered), **TECH STACK**, **TIMELINE**, **RISKS**, **FIRST STEP**."
    },
    "ralph": {
        "name": "🔄 Ralph (Persistent)", "color": "#ffd700",
        "system": "You are Ralph — persistent completion agent. Never give up. Show progress with [▓▓▓░░░] percentage. Handle every edge case. End with ✅ TASK COMPLETE."
    },
    "researcher": {
        "name": "🔍 Researcher", "color": "#ff6eb4",
        "system": "You are the Research agent. Provide structured research: **OVERVIEW**, **KEY FINDINGS**, **DETAILS**, **SOURCES TO CHECK**, **ACTION ITEMS**. Be thorough and actionable."
    },
    "coder": {
        "name": "💻 Coder", "color": "#c878ff",
        "system": "You are the Coder agent — expert software engineer. Write production-quality code with comments, error handling, and complete implementations. Output: **APPROACH**, **CODE**, **USAGE**, **NEXT STEPS**."
    },
    "eco": {
        "name": "⚡ Ecomode (Fast)", "color": "#ff9f43",
        "system": "You are Ecomode — optimized for speed. Give concise direct answers. Bullet points. No fluff. Maximum signal-to-noise ratio."
    },
}

ORCHESTRATOR = """Analyze the user's task and decide the best agent. Respond ONLY with valid JSON:
{"agent":"agent_name","mode":"single|parallel|sequential","reasoning":"why","task_refined":"refined task","parallel_agents":["a1","a2"]}
Agents: autopilot(full autonomous), planner(project planning), ralph(persistent completion), researcher(deep research), coder(write code), eco(fast/simple)
Use parallel for complex multi-part tasks. Use sequential for plan-then-execute. Use single for focused tasks."""

class Manager:
    def __init__(self): self.conns = {}
    async def connect(self, ws, cid): await ws.accept(); self.conns[cid] = ws
    def disconnect(self, cid): self.conns.pop(cid, None)
    async def send(self, cid, data):
        if cid in self.conns:
            try: await self.conns[cid].send_json(data)
            except: pass

mgr = Manager()

async def run_agent(key, task, cid, label=None):
    a = AGENTS[key]
    await mgr.send(cid, {"type":"agent_start","agent":key,"name":label or a["name"],"color":a["color"]})
    result = ""
    try:
        with client.messages.stream(model="claude-sonnet-4-6", max_tokens=2048,
                system=a["system"], messages=[{"role":"user","content":task}]) as s:
            for t in s.text_stream:
                result += t
                await mgr.send(cid, {"type":"token","agent":key,"text":t,"color":a["color"]})
    except Exception as e:
        await mgr.send(cid, {"type":"error","agent":key,"text":str(e)})
    await mgr.send(cid, {"type":"agent_done","agent":key})
    return result

async def orchestrate(task, cid):
    await mgr.send(cid, {"type":"orchestrating","text":"Analysing task..."})
    try:
        r = client.messages.create(model="claude-sonnet-4-6", max_tokens=512,
            system=ORCHESTRATOR, messages=[{"role":"user","content":task}])
        raw = r.content[0].text.strip().strip("```json").strip("```").strip()
        d = json.loads(raw)
    except:
        d = {"agent":"autopilot","mode":"single","reasoning":"fallback","task_refined":task}
    await mgr.send(cid, {"type":"decision","agent":d.get("agent","autopilot"),
        "mode":d.get("mode","single"),"reasoning":d.get("reasoning",""),
        "task_refined":d.get("task_refined",task)})
    mode, key, refined = d.get("mode","single"), d.get("agent","autopilot"), d.get("task_refined",task)
    if mode == "parallel":
        agents = d.get("parallel_agents",[key])[:3]
        await asyncio.gather(*[run_agent(a,refined,cid) for a in agents])
    elif mode == "sequential":
        plan = await run_agent("planner",refined,cid,"📋 Planning")
        await run_agent(key,f"Task: {refined}\n\nPlan:\n{plan}",cid,"⚡ Executing")
    else:
        await run_agent(key,refined,cid)
    await mgr.send(cid, {"type":"complete"})

@app.websocket("/ws/{cid}")
async def ws_endpoint(ws: WebSocket, cid: str):
    await mgr.connect(ws, cid)
    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "task":
                task = data.get("task","").strip()
                if not task: continue
                agent_override = data.get("agent")
                if agent_override and agent_override in AGENTS:
                    await run_agent(agent_override, task, cid)
                    await mgr.send(cid, {"type":"complete"})
                else:
                    await orchestrate(task, cid)
    except WebSocketDisconnect: mgr.disconnect(cid)
    except Exception as e:
        await mgr.send(cid, {"type":"error","text":str(e)})
        mgr.disconnect(cid)

@app.get("/agents")
def get_agents(): return {k:{"name":v["name"],"color":v["color"]} for k,v in AGENTS.items()}

@app.get("/health")
def health(): return {"status":"ok","agents":len(AGENTS)}

app.mount("/", StaticFiles(directory="static", html=True), name="static")
