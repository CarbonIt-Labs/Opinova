import os
import json
import time
from typing import List, Dict, Any
import uvicorn
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# Initialize FastAPI
app = FastAPI(title="Opinova Backend")

# STRICT CORS - This is required so port 3000 (UI) can talk to port 8000 (Backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_data() -> List[Dict[str, Any]]:
    """Robustly find and load the JSON file, no matter where the script is run from."""
    paths_to_try = [
        "processed_results.json",
        "data/processed_results.json",
        "../processed_results.json",
        "../data/processed_results.json"
    ]
    
    for path in paths_to_try:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
            except Exception as e:
                print(f"Failed to read {path}: {e}")
                
    print("WARNING: processed_results.json not found anywhere!")
    return []

# ==========================================
#          EXACT ROUTE MATCHES              #
# ==========================================

@app.get("/api/v1/dashboard/kpi")
def get_kpi():
    clusters = load_data()
    if not clusters:
        return {
            "total_feedback": 0, "total_feedback_change": 0,
            "clusters": 0, "clusters_new": 0,
            "high_priority": 0, "high_priority_change": 0,
            "immediate_actions": 0, "immediate_actions_change": 0,
            "resolution_rate": 0, "resolution_rate_change": 0
        }

    total_feedback = sum([c.get('frequency', 1) for c in clusters])
    high_priority = len([c for c in clusters if c.get('priority_score', 0) >= 70])
    immediate = len([c for c in clusters if c.get('category') == "Immediate Action Required"])

    return {
        "total_feedback": total_feedback,
        "total_feedback_change": 14.5,
        "clusters": len(clusters),
        "clusters_new": 1,
        "high_priority": high_priority,
        "high_priority_change": 1,
        "immediate_actions": immediate,
        "immediate_actions_change": 0,
        "resolution_rate": 88,
        "resolution_rate_change": 4.2
    }

@app.get("/api/v1/dashboard/matrix")
def get_matrix():
    clusters = load_data()
    matrix_points = []
    
    for c in clusters:
        score = c.get('priority_score', 0)
        if score >= 85: sev = "critical"
        elif score >= 70: sev = "high"
        elif score >= 50: sev = "medium"
        else: sev = "low"

        matrix_points.append({
            "name": c.get("topic", "Unassigned Issue"),
            "x": c.get("urgency", 5) / 10.0,  # Scaled for 0.0-1.0 chart axis
            "y": c.get("impact", 5) / 10.0,   # Scaled for 0.0-1.0 chart axis
            "score": score,
            "severity": sev
        })
    return matrix_points

@app.get("/api/v1/dashboard/issues")
def get_issues():
    clusters = load_data()
    sorted_clusters = sorted(clusters, key=lambda x: x.get('priority_score', 0), reverse=True)
    
    issues_list = []
    for i, c in enumerate(sorted_clusters[:8]):
        issues_list.append({
            "rank": i + 1,
            "name": c.get("topic", "Unknown Cluster"),
            "category": c.get("issue_type", "General feedback"),
            "mentions": c.get("frequency", 1),
            "score": c.get("priority_score", 0)
        })
    return issues_list

@app.get("/api/v1/dashboard/sentiment")
def get_sentiment():
    return {"positive": 68, "neutral": 20, "negative": 12}

@app.get("/api/v1/dashboard/sentiment/trend")
def get_sentiment_trend():
    return [58, 60, 61, 59, 64, 66, 65, 68, 70, 72, 71, 73]

@app.get("/api/v1/dashboard/trend")
def get_trend():
    clusters = load_data()
    sample = clusters[:4]
    
    return {
        "labels": [c.get("topic", "Topic")[:15] for c in sample] if sample else ["No Data"],
        "positive": [int(c.get("frequency", 1) * 0.6) for c in sample] if sample else [0],
        "neutral": [int(c.get("frequency", 1) * 0.3) for c in sample] if sample else [0],
        "negative": [int(c.get("frequency", 1) * 0.1) for c in sample] if sample else [0],
    }

@app.get("/api/v1/dashboard/recommendations")
def get_recommendations():
    clusters = load_data()
    sorted_clusters = sorted(clusters, key=lambda x: x.get('priority_score', 0), reverse=True)
    
    recommendations = []
    for c in sorted_clusters[:3]:
        score = c.get('priority_score', 0)
        if score >= 85: sev = "critical"
        elif score >= 70: sev = "high"
        else: sev = "medium"

        recommendations.append({
            "title": f"Action Required: {c.get('topic')}",
            "text": c.get('recommended_action', 'Review this feedback manually.'),
            "priority": sev
        })
    return recommendations

# --- Dummy routes for UI buttons to prevent crashes ---

@app.post("/api/v1/upload")
async def upload_file(file: UploadFile = File(...)):
    time.sleep(1) # Simulate processing
    return {"status": "success", "message": "File parsed successfully"}

@app.post("/api/v1/dashboard/export")
def export_dashboard():
    os.makedirs("exports", exist_ok=True)
    file_path = "exports/Opinova_Report.txt"
    with open(file_path, "w") as f:
        f.write("Opinova Dashboard Export Data.")
    return {"status": "success", "download_url": "/api/v1/reports/download"}

@app.get("/api/v1/reports/download")
def download_report():
    file_path = "exports/Opinova_Report.txt"
    if os.path.exists(file_path):
         return FileResponse(file_path, filename="Opinova_Report.txt")
    return {"error": "File not found"}

# ==========================================
#          APP STARTUP LOGIC                #
# ==========================================
if __name__ == "__main__":
    print("Starting Opinova API Server on http://localhost:8000")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
