import argparse
import sys
import json
import os
import time
from data_loader import load_file
from ai_engine import analyze_feedback_batch
from clustering import merge_batch_clusters
from scoring import score_clusters
from reports import print_top_issues, print_summary, export_report
from fastapi import FastAPI
import uvicorn
from dotenv import load_dotenv
from config import BATCH_SIZE

load_dotenv()

app = FastAPI(title="Opinova API API")

PROCESSED_FILE = "data/processed_results.json"

def run_analysis(filepath: str):
    print(f"Loading data from {filepath}...")
    try:
        df = load_file(filepath)
    except FileNotFoundError:
        print(f"File {filepath} not found. Ensure it exists in the correct folder.")
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
    print_top_issues(scored_clusters)

def load_processed_results():
    if not os.path.exists(PROCESSED_FILE):
        print(f"Error: Processed data not found. Please run 'python main.py analyze <file>' first.")
        sys.exit(1)
    with open(PROCESSED_FILE, 'r') as f:
        return json.load(f)

# --- FastAPI Endpoints ---
@app.get("/api/top-issues")
def api_top_issues():
    if not os.path.exists(PROCESSED_FILE):
        return {"error": "No analyzed data found."}
    clusters = load_processed_results()
    sorted_clusters = sorted(clusters, key=lambda x: x['priority_score'], reverse=True)
    return {"top_issues": sorted_clusters[:5]}

@app.get("/api/summary")
def api_summary():
    if not os.path.exists(PROCESSED_FILE):
        return {"error": "No analyzed data found."}
    clusters = load_processed_results()
    return {"total_clusters": len(clusters)}

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
        run_analysis(args.file)
    elif args.command == "summary":
        clusters = load_processed_results()
        print_summary(clusters)
    elif args.command == "top-issues":
        clusters = load_processed_results()
        print_top_issues(clusters)
    elif args.command == "export-report":
        clusters = load_processed_results()
        export_report(clusters, args.output)
    elif args.command == "serve":
        print("Starting FastAPI server...")
        uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
