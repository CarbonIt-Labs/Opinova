import json
from typing import List, Dict

def print_top_issues(scored_clusters: List[Dict], top_n: int = 3):
    sorted_clusters = sorted(scored_clusters, key=lambda x: x['priority_score'], reverse=True)
    
    print("\nTOP ISSUES\n")
    for i, cluster in enumerate(sorted_clusters[:top_n], 1):
        print(f"{i}. {cluster['topic']}")
        print(f"Priority: {cluster['priority_score']}/100")
        print(f"Category: {cluster['category']}")
        print()

def print_summary(scored_clusters: List[Dict]):
    total_issues = sum([c['frequency'] for c in scored_clusters])
    print(f"\nTotal Feedback Analyzed: {total_issues}")
    print(f"Total Clusters Identified: {len(scored_clusters)}\n")
    
    print("Category Breakdown:")
    categories = {}
    for c in scored_clusters:
        cat = c['category']
        categories[cat] = categories.get(cat, 0) + 1
        
    for cat, count in categories.items():
        print(f"- {cat}: {count} cluster(s)")
    print()

def export_report(scored_clusters: List[Dict], output_path: str = "report.json"):
    with open(output_path, 'w') as f:
        json.dump(scored_clusters, f, indent=4)
    print(f"Report exported successfully to {output_path}")
