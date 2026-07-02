import argparse
import sys
import json
import os
from data_loader import load_file
from ai_engine import analyze_feedback
from clustering import cluster_feedback
from scoring import score_clusters
from reports import print_top_issues, print_summary, export_report
from fastapi import FastAPI
import uvicorn
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="ConsensusAI API")

PROCESSED_FILE = "data/processed_results.json"

def run_analysis(filepath: str):
    print(f"Loading data from {filepath}...")
    try:
        df = load_file(filepath)
    except FileNotFoundError:
        print(f"File {filepath} not found. Ensure it exists in the correct folder.")
        return
        
    text_col = None
    for col in df.columns:
        if df[col].dtype == 'object':
            text_col = col
            break
            
    if not text_col:
        print("Could not find a text column in the dataset.")
        return
        
    print(f"Found text column: '{text_col}'. Analyzing {len(df)} records...")
    
    processed_data = []
    for index, row in df.iterrows():
        text = str(row[text_col])
        print(f"Analyzing {index+1}/{len(df)}...")
        try:
            analysis = analyze_feedback(text)
            record = analysis.model_dump()
            record['original_text'] = text
            processed_data.append(record)
        except Exception as e:
            print(f"Error processing record {index+1}: {e}")
            
    if not processed_data:
        print("No records processed successfully.")
        return
        
    print("Clustering feedback...")
    clusters = cluster_feedback(processed_data)
    
    print("Scoring clusters...")
    scored_clusters = score_clusters(clusters)
    
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
    parser = argparse.ArgumentParser(description="ConsensusAI - Decision Intelligence Platform")
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
