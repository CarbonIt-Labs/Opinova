import os
from sklearn.feature_extraction.text import TfidfVectorizer
import math

def create_semantic_batches(deduplicated_items: list[dict], batch_size: int = None) -> list[list[dict]]:
    """
    Groups deduplicated feedback items into batches based on dominant TF-IDF keyword.
    This ensures Gemini analyzes related feedbacks together and is extremely fast.
    """
    if batch_size is None:
        batch_size = int(os.getenv("BATCH_SIZE", "50"))
        
    if not deduplicated_items:
        return []
        
    num_items = len(deduplicated_items)
    
    # If the total items are less than or equal to batch size, return a single batch
    if num_items <= batch_size:
        return [deduplicated_items]
        
    # Extract texts for TF-IDF
    texts = [item["cleaned_text"] for item in deduplicated_items]
    
    try:
        # Use simple TF-IDF to get features with stop_words to ignore noise
        vectorizer = TfidfVectorizer(stop_words='english', max_features=2000)
        X = vectorizer.fit_transform(texts)
        feature_names = vectorizer.get_feature_names_out()
        
        # Group items by their dominant TF-IDF keyword
        clusters = {}
        for idx in range(num_items):
            row = X.getrow(idx).tocoo()
            if row.nnz == 0:
                label = "misc"
            else:
                max_idx = row.col[row.data.argmax()]
                label = feature_names[max_idx]
                
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(deduplicated_items[idx])
            
        # Distribute into final batches ensuring no batch exceeds batch_size
        batches = []
        current_batch = []
        
        # We can sort clusters by size descending so largest topics are grouped nicely
        sorted_clusters = sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True)
        
        for label, cluster_items in sorted_clusters:
            for item in cluster_items:
                current_batch.append(item)
                if len(current_batch) >= batch_size:
                    batches.append(current_batch)
                    current_batch = []
                    
        # Add any remaining items
        if current_batch:
            batches.append(current_batch)
            
        return batches
    except Exception as e:
        print(f"Error during semantic batching, falling back to sequential batching: {e}")
        # Fallback to sequential batching
        batches = []
        for i in range(0, num_items, batch_size):
            batches.append(deduplicated_items[i:i+batch_size])
        return batches
