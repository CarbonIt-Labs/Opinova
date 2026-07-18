import os
import json
import time
import sys
import shutil
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
from database import (
    init_db, authenticate, save_clusters, load_clusters,
    update_cluster_status, add_file, get_files, get_file_by_id, update_file_status
)

load_dotenv()

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "uploads")

def run_analysis(filepath: str, file_id: str, api_ref=None):
    try:
        if api_ref: api_ref.log_activity(f"System started analysis on {os.path.basename(filepath)}.")
        print(f"Loading data from {filepath}...")
        try:
            df = load_file(filepath)
        except FileNotFoundError:
            print(f"File {filepath} not found.")
            if api_ref: api_ref.log_activity(f"Error: File {filepath} not found.")
            return False

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
            return False

        print(f"Found text column: '{text_col}'. Processing {len(df)} records in batches of {BATCH_SIZE}...")

        all_feedback = [str(text) for text in df[text_col].tolist()]
        all_ai_clusters = []

        for i in range(0, len(all_feedback), BATCH_SIZE):
            batch = all_feedback[i:i+BATCH_SIZE]
            print(f"Analyzing batch {i//BATCH_SIZE + 1}/{(len(all_feedback)-1)//BATCH_SIZE + 1}...")

            backoff_times = [5, 15, 30, 60]
            max_retries = len(backoff_times)

            for attempt in range(max_retries):
                try:
                    result = analyze_feedback_batch(batch)
                    for cluster in result.clusters:
                        cluster_dict = cluster.model_dump()
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
            time.sleep(2)

        if not all_ai_clusters:
            print("No batches processed successfully.")
            return False

        print("Merging clusters across batches...")
        merged_clusters = merge_batch_clusters(all_ai_clusters, all_feedback)

        print("Applying priority scoring logic...")
        scored_clusters = score_clusters(merged_clusters)

        save_clusters(scored_clusters, file_id=file_id)
        update_file_status(file_id, 'analyzed')
        print(f"Analysis complete. Results saved to SQLite database.")
        if api_ref:
            api_ref.log_activity(f"Analysis complete for file {os.path.basename(filepath)}.")
        print_top_issues(scored_clusters)
        return True
    except Exception as e:
        print(f"Critical error in run_analysis: {e}")
        if api_ref: api_ref.log_activity(f"Critical error: {e}")
        return False


