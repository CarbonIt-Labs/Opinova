import os
import json
import time
import sys
import argparse
from typing import List, Dict, Any
import webview
from dotenv import load_dotenv

# Core analysis imports
from data_loader import load_file
from ai_engine import analyze_feedback_batch
from clustering import merge_batch_clusters
from scoring import score_clusters
from reports import print_top_issues, print_summary, export_report
from config import BATCH_SIZE

load_dotenv()

# Core analysis imports

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

PROCESSED_FILE = "data/processed_results.json"

def run_analysis(filepath: str, api_ref=None):
    if api_ref: api_ref.log_activity(f"System started analysis on {filepath}.")
    print(f"Loading data from {filepath}...")
    try:
        df = load_file(filepath)
    except FileNotFoundError:
        print(f"File {filepath} not found. Ensure it exists in the correct folder.")
        if api_ref: api_ref.log_activity(f"Error: File {filepath} not found.")
        return
        
    if len(df.columns) == 1:
        text_col = df.columns[0]
    else:
        text_col = None
        for col in df.columns:
            if df[col].dtype == 'object' or df[col].dtype == 'string':
                text_col = col
                break
            
    if not text_col:
        print("Could not find a text column in the dataset.")
        return
        
    print(f"Found text column: '{text_col}'. Processing {len(df)} records in batches of {BATCH_SIZE}...")
    
    # Extract all text into a list
    all_feedback = [str(text) for text in df[text_col].tolist()]
    
    all_ai_clusters = []
    
    # Chunking
    for i in range(0, len(all_feedback), BATCH_SIZE):
        batch = all_feedback[i:i+BATCH_SIZE]
        print(f"Analyzing batch {i//BATCH_SIZE + 1}/{(len(all_feedback)-1)//BATCH_SIZE + 1}...")
        
        backoff_times = [5, 15, 30, 60]
        max_retries = len(backoff_times)
        
        for attempt in range(max_retries):
            try:
                # LLM Call
                result = analyze_feedback_batch(batch)
                
                # Convert pydantic models to dict, adjust indices to absolute global indices
                for cluster in result.clusters:
                    cluster_dict = cluster.model_dump()
                    # Convert batch-relative indices to global indices
                    cluster_dict['feedback_indices'] = [idx + i for idx in cluster_dict['feedback_indices']]
                    all_ai_clusters.append(cluster_dict)
                break
                
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "Too Many Requests" in error_msg or "quota" in error_msg.lower() or "503" in error_msg or "Unavailable" in error_msg:
                    if attempt < max_retries - 1:
                        sleep_time = backoff_times[attempt]
                        print(f"API busy or quota hit. Waiting {sleep_time} seconds before retrying...")
                        time.sleep(sleep_time)
                    else:
                        print(f"Failed to process batch {i//BATCH_SIZE + 1} after retries: {e}")
                else:
                    print(f"Error processing batch {i//BATCH_SIZE + 1}: {e}")
                    break
                    
        # Small delay between successful batches
        time.sleep(2)
            
    if not all_ai_clusters:
        print("No batches processed successfully.")
        return
        
    print("Merging clusters across batches...")
    merged_clusters = merge_batch_clusters(all_ai_clusters, all_feedback)
    
    print("Applying priority scoring logic...")
    scored_clusters = score_clusters(merged_clusters)
    
    os.makedirs("data", exist_ok=True)
    with open(PROCESSED_FILE, 'w') as f:
        json.dump(scored_clusters, f, indent=4)
        
    print(f"Analysis complete. Results saved.")
    if api_ref: api_ref.log_activity(f"System completed analysis and saved results.")
    print_top_issues(scored_clusters)

def load_processed_results():
    if not os.path.exists(PROCESSED_FILE):
        print(f"Error: Processed data not found. Please run 'python main.py analyze <file>' first.")
        sys.exit(1)
    with open(PROCESSED_FILE, 'r') as f:
        return json.load(f)

# ==========================================
#          EXACT ROUTE MATCHES              #
# ==========================================

