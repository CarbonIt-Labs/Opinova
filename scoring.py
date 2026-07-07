from typing import Dict, List

def calculate_priority_score(cluster: Dict) -> Dict:
    """
    Calculates a Priority Score (out of 100) based on metrics.
    Weights: Criticality (35%), Urgency (25%), Impact (20%), Frequency (10%), Users Affected (10%)
    """
    freq_score = min(cluster['frequency'] * 2, 10) 
    users_score = min(cluster['users_affected_estimate'] / 5, 10)
    
    score = (
        (cluster['criticality'] * 3.5) +
        (cluster['urgency'] * 2.5) +
        (cluster['impact'] * 2.0) +
        (freq_score * 1.0) +
        (users_score * 1.0)
    )
    
    final_score = int(min(round(score), 100))
    cluster['priority_score'] = final_score
    cluster['category'] = categorize_issue(cluster)
    return cluster

def categorize_issue(cluster: Dict) -> str:
    """Classifies issues based on scores and types."""
    score = cluster.get('priority_score', 0)
    issue_type = cluster.get('issue_type', '').lower()
    
    # Hard rule: USP
    if cluster.get('criticality', 0) >= 8 and cluster.get('urgency', 0) >= 8:
        return "Immediate Action Required"
        
    if "suggestion" in issue_type and score < 80:
        return "Community Suggestions"
    
    if score >= 85:
        return "Immediate Action Required"
    elif score >= 70:
        if cluster.get('urgency', 0) >= 8 and cluster.get('impact', 0) <= 6:
            return "Quick Wins"
        else:
            return "Strategic Improvements"
    elif score >= 50:
        return "Quick Wins" if cluster.get('urgency', 0) >= 6 else "Strategic Improvements"
    else:
        return "Monitor & Observe"

def score_clusters(clusters: List[Dict]) -> List[Dict]:
    return [calculate_priority_score(c) for c in clusters]