class Api:
    def __init__(self):
        self._window = None
        self.activities = []
        import datetime
        self.log_activity(f"System initialized at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def log_activity(self, message):
        import datetime
        self.activities.append({
            "message": message,
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    def login(self, username, password):
        try:
            success = authenticate(username, password)
            if success:
                self.log_activity(f"User {username} logged in successfully.")
                html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "index.html")
                html_url = f"file:///{html_path.replace(os.sep, '/')}"
                return html_url
            else:
                self.log_activity(f"Failed login attempt for user {username}.")
                return False
        except Exception as e:
            print(f"Login error: {e}")
            return False

    def get_activities(self):
        return self.activities[::-1][:50]

    # ── File management ──────────────────────────────────────────────────────

    def get_files(self):
        try:
            return get_files()
        except Exception as e:
            print(f"Error in get_files: {e}")
            return []

    def upload_csv(self):
        """Opens file dialog, copies CSV to data/uploads/, registers in DB. Does NOT analyze."""
        try:
            if not self._window:
                return {"status": "error", "message": "No window reference"}
            file_types = ('CSV files (*.csv)', 'All files (*.*)')
            try:
                result = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=False, file_types=file_types)
            except AttributeError:
                result = self._window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, file_types=file_types)
            if not result or len(result) == 0:
                return {"status": "cancelled"}

            src_path = result[0]
            filename = os.path.basename(src_path)
            os.makedirs(DATA_DIR, exist_ok=True)
            dest_path = os.path.join(DATA_DIR, filename)

            # If file already exists, add suffix to avoid collision
            if os.path.exists(dest_path):
                base, ext = os.path.splitext(filename)
                import time as t
                dest_path = os.path.join(DATA_DIR, f"{base}_{int(t.time())}{ext}")
                filename = os.path.basename(dest_path)

            shutil.copy2(src_path, dest_path)
            file_id = add_file(filename, dest_path)
            if not file_id:
                return {"status": "error", "message": "Failed to register file in database"}

            self.log_activity(f"Uploaded file '{filename}' (id={file_id[:8]}). Ready for analysis.")
            return {"status": "success", "file_id": file_id, "filename": filename}
        except Exception as e:
            print(f"Upload error: {e}")
            return {"status": "error", "message": str(e)}

    def analyze_file(self, file_id):
        """Run analysis on the selected file_id. Returns progress/completion status."""
        try:
            file_info = get_file_by_id(file_id)
            if not file_info:
                return {"status": "error", "message": "File not found"}

            self.log_activity(f"Starting analysis of '{file_info['filename']}'...")
            update_file_status(file_id, 'analyzing')

            success = run_analysis(file_info['filepath'], file_id=file_id, api_ref=self)
            if success:
                return {"status": "success", "message": f"Analysis complete for {file_info['filename']}"}
            else:
                update_file_status(file_id, 'error')
                return {"status": "error", "message": "Analysis pipeline failed. Check console."}
        except Exception as e:
            print(f"Analyze error: {e}")
            return {"status": "error", "message": str(e)}

    # ── Dashboard data endpoints ─────────────────────────────────────────────

    def _extract_params(self, filter_params):
        if not filter_params:
            return None, None
        return filter_params.get('file_id'), filter_params.get('status')

    def get_kpi(self, filter_params=None):
        try:
            file_id, status = self._extract_params(filter_params)
            clusters = load_clusters(file_id=file_id, filter_status=status)
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
        except Exception as e:
            print(f"Error in get_kpi: {e}")
            return {}

    def get_matrix(self, filter_params=None):
        try:
            file_id, status = self._extract_params(filter_params)
            clusters = load_clusters(file_id=file_id, filter_status=status)
            matrix_points = []
            for c in clusters:
                score = c.get('priority_score', 0)
                if score >= 85: sev = "critical"
                elif score >= 70: sev = "high"
                elif score >= 50: sev = "medium"
                else: sev = "low"
                matrix_points.append({
                    "name": c.get("topic", "Unassigned Issue"),
                    "x": c.get("urgency", 5) / 10.0,
                    "y": c.get("impact", 5) / 10.0,
                    "score": score,
                    "severity": sev
                })
            return matrix_points
        except Exception as e:
            print(f"Error in get_matrix: {e}")
            return []

    def get_issues(self, filter_params=None):
        try:
            file_id, status = self._extract_params(filter_params)
            clusters = load_clusters(file_id=file_id, filter_status=status)
            sorted_clusters = sorted(clusters, key=lambda x: x.get('priority_score', 0), reverse=True)
            issues_list = []
            for i, c in enumerate(sorted_clusters[:8]):
                issues_list.append({
                    "id": c.get("id"),
                    "rank": i + 1,
                    "name": c.get("topic", "Unknown Cluster"),
                    "category": c.get("issue_type", "General feedback"),
                    "mentions": c.get("frequency", 1),
                    "score": c.get("priority_score", 0),
                    "source_ids": c.get("feedback_indices", []),
                    "original_texts": c.get("original_texts", []),
                    "status": c.get("status", "pending")
                })
            return issues_list
        except Exception as e:
            print(f"Error in get_issues: {e}")
            return []

    def get_suggestions(self, filter_params=None):
        try:
            file_id, status = self._extract_params(filter_params)
            clusters = load_clusters(file_id=file_id, filter_status=status, suggestions_only=True)
            return sorted(clusters, key=lambda x: x.get('priority_score', 0), reverse=True)
        except Exception as e:
            print(f"Error in get_suggestions: {e}")
            return []

    def mark_issue_status(self, issue_id, status):
        try:
            success = update_cluster_status(issue_id, status)
            if success:
                self.log_activity(f"Marked issue {issue_id} as {status}.")
            return success
        except Exception as e:
            print(f"Error marking issue: {e}")
            return False

    def get_clusters_detail(self, filter_params=None):
        try:
            file_id, status = self._extract_params(filter_params)
            return load_clusters(file_id=file_id, filter_status=status)
        except Exception as e:
            print(f"Error in get_clusters_detail: {e}")
            return []

    def get_sentiment(self, filter_params=None):
        try:
            file_id, status = self._extract_params(filter_params)
            clusters = load_clusters(file_id=file_id, filter_status=status)
            if not clusters:
                return {"positive": 0, "neutral": 0, "negative": 0}
            pos = neu = neg = 0
            for c in clusters:
                score = c.get('priority_score', 0)
                freq = c.get('frequency', 1)
                if score >= 70: neg += freq
                elif score >= 50: neu += freq
                else: pos += freq
            total = pos + neu + neg
            if total == 0: return {"positive": 0, "neutral": 0, "negative": 0}
            return {
                "positive": int((pos/total)*100),
                "neutral": int((neu/total)*100),
                "negative": int((neg/total)*100)
            }
        except Exception as e:
            print(f"Error in get_sentiment: {e}")
            return {"positive": 0, "neutral": 0, "negative": 0}

    def get_trend(self, filter_params=None):
        try:
            file_id, status = self._extract_params(filter_params)
            clusters = load_clusters(file_id=file_id, filter_status=status)
            sample = clusters[:4]
            positive_list, neutral_list, negative_list = [], [], []
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
        except Exception as e:
            print(f"Error in get_trend: {e}")
            return {"labels": [], "positive": [], "neutral": [], "negative": []}

    def get_recommendations(self, filter_params=None):
        try:
            file_id, status = self._extract_params(filter_params)
            clusters = load_clusters(file_id=file_id, filter_status=status)
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
        except Exception as e:
            print(f"Error in get_recommendations: {e}")
            return []

    def export_dashboard(self, filter_params=None):
        try:
            file_id, status = self._extract_params(filter_params)
            clusters = load_clusters(file_id=file_id, filter_status=status)
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
        except Exception as e:
            return {"status": "error", "message": str(e)}


def main():
    try:
        init_db()
    except Exception as e:
        print(f"Failed to init DB: {e}")

    parser = argparse.ArgumentParser(description="Opinova - Decision Intelligence Platform")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    parser_analyze = subparsers.add_parser("analyze", help="Analyze a feedback file (CSV/JSON)")
    parser_analyze.add_argument("file", type=str, help="Path to the file to analyze")

    subparsers.add_parser("summary", help="Show summary of analyzed feedback")
    subparsers.add_parser("top-issues", help="Show top priority issues")

    parser_export = subparsers.add_parser("export-report", help="Export report to JSON")
    parser_export.add_argument("--output", type=str, default="report.json", help="Output file path")

    subparsers.add_parser("serve", help="Run App")

    args = parser.parse_args()

    if args.command == "analyze":
        import uuid
        file_id = str(uuid.uuid4())
        run_analysis(args.file, file_id=file_id)
    elif args.command == "serve" or args.command is None:
        print("Starting Opinova Desktop App...")
        api = Api()
        html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "signinlogin.html")
        html_url = f"file:///{html_path.replace(os.sep, '/')}"
        api._window = webview.create_window("Opinova — Login", url=html_url, js_api=api, width=1200, height=800)
        webview.start()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
