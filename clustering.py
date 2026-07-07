from typing import List, Dict

def merge_batch_clusters(all_clusters: List[Dict], original_feedback: List[str]) -> List[Dict]:
    """
    Merges AI-generated clusters from multiple batches.
    If two clusters from different batches have the same topic (case-insensitive), 
    they are combined.
    """
    merged = {}
    
    for cluster in all_clusters:
        topic_key = cluster['topic'].strip().lower()
        
        # Populate actual text from indices
        texts = [original_feedback[i] for i in cluster['feedback_indices'] if i < len(original_feedback)]
        freq = len(texts)
        if freq == 0:
            continue # Skip empty clusters
            
        if topic_key not in merged:
            merged[topic_key] = cluster.copy()
            merged[topic_key]['frequency'] = freq
            merged[topic_key]['original_texts'] = texts
            # Keep the highest confidence reasoning/action or just the first one
        else:
            existing = merged[topic_key]
            total_freq = existing['frequency'] + freq
            
            # Weighted average for scores
            existing['criticality'] = ((existing['criticality'] * existing['frequency']) + (cluster['criticality'] * freq)) / total_freq
            existing['urgency'] = ((existing['urgency'] * existing['frequency']) + (cluster['urgency'] * freq)) / total_freq
            existing['impact'] = ((existing['impact'] * existing['frequency']) + (cluster['impact'] * freq)) / total_freq
            
            # Sum users affected
            existing['users_affected_estimate'] += cluster['users_affected_estimate']
            existing['frequency'] = total_freq
            existing['original_texts'].extend(texts)
            
            # Update confidence (take average)
            existing['confidence'] = (existing['confidence'] + cluster['confidence']) / 2.0

    return list(merged.values())
