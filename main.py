import os
import cv2
import time
import base64
import json
import io
from fastapi import FastAPI, UploadFile, File, Form, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, List

from core.fusion_engine import FusionEngine

app = FastAPI(title="IIIT-B Contactless Access Control (Face + Proximity Fusion)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate Fusion Engine
engine = FusionEngine(data_dir="data")

# Mount static folder
os.makedirs("static", exist_ok=True)
os.makedirs("data/enrolled_faces", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# -------------------------------------------------------------
# Frontend Page Routes
# -------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = os.path.join("static", "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>IIIT-B Smart Campus Access Control Online</h1>"

@app.get("/admin", response_class=HTMLResponse)
async def serve_admin():
    admin_file = os.path.join("static", "admin.html")
    if os.path.exists(admin_file):
        with open(admin_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Admin Dashboard loading...</h1>"

# -------------------------------------------------------------
# Live Verification & Status APIs
# -------------------------------------------------------------

@app.get("/api/status")
async def get_system_status():
    """Returns complete real-time telemetry from CAM, WIFI, AUDIO, and MCU."""
    evaluation = engine.evaluate_access()
    return evaluation

class RecognizeFrameRequest(BaseModel):
    image_base64: Optional[str] = None
    scenario_override: Optional[str] = None

@app.post("/api/recognize_frame")
async def recognize_live_frame(req: RecognizeFrameRequest):
    """
    Receives an actual live camera frame from the browser webcam,
    runs YuNet deep face detection and SFace 128-d deep embedding matching,
    and returns full multi-modal fusion decision.
    """
    frame = None
    if req.image_base64:
        try:
            data = req.image_base64
            if "base64," in data:
                data = data.split("base64,")[1]
            img_bytes = base64.b64decode(data)
            import numpy as np
            nparr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception as e:
            print(f"[RECOGNIZE] Frame decode error: {e}")

    if req.scenario_override:
        engine.set_scenario_override(req.scenario_override)

    evaluation = engine.evaluate_access(frame=frame)

    # Debug logging
    cam_data = evaluation.get("components", {}).get("cam", {})
    print(f"[RECOGNIZE] Decision: {evaluation.get('decision')} | "
          f"Face: {cam_data.get('name')} | "
          f"Similarity: {cam_data.get('similarity')} | "
          f"Liveness: {cam_data.get('liveness')} | "
          f"is_live: {cam_data.get('is_live')} | "
          f"Breakdown: {cam_data.get('breakdown')}")

    return evaluation

@app.post("/api/scenario/{scenario_name}")
async def set_scenario(scenario_name: str):
    """
    Switches simulation test scenario:
    - NORMAL: Authorized user with phone at door (Door unlocks)
    - PHOTO_ATTACK: Photo presentation attack (Alarm)
    - WALK_BY: User walking in hallway at 3.5m (Lock remains secure)
    - STOLEN_PHONE: Authorized phone held by stranger (Alarm)
    - RESET: Clears scenario override
    """
    if scenario_name == "RESET":
        engine.set_scenario_override(None)
    else:
        engine.set_scenario_override(scenario_name)

    return {"status": "SUCCESS", "active_scenario": scenario_name}

@app.get("/api/logs")
async def get_logs():
    """Returns recent security access audit entries."""
    return {"logs": list(reversed(engine.audit_logs))}

@app.post("/api/manual_lock_action/{action}")
async def manual_lock_action(action: str):
    """Admin override to manually test MCU lock or alarm."""
    if action == "UNLOCK":
        state = engine.mcu.trigger_unlock(duration_sec=3.0)
    elif action == "ALARM":
        state = engine.mcu.trigger_alarm(duration_sec=2.0)
    else:
        engine.mcu._auto_relock()
        state = engine.mcu.get_status()
    return {"status": "ACK", "mcu_state": state}

# -------------------------------------------------------------
# Admin Dashboard APIs: Authorized Faces Database & Enrollment
# -------------------------------------------------------------

@app.get("/api/admin/users")
async def get_authorized_users():
    """Returns roster of authorized personnel in the database."""
    users_list = []
    for uid, udata in engine.vision.enrolled_users.items():
        users_list.append({
            "user_id": uid,
            "name": udata.get("name", "Unknown"),
            "role": udata.get("role", "Authorized Member"),
            "department": udata.get("department", "General Research"),
            "access_tier": udata.get("access_tier", "Standard Access"),
            "registered_phone": udata.get("registered_phone", "—"),
            "registered_mac": udata.get("registered_mac", "—"),
            "enrolled_at": udata.get("enrolled_at", "2026-09-01 09:00:00"),
            "photo_url": f"/api/user_photo/{uid}"
        })
    return {"users": users_list}

@app.get("/api/user_photo/{user_id}")
async def get_user_photo(user_id: str):
    """Serves the face portrait or generates a clean initials avatar."""
    photo_path = os.path.join("data", "enrolled_faces", f"{user_id}.jpg")
    if os.path.exists(photo_path):
        return FileResponse(photo_path, media_type="image/jpeg")

    # Generate initials avatar canvas
    import numpy as np
    canvas = np.zeros((160, 160, 3), dtype=np.uint8)
    
    # Palette based on hash of user_id
    colors = [(37, 99, 235), (22, 163, 74), (217, 119, 6), (147, 51, 234)]
    bg_color = colors[hash(user_id) % len(colors)]
    canvas[:] = bg_color

    # Initials
    name = engine.vision.enrolled_users.get(user_id, {}).get("name", user_id)
    initials = "".join([part[0] for part in name.split()[:2]]).upper() or "U"
    
    cv2.putText(canvas, initials, (40, 95), cv2.FONT_HERSHEY_SIMPLEX, 1.3, (255, 255, 255), 3)

    _, jpeg = cv2.imencode('.jpg', canvas)
    return Response(content=jpeg.tobytes(), media_type="image/jpeg")

class Base64EnrollRequest(BaseModel):
    user_id: Optional[str] = None
    name: str
    role: str
    department: str
    access_tier: str
    phone: str
    mac: str
    image_base64: str

@app.post("/api/admin/enroll_webcam")
async def enroll_from_webcam(req: Base64EnrollRequest):
    """Enrolls a new authorized person via live webcam capture (base64) using YuNet and SFace."""
    import numpy as np
    try:
        data = req.image_base64
        if "base64," in data:
            data = data.split("base64,")[1]
        img_bytes = base64.b64decode(data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return JSONResponse(status_code=400, content={"error": "Invalid camera image."})

        success, assigned_id = engine.vision.enroll_user(
            user_id=req.user_id,
            name=req.name,
            role=req.role,
            phone=req.phone,
            mac=req.mac,
            face_img=img,
            dept=req.department,
            tier=req.access_tier
        )

        if success:
            return {"status": "SUCCESS", "user_id": assigned_id, "name": req.name}
        else:
            return JSONResponse(status_code=400, content={"error": "Could not detect human face in photo."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/admin/enroll_upload")
async def enroll_from_upload(
    name: str = Form(...),
    role: str = Form(...),
    department: str = Form("Networking & AI Lab"),
    access_tier: str = Form("Standard Access"),
    phone: str = Form("Personal Device"),
    mac: str = Form("AA:BB:CC:DD:EE:FF"),
    photo: UploadFile = File(...),
    user_id: Optional[str] = Form(None)
):
    """Enrolls a new authorized person via image file upload using YuNet and SFace."""
    import numpy as np
    contents = await photo.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return JSONResponse(status_code=400, content={"error": "Failed to decode uploaded image file."})

    success, assigned_id = engine.vision.enroll_user(
        user_id=user_id,
        name=name,
        role=role,
        phone=phone,
        mac=mac,
        face_img=img,
        dept=department,
        tier=access_tier
    )

    if success:
        return {"status": "SUCCESS", "user_id": assigned_id, "name": name}
    else:
        return JSONResponse(status_code=400, content={"error": "Could not detect human face in uploaded photo."})

@app.delete("/api/admin/users/{user_id}")
async def delete_user(user_id: str):
    """Revokes and deletes an authorized person from the database."""
    if user_id in engine.vision.enrolled_users:
        del engine.vision.enrolled_users[user_id]
        engine.vision.save_enrolled_users()
        
        photo_path = os.path.join("data", "enrolled_faces", f"{user_id}.jpg")
        if os.path.exists(photo_path):
            try:
                os.remove(photo_path)
            except Exception:
                pass
        return {"status": "SUCCESS", "message": f"User {user_id} revoked."}
    return JSONResponse(status_code=404, content={"error": "User ID not found."})

@app.get("/api/admin/logs")
async def get_admin_logs():
    """Returns complete timestamped premises entry history."""
    return {"logs": list(reversed(engine.audit_logs))}

@app.post("/api/admin/clear_logs")
async def clear_logs():
    """Clears premises entry history."""
    engine.audit_logs = []
    engine._save_audit_logs()
    return {"status": "SUCCESS", "message": "Audit logs cleared."}

@app.get("/api/admin/export_logs_csv")
async def export_logs_csv():
    """Exports entry history as a downloadable CSV."""
    import csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Event ID", "Timestamp", "Person Name", "User ID", "Decision", "Composite Score", "Reason", "Action"])
    
    for log in engine.audit_logs:
        writer.writerow([
            log.get("id"),
            log.get("timestamp"),
            log.get("user_name"),
            log.get("user_id"),
            log.get("decision"),
            f"{int(log.get('composite_score', 0) * 100)}%",
            log.get("reason"),
            log.get("action_type")
        ])
    
    output.seek(0)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=premises_entry_logs_{int(time.time())}.csv"}
    )

# -------------------------------------------------------------
# MJPEG Video Streaming
# -------------------------------------------------------------

def generate_video_stream():
    """Generates continuous MJPEG stream with visual AI telemetry."""
    while True:
        if engine.vision.cap and engine.vision.cap.isOpened() and not engine.vision.simulated_mode:
            ret, frame = engine.vision.cap.read()
            if ret and frame is not None:
                processed, _ = engine.vision.process_frame(frame, engine.current_scenario_override)
            else:
                processed, _ = engine.vision.generate_synthetic_feed(engine.current_scenario_override or "NORMAL")
        else:
            processed, _ = engine.vision.generate_synthetic_feed(engine.current_scenario_override or "NORMAL")

        ret, jpeg = cv2.imencode('.jpg', processed)
        if not ret:
            time.sleep(0.05)
            continue

        frame_bytes = jpeg.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.04)

@app.get("/api/stream")
def video_feed():
    """MJPEG stream endpoint for real-time camera display."""
    return StreamingResponse(generate_video_stream(), media_type="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
