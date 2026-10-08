from uuid import uuid4
from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from .models import TravelRequest, ReviewRequest
from .workflow import start_plan, resume_plan, snapshot
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(title="AI Travel Planner", version="1.0.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", include_in_schema=False)
def home():
    return FileResponse("app/templates/index.html")

def view(plan_id: str):
    try: snap = snapshot(plan_id)
    except Exception: raise HTTPException(404, "Plan not found")
    values = snap.values or {}
    if not values: raise HTTPException(404, "Plan not found")
    interrupted = bool(snap.interrupts)
    return {"plan_id": plan_id, "status": values.get("status"), "workflow_paused": interrupted, "draft": values.get("draft"), "revision_count": values.get("revision_count",0)}

@app.get("/health")
def health(): return {"status": "ok"}

@app.post("/plan", status_code=201)
def create_plan(req: TravelRequest):
    plan_id = str(uuid4())
    start_plan(plan_id, req.model_dump())
    return view(plan_id)

@app.get("/plan/{plan_id}")
def get_plan(plan_id: str): return view(plan_id)

@app.post("/plan/{plan_id}/review")
def review_plan(plan_id: str, review: ReviewRequest):
    current = view(plan_id)
    if not current["workflow_paused"]: raise HTTPException(409, "Plan is not awaiting review")
    resume_plan(plan_id, review.model_dump(exclude_none=True))
    return view(plan_id)

@app.get("/plan/{plan_id}/final")
def final_plan(plan_id: str):
    snap = snapshot(plan_id); values = snap.values or {}
    if values.get("status") != "approved" or not values.get("final"):
        raise HTTPException(409, "Final plan is available only after approval")
    return jsonable_encoder({"plan_id": plan_id, "plan": values["final"]})
