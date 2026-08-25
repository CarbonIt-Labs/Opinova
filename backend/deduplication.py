import os
from rapidfuzz import fuzz

def deduplicate_feedbacks(valid_items: list[dict]) -> dict:
    threshold = float(os.getenv("DUPLICATE_SIMILARITY_THRESHOLD", "90.0"))
    unique_items = []
    duplicate_count = 0
    
    for item in valid_items:
        cleaned_text = item["cleaned_text"]
        is_duplicate = False
        
        for u_item in unique_items:
            if cleaned_text == u_item["cleaned_text"]:
                is_duplicate = True
                match_index = unique_items.index(u_item)
                break
                
            similarity = fuzz.ratio(cleaned_text, u_item["cleaned_text"])
            if similarity >= threshold:
                is_duplicate = True
                match_index = unique_items.index(u_item)
                break
                
        if is_duplicate:
            unique_items[match_index]["original_indices"].extend(item["original_indices"])
            unique_items[match_index]["hashes"].append(item["hash"])
            unique_items[match_index]["frequency"] += len(item["original_indices"])
            duplicate_count += len(item["original_indices"])
        else:
            unique_items.append({
                "representative_text": item["original_text"],
                "cleaned_text": cleaned_text,
                "original_indices": list(item["original_indices"]),
                "hashes": [item["hash"]],
                "frequency": len(item["original_indices"])
            })
            
    return {
        "deduplicated_items": unique_items,
        "duplicate_count": duplicate_count
    }
