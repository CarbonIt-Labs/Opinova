from typing import Dict, List

def calculate_priority_score(cluster: Dict) -> Dict:
    """
    Calculates a Priority Score (out of 100) based on average metrics.
    Weights: Criticality (35%), Urgency (25%), Impact (20%), Frequency (10%), Users Affected (10%)
    """
    # Normalize frequency and users affected to a 10-point scale for scoring
    # Cap at 10 to prevent them from overwhelming the score
    freq_score = min(cluster['frequency'] * 2, 10) 
    users_score = min(cluster['total_users_affected'] / 5, 10)
    
    score = (
        (cluster['avg_criticality'] * 3.5) +
        (cluster['avg_urgency'] * 2.5) +
        (cluster['avg_impact'] * 2.0) +
        (freq_score * 1.0) +
        (users_score * 1.0)
    )
    
    # Cap total score at 100
    final_score = int(min(round(score), 100))
    
    cluster['priority_score'] = final_score
    cluster['category'] = categorize_issue(cluster)
    return cluster

def categorize_issue(cluster: Dict) -> str:
    """Classifies issues based on scores and types."""
    score = cluster.get('priority_score', 0)
    is_suggestion = cluster.get('is_suggestion_majority', False)
    
    # Hard rule: If both criticality and urgency are 8 or higher, it's an immediate crisis
    if cluster.get('avg_criticality', 0) >= 8 and cluster.get('avg_urgency', 0) >= 8:
        return "Immediate Action Required"
        
    if is_suggestion and score < 80:
        return "Community Suggestions"
    
    if score >= 85:
        return "Immediate Action Required"
    elif score >= 70:
        # High urgency but maybe lower impact -> Quick Win
        if cluster.get('avg_urgency', 0) >= 8 and cluster.get('avg_impact', 0) <= 6:
            return "Quick Wins"
        else:
            return "Strategic Improvements"
    elif score >= 50:
        return "Quick Wins" if cluster.get('avg_urgency', 0) >= 6 else "Strategic Improvements"
    else:
        return "Monitor & Observe"

def score_clusters(clusters: List[Dict]) -> List[Dict]:
    return [calculate_priority_score(c) for c in clusters]
