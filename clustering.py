import pandas as pd
from typing import List, Dict

def cluster_feedback(processed_data: List[Dict]) -> List[Dict]:
    """
    Groups individual feedback analysis results by their extracted topics.
    Calculates aggregate metrics for the cluster (frequency, avg impact, etc.).
    """
    df = pd.DataFrame(processed_data)
    
    if df.empty:
        return []
        
    # Group by the LLM-extracted topic
    clusters = []
    grouped = df.groupby('topic')
    
    for topic, group in grouped:
        cluster = {
            "topic": topic,
            "frequency": len(group),
            "avg_criticality": group['criticality'].mean(),
            "avg_urgency": group['urgency'].mean(),
            "avg_impact": group['impact'].mean(),
            "total_users_affected": group['users_affected_estimate'].sum(),
            "is_complaint_majority": group['is_complaint'].mean() > 0.5,
            "is_suggestion_majority": group['is_suggestion'].mean() > 0.5,
            "original_texts": group['original_text'].tolist()
        }
        clusters.append(cluster)
        
    return clusters