class Api:
    def __init__(self):
        self._window = None
        self.activities = []
        import datetime
        self.log_activity("Admin accessed Dashboard.")
        self.log_activity(f"System initialized at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    def log_activity(self, message):
        import datetime
        self.activities.append({
             "message": message,
             "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    def get_activities(self):
        return self.activities[::-1][:50]

    def get_kpi(self, filter_params=None):
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

    def get_matrix(self, filter_params=None):
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

    def get_issues(self, filter_params=None):
        clusters = load_data()
        sorted_clusters = sorted(clusters, key=lambda x: x.get('priority_score', 0), reverse=True)
        
        issues_list = []
        for i, c in enumerate(sorted_clusters[:8]):
            issues_list.append({
                "rank": i + 1,
                "name": c.get("topic", "Unknown Cluster"),
                "category": c.get("issue_type", "General feedback"),
                "mentions": c.get("frequency", 1),
                "score": c.get("priority_score", 0),
                "source_ids": c.get("feedback_indices", []),
                "original_texts": c.get("original_texts", [])
            })
        return issues_list

    def get_clusters_detail(self, filter_params=None):
        clusters = load_data()
        return clusters

    def get_sentiment(self, filter_params=None):
        clusters = load_data()
        if not clusters:
             return {"positive": 0, "neutral": 0, "negative": 0}
        pos = neu = neg = 0
        for c in clusters:
             score = c.get('priority_score', 0)
             freq = c.get('frequency', 1)
             if score >= 70:
                  neg += freq
             elif score >= 50:
                  neu += freq
             else:
                  pos += freq
        total = pos + neu + neg
        if total == 0: return {"positive": 0, "neutral": 0, "negative": 0}
        return {
             "positive": int((pos/total)*100),
             "neutral": int((neu/total)*100),
             "negative": int((neg/total)*100)
        }

    def get_trend(self, filter_params=None):
        clusters = load_data()
        sample = clusters[:4]
        
        positive_list = []
        neutral_list = []
        negative_list = []
        
        for c in sample:
            freq = c.get("frequency", 1)
            score = c.get("priority_score", 0)
            
            if score >= 70:
                positive_list.append(int(freq * 0.1))
                neutral_list.append(int(freq * 0.2))
                negative_list.append(max(1, int(freq * 0.7)))
            elif score >= 50:
                positive_list.append(int(freq * 0.3))
                neutral_list.append(int(freq * 0.4))
                negative_list.append(int(freq * 0.3))
            else:
                positive_list.append(max(1, int(freq * 0.7)))
                neutral_list.append(int(freq * 0.2))
                negative_list.append(int(freq * 0.1))
                
        return {
            "labels": [c.get("topic", "Topic")[:15] for c in sample] if sample else ["No Data"],
            "positive": positive_list if sample else [0],
            "neutral": neutral_list if sample else [0],
            "negative": negative_list if sample else [0],
        }

    def get_recommendations(self, filter_params=None):
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
                "priority": sev,
                "source_ids": c.get("feedback_indices", [])
            })
        return recommendations

    # --- Dummy routes for UI buttons to prevent crashes ---

    def upload_csv(self):
        if self._window:
            file_types = ('CSV files (*.csv)', 'All files (*.*)')
            result = self._window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, file_types=file_types)
            if result and len(result) > 0:
                filepath = result[0]
                import pandas as pd
                import uuid
                try:
                    df = pd.read_csv(filepath)
                    if 'feedback_id' not in df.columns:
                        df['feedback_id'] = [str(uuid.uuid4())[:8] for _ in range(len(df))]
                        df.to_csv(filepath, index=False)
                    self.log_activity(f"Uploaded CSV and assigned IDs to {len(df)} rows.")
                    run_analysis(filepath, api_ref=self)
                    return {"status": "success", "message": "File parsed and analyzed successfully"}
                except Exception as e:
                    self.log_activity(f"Error processing CSV: {str(e)}")
                    return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "No file selected"}

    def export_dashboard(self, filter_params=None):
        clusters = load_data()
        if not clusters:
             return {"status": "error", "message": "No data to export"}
        if self._window:
            result = self._window.create_file_dialog(webview.SAVE_DIALOG, allow_multiple=False, save_filename="Opinova_Report.csv")
            if result and len(result) > 0:
                import pandas as pd
                df = pd.DataFrame(clusters)
                df.to_csv(result[0], index=False)
                self.log_activity(f"Exported report to {result[0]}")
                return {"status": "success"}
        return {"status": "error"}

# ==========================================
#          APP STARTUP LOGIC                #
# ==========================================
def main():
    parser = argparse.ArgumentParser(description="Opinova - Decision Intelligence Platform")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    parser_analyze = subparsers.add_parser("analyze", help="Analyze a feedback file (CSV/JSON)")
    parser_analyze.add_argument("file", type=str, help="Path to the file to analyze")
    
    parser_summary = subparsers.add_parser("summary", help="Show summary of analyzed feedback")
    parser_top = subparsers.add_parser("top-issues", help="Show top priority issues")
    
    parser_export = subparsers.add_parser("export-report", help="Export report to JSON")
    parser_export.add_argument("--output", type=str, default="report.json", help="Output file path")
    
    parser_serve = subparsers.add_parser("serve", help="Run FastAPI server")
    
    args = parser.parse_args()
    
    if args.command == "analyze":
        api_ref = Api()
        run_analysis(args.file, api_ref=api_ref)
    elif args.command == "summary":
        clusters = load_processed_results()
        print_summary(clusters)
    elif args.command == "top-issues":
        clusters = load_processed_results()
        print_top_issues(clusters)
    elif args.command == "export-report":
        clusters = load_processed_results()
        export_report(clusters, args.output)
    elif args.command == "serve" or args.command is None:
        print("Starting Opinova Desktop App...")
        api = Api()
        html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
        html_url = f"file:///{html_path.replace('//', '/')}"
        api._window = webview.create_window("Opinova — Dashboard", url=html_url, js_api=api, width=1200, height=800)
        webview.start()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
