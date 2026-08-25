import os
os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = "--disable-logging --log-level=3"
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
from config import BATCH_SIZE, DATA_DIR, ENV_FILE, LOG_FILE
# Optimization imports
from preprocessing import preprocess_feedbacks
from deduplication import deduplicate_feedbacks
from batching import create_semantic_batches
from database import (
    init_db, authenticate, save_clusters, load_clusters,
    update_cluster_status, add_file, get_files, get_file_by_id, update_file_status,
    get_default_user, update_default_user, delete_file as delete_db_file,
    get_cached_feedback, save_cached_feedback, save_metrics
)

def run_analysis(filepath: str, file_id: str, api_ref=None):
    try:
        from dotenv import load_dotenv
        load_dotenv(ENV_FILE, override=True)
        import time
        start_time = time.time()
        
        if api_ref: api_ref.log_activity(f"System started analysis on {os.path.basename(filepath)}.")
        print(f"Loading data from {filepath}...")
        try:
            df = load_file(filepath)
        except FileNotFoundError:
            print(f"File {filepath} not found.")
            if api_ref: api_ref.log_activity(f"Error: File {filepath} not found.")
            return False

        print("Reading all columns from the dataset...")
        df_str = df.astype(str)
        # Combine all columns for each row
        all_feedback = df_str.apply(lambda x: ' | '.join(x.dropna()), axis=1).tolist()
        
        # 1. Preprocessing
        prep_result = preprocess_feedbacks(all_feedback)
        valid_items = prep_result["valid_items"]
        stats = prep_result["stats"]
        
        print(f"Preprocessing stats: {stats}")
        if api_ref:
            api_ref.log_activity(f"Preprocessing removed {stats['empty_or_short']} empty/short, {stats['ignored_phrases']} ignored, {stats['emoji_punct_only']} noise.")
            
        # 2. Caching Check
        new_items = []
        cached_ai_clusters = []
        
        # We need to adapt cached clusters to the format expected by merge_batch_clusters
        # A cached cluster is one feedback's result, so frequency=1. We'll build temporary clusters.
        for item in valid_items:
            cached_cluster = get_cached_feedback(item["hash"])
            if cached_cluster:
                # Add the original index so merge_batch_clusters can find its text
                cached_cluster_copy = dict(cached_cluster)
                cached_cluster_copy['feedback_indices'] = [item["original_index"]]
                cached_ai_clusters.append(cached_cluster_copy)
            else:
                new_items.append(item)
                
        print(f"Found {len(cached_ai_clusters)} items in cache. {len(new_items)} items need Gemini analysis.")
        
        all_ai_clusters = list(cached_ai_clusters)
        
        duplicate_count = 0
        if new_items:
            # 3. Deduplication
            dedup_result = deduplicate_feedbacks(new_items)
            deduplicated_items = dedup_result["deduplicated_items"]
            duplicate_count = dedup_result["duplicate_count"]
            print(f"Deduplication merged {duplicate_count} items. Distinct items to process: {len(deduplicated_items)}")
            
            # 4. Batching
            batches = create_semantic_batches(deduplicated_items)
            
            for b_idx, batch in enumerate(batches):
                print(f"Analyzing semantic batch {b_idx + 1}/{len(batches)} (size: {len(batch)})...")
                
                backoff_times = [5, 15, 30, 60]
                max_retries = len(backoff_times)
                
                for attempt in range(max_retries):
                    try:
                        result = analyze_feedback_batch(batch)
                        for cluster in result.clusters:
                            cluster_dict = cluster.model_dump()
                            
                            # Map the returned indices (which refer to the batch array) 
                            # back to the original raw dataframe indices
                            mapped_original_indices = []
                            for local_idx in cluster_dict['feedback_indices']:
                                if local_idx < len(batch):
                                    mapped_original_indices.extend(batch[local_idx]["original_indices"])
                                    
                                    # 5. Save to Cache
                                    # Save a single-item cluster version for each unique hash in this representative group
                                    cache_cluster_repr = dict(cluster_dict)
                                    # strip indices since it's just for caching logic
                                    cache_cluster_repr['feedback_indices'] = [] 
                                    for h in batch[local_idx]["hashes"]:
                                        save_cached_feedback(h, cache_cluster_repr)
                                        
                            cluster_dict['feedback_indices'] = mapped_original_indices
                            all_ai_clusters.append(cluster_dict)
                        break
                    except Exception as e:
                        error_msg = str(e)
                        if "429" in error_msg or "Too Many Requests" in error_msg or "quota" in error_msg.lower() or "503" in error_msg or "Unavailable" in error_msg:
                            if attempt < max_retries - 1:
                                sleep_time = backoff_times[attempt]
                                print(f"API busy. Waiting {sleep_time}s...")
                                time.sleep(sleep_time)
                            else:
                                print(f"Failed to process batch {b_idx + 1}: {e}")
                        else:
                            print(f"Error processing batch {b_idx + 1}: {e}")
                            break
                time.sleep(2)

        if not all_ai_clusters:
            print("No feedback processed successfully.")
            return False

        print("Merging clusters across batches...")
        merged_clusters = merge_batch_clusters(all_ai_clusters, all_feedback)

        print("Applying priority scoring logic...")
        scored_clusters = score_clusters(merged_clusters)

        save_clusters(scored_clusters, file_id=file_id)
        update_file_status(file_id, 'analyzed')
        
        # 6. Metrics Calculation
        time_taken = time.time() - start_time
        tokens_before = sum([len(f)/4 for f in all_feedback])  # rough estimate
        tokens_after = 0
        if new_items:
             # Tokens based on representative texts passed to API
             tokens_after = sum([len(b['representative_text'])/4 for b in deduplicated_items])
        
        reduction = 100.0
        if tokens_before > 0:
            reduction = max(0, ((tokens_before - tokens_after) / tokens_before) * 100)
            
        save_metrics(file_id, int(tokens_before), int(tokens_after), reduction, duplicate_count, time_taken)
        
        print(f"Analysis complete. Results saved to DB. Tokens reduced by {reduction:.1f}%")
        if api_ref:
            api_ref.log_activity(f"Analysis complete for {os.path.basename(filepath)}. Optimization saved {reduction:.1f}% tokens.")
            
        print_top_issues(scored_clusters)
        return True
    except Exception as e:
        print(f"Critical error in run_analysis: {e}")
        import traceback
        traceback.print_exc()
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
        entry = {
            "message": message,
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.activities.append(entry)
        try:
            os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
            with open(LOG_FILE, "a", encoding="utf-8") as log_file:
                log_file.write(json.dumps(entry) + "\n")
        except Exception as e:
            print(f"Log write error: {e}")

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
        try:
            entries = []
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, "r", encoding="utf-8") as log_file:
                    for line in log_file:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entries.append(json.loads(line))
                        except Exception:
                            entries.append({"message": line, "time": ""})
            return entries[::-1][:100]
        except Exception as e:
            print(f"Log read error: {e}")
            return self.activities[::-1][:50]

    def clear_activities(self):
        try:
            os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
            with open(LOG_FILE, "w", encoding="utf-8"):
                pass
            self.activities = []
            self.log_activity("Activity logs cleared.")
            return {"status": "success"}
        except Exception as e:
            print(f"Log clear error: {e}")
            return {"status": "error", "message": str(e)}

    def log_custom_activity(self, message):
        self.log_activity(message)
        return True

    def get_settings(self):
        try:
            load_dotenv(ENV_FILE, override=True)
            user = get_default_user()
            return {
                "api_key": os.getenv("GEMINI_API_KEY", ""),
                "username": user.get("username", "admin"),
                "duplicate_threshold": os.getenv("DUPLICATE_SIMILARITY_THRESHOLD", "90.0"),
                "min_feedback_length": os.getenv("MIN_FEEDBACK_LENGTH", "3"),
                "batch_size": os.getenv("BATCH_SIZE", "50"),
                "ignored_phrases": os.getenv("IGNORED_PHRASES", "ok,good,fine,nice,yes,no,n/a,-,none"),
                "language_whitelist": os.getenv("LANGUAGE_WHITELIST", "en")
            }
        except Exception as e:
            print(f"Settings read error: {e}")
            return {"api_key": "", "username": "admin"}

    def save_settings(self, settings):
        try:
            api_key = (settings or {}).get("api_key", "").strip()
            username = (settings or {}).get("username", "").strip()
            password = (settings or {}).get("password", "").strip()
            
            dup_thresh = str((settings or {}).get("duplicate_threshold", "")).strip()
            min_len = str((settings or {}).get("min_feedback_length", "")).strip()
            batch_sz = str((settings or {}).get("batch_size", "")).strip()
            ignored = (settings or {}).get("ignored_phrases", "").strip()
            lang_white = (settings or {}).get("language_whitelist", "").strip()

            if api_key:
                self._set_env_value("GEMINI_API_KEY", api_key)
                os.environ["GEMINI_API_KEY"] = api_key
            
            if dup_thresh: self._set_env_value("DUPLICATE_SIMILARITY_THRESHOLD", dup_thresh)
            if min_len: self._set_env_value("MIN_FEEDBACK_LENGTH", min_len)
            if batch_sz: self._set_env_value("BATCH_SIZE", batch_sz)
            if ignored: self._set_env_value("IGNORED_PHRASES", ignored)
            if lang_white: self._set_env_value("LANGUAGE_WHITELIST", lang_white)

            if username:
                if not update_default_user(username, password or None):
                    return {"status": "error", "message": "Could not update login credentials."}

            self.log_activity("Platform settings updated.")
            return {"status": "success"}
        except Exception as e:
            print(f"Settings save error: {e}")
            return {"status": "error", "message": str(e)}

    def _set_env_value(self, key, value):
        os.makedirs(os.path.dirname(ENV_FILE), exist_ok=True)
        lines = []
        if os.path.exists(ENV_FILE):
            with open(ENV_FILE, "r", encoding="utf-8") as env_file:
                lines = env_file.read().splitlines()

        escaped_value = value.replace('"', '\\"')
        new_line = f'{key}="{escaped_value}"'
        updated = False
        for index, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[index] = new_line
                updated = True
                break
        if not updated:
            lines.append(new_line)

        with open(ENV_FILE, "w", encoding="utf-8") as env_file:
            env_file.write("\n".join(lines) + "\n")

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

    def delete_file(self, file_id):
        try:
            file_info = get_file_by_id(file_id)
            if not file_info:
                return {"status": "error", "message": "File not found"}
            if delete_db_file(file_id):
                self.log_activity(f"Deleted analyzed file '{file_info['filename']}'.")
                return {"status": "success", "message": "File deleted"}
            return {"status": "error", "message": "Could not delete file"}
        except Exception as e:
            print(f"Delete file error: {e}")
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
            suggestions = load_clusters(file_id=file_id, filter_status=status, suggestions_only=True)
            if not clusters and not suggestions:
                return {
                    "total_feedback": 0, "total_feedback_change": 0,
                    "clusters": 0, "clusters_new": 0,
                    "high_priority": 0, "high_priority_change": 0,
                    "immediate_actions": 0, "immediate_actions_change": 0,
                    "resolution_rate": 0, "resolution_rate_change": 0,
                    "suggestions_collected": 0
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
                "resolution_rate_change": 4.2,
                "suggestions_collected": len(suggestions)
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
                    "severity": sev,
                    "reasoning": c.get("reasoning", ""),
                    "why_it_matters": c.get("reasoning", ""),
                    "confidence": int(c.get("confidence", 0.95) * 100)
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
                    "status": c.get("status", "pending"),
                    "reasoning": c.get("reasoning", ""),
                    "why_it_matters": c.get("reasoning", ""),
                    "confidence": int(c.get("confidence", 0.95) * 100),
                    "recommended_action": c.get("recommended_action", "")
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
            for c in sorted_clusters:
                score = c.get('priority_score', 0)
                if score >= 85: sev = "critical"
                elif score >= 70: sev = "high"
                else: sev = "medium"
                recommendations.append({
                    "id": c.get("id"),
                    "title": f"Action Required: {c.get('topic')}",
                    "text": c.get('recommended_action', 'Review this feedback manually.'),
                    "priority": sev,
                    "status": c.get("status", "pending"),
                    "source_ids": c.get("feedback_indices", [])
                })
            return recommendations
        except Exception as e:
            print(f"Error in get_recommendations: {e}")
            return []

    def export_dashboard(self, filter_params=None):
        """Export comprehensive PDF report."""
        try:
            file_id, status = self._extract_params(filter_params)
            clusters = load_clusters(file_id=file_id, filter_status=status)
            suggestions = load_clusters(file_id=file_id, filter_status=status, suggestions_only=True)
            all_data = clusters + suggestions
            if not all_data:
                return {"status": "error", "message": "No data to export"}
            if self._window:
                result = self._window.create_file_dialog(webview.SAVE_DIALOG, allow_multiple=False, save_filename="Opinova_Report.pdf", file_types=('PDF Files (*.pdf)', 'All Files (*.*)'))
                if result and len(result) > 0:
                    dest_path = result[0] if isinstance(result, (list, tuple)) else result
                    self._generate_pdf_report(all_data, dest_path)
                    self.log_activity(f"Exported PDF report to {dest_path}")
                    import datetime
                    export_entry = {
                        "filename": os.path.basename(dest_path),
                        "path": dest_path,
                        "type": "PDF",
                        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "count": len(all_data)
                    }
                    if not hasattr(self, 'recent_exports'):
                        self.recent_exports = []
                    self.recent_exports.insert(0, export_entry)
                    return {"status": "success", "export": export_entry, "filename": export_entry["filename"], "message": "PDF report generated successfully!"}
            return {"status": "cancelled"}
        except Exception as e:
            print(f"Export PDF error: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    def export_csv(self, filter_params=None):
        """Export raw data as CSV."""
        try:
            file_id, status = self._extract_params(filter_params)
            clusters = load_clusters(file_id=file_id, filter_status=status)
            suggestions = load_clusters(file_id=file_id, filter_status=status, suggestions_only=True)
            all_data = clusters + suggestions
            if not all_data:
                return {"status": "error", "message": "No data to export"}
            if self._window:
                result = self._window.create_file_dialog(webview.SAVE_DIALOG, allow_multiple=False, save_filename="Opinova_Data.csv", file_types=('CSV Files (*.csv)', 'All Files (*.*)'))
                if result and len(result) > 0:
                    import pandas as pd
                    dest_path = result[0] if isinstance(result, (list, tuple)) else result
                    rows = []
                    for c in all_data:
                        rows.append({
                            "Topic": c.get("topic", ""),
                            "Issue Type": c.get("issue_type", ""),
                            "Category": c.get("category", ""),
                            "Priority Score": c.get("priority_score", 0),
                            "Frequency": c.get("frequency", 1),
                            "Criticality": c.get("criticality", 0),
                            "Urgency": c.get("urgency", 0),
                            "Impact": c.get("impact", 0),
                            "AI Confidence": f"{int(c.get('confidence', 0.95) * 100)}%",
                            "Reasoning": c.get("reasoning", ""),
                            "Recommended Action": c.get("recommended_action", ""),
                            "Status": c.get("status", "pending"),
                            "Feedback IDs": ", ".join([str(x) for x in c.get("feedback_indices", [])]),
                            "Original Texts": " | ".join(c.get("original_texts", []))
                        })
                    df = pd.DataFrame(rows)
                    df.to_csv(dest_path, index=False, encoding='utf-8-sig')
                    self.log_activity(f"Exported CSV data to {dest_path}")
                    import datetime
                    export_entry = {
                        "filename": os.path.basename(dest_path),
                        "path": dest_path,
                        "type": "CSV",
                        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "count": len(all_data)
                    }
                    if not hasattr(self, 'recent_exports'):
                        self.recent_exports = []
                    self.recent_exports.insert(0, export_entry)
                    return {"status": "success", "export": export_entry, "filename": export_entry["filename"], "message": "CSV data exported successfully!"}
            return {"status": "cancelled"}
        except Exception as e:
            print(f"Export CSV error: {e}")
            return {"status": "error", "message": str(e)}

    def get_recent_exports(self):
        if not hasattr(self, 'recent_exports'):
            self.recent_exports = []
        return self.recent_exports

    def _generate_pdf_report(self, clusters, filepath):
        """Generate a comprehensive PDF report from cluster data."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER, TA_LEFT
        except ImportError:
            # Fallback: write a formatted text file if reportlab is not installed
            self._generate_text_report(clusters, filepath)
            return

        doc = SimpleDocTemplate(filepath, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=20, spaceAfter=20, textColor=colors.HexColor('#0ea5e9'))
        heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=14, spaceAfter=8, spaceBefore=16, textColor=colors.HexColor('#1e293b'))
        body_style = ParagraphStyle('CustomBody', parent=styles['Normal'], fontSize=10, spaceAfter=4, leading=14)
        small_style = ParagraphStyle('CustomSmall', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#64748b'), leading=12)

        elements = []
        import datetime
        elements.append(Paragraph("Opinova — AI Feedback Analysis Report", title_style))
        elements.append(Paragraph(f"Generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", small_style))
        elements.append(Spacer(1, 20))

        # Summary
        sorted_clusters = sorted(clusters, key=lambda x: x.get('priority_score', 0), reverse=True)
        total_feedback = sum(c.get('frequency', 1) for c in clusters)
        high_priority = len([c for c in clusters if c.get('priority_score', 0) >= 70])
        elements.append(Paragraph("Executive Summary", heading_style))
        elements.append(Paragraph(f"Total feedback items analyzed: {total_feedback}", body_style))
        elements.append(Paragraph(f"Clusters identified: {len(clusters)}", body_style))
        elements.append(Paragraph(f"High priority issues: {high_priority}", body_style))
        elements.append(Spacer(1, 12))

        # Issues table
        elements.append(Paragraph("Priority Issues", heading_style))
        for i, c in enumerate(sorted_clusters):
            score = c.get('priority_score', 0)
            confidence = int(c.get('confidence', 0.95) * 100)
            elements.append(Paragraph(f"<b>{i+1}. {c.get('topic', 'Unknown')} (Score: {score}/100)</b>", body_style))
            elements.append(Paragraph(f"Category: {c.get('category', 'N/A')} | Frequency: {c.get('frequency', 1)} | AI Confidence: {confidence}%", small_style))
            if c.get('reasoning'):
                elements.append(Paragraph(f"<i>Why this matters:</i> {c.get('reasoning', '')}", small_style))
            if c.get('recommended_action'):
                elements.append(Paragraph(f"<i>Recommended action:</i> {c.get('recommended_action', '')}", small_style))
            elements.append(Spacer(1, 8))

        doc.build(elements)

    def _generate_text_report(self, clusters, filepath):
        """Fallback: generate a text-based report when reportlab is unavailable."""
        sorted_clusters = sorted(clusters, key=lambda x: x.get('priority_score', 0), reverse=True)
        total_feedback = sum(c.get('frequency', 1) for c in clusters)
        high_priority = len([c for c in clusters if c.get('priority_score', 0) >= 70])

        import datetime
        lines = []
        lines.append("=" * 60)
        lines.append("OPINOVA — AI FEEDBACK ANALYSIS REPORT")
        lines.append(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Total Feedback Items: {total_feedback}")
        lines.append(f"Clusters Identified: {len(clusters)}")
        lines.append(f"High Priority Issues: {high_priority}")
        lines.append("")
        lines.append("-" * 60)
        lines.append("PRIORITY ISSUES")
        lines.append("-" * 60)

        for i, c in enumerate(sorted_clusters):
            score = c.get('priority_score', 0)
            confidence = int(c.get('confidence', 0.95) * 100)
            lines.append("")
            lines.append(f"{i+1}. {c.get('topic', 'Unknown')} (Score: {score}/100)")
            lines.append(f"   Category: {c.get('category', 'N/A')} | Frequency: {c.get('frequency', 1)} | AI Confidence: {confidence}%")
            if c.get('reasoning'):
                lines.append(f"   Why this matters: {c.get('reasoning', '')}")
            if c.get('recommended_action'):
                lines.append(f"   Recommended action: {c.get('recommended_action', '')}")
            lines.append("-" * 40)

        # Change extension to .txt if it was .pdf
        if filepath.endswith('.pdf'):
            filepath = filepath[:-4] + '.txt'

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        self.log_activity(f"Note: reportlab not installed. Exported as text to {filepath}")


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
        def set_app_icon():
            import ctypes
            import time
            import sys
            if sys.platform == "win32":
                try:
                    # Give the window a moment to appear
                    time.sleep(1)
                    hwnd = ctypes.windll.user32.FindWindowW(None, "Opinova - Login")
                    if hwnd:
                        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logo.ico")
                        LR_LOADFROMFILE = 0x0010
                        IMAGE_ICON = 1
                        hicon = ctypes.windll.user32.LoadImageW(0, icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE)
                        if hicon:
                            WM_SETICON = 0x0080
                            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, 0, hicon) # ICON_SMALL
                            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, 1, hicon) # ICON_BIG
                            
                            # Update Taskbar icon by setting AppUserModelID
                            myappid = 'opinova.dashboard.app.1'
                            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
                except Exception as e:
                    print("Icon set error:", e)

        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logo.png")
        api._window = webview.create_window("Opinova - Login", url=html_url, js_api=api, width=1200, height=800)
        webview.start(func=set_app_icon, icon=logo_path)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
