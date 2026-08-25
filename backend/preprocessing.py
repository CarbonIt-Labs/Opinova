import re
import hashlib
import os
from functools import lru_cache
from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException

# To ensure consistent language detection
DetectorFactory.seed = 0

# Common English contractions expansion dictionary
CONTRACTIONS = {
    "won't": "will not", "won't've": "will not have", "can't": "cannot", "can't've": "cannot have",
    "let's": "let us", "ma'am": "madam", "it's": "it is", "i'm": "i am",
    "isn't": "is not", "aren't": "are not", "wasn't": "was not", "weren't": "were not",
    "haven't": "have not", "hasn't": "has not", "hadn't": "had not", "doesn't": "does not",
    "don't": "do not", "didn't": "did not", "couldn't": "could not", "shouldn't": "should not",
    "wouldn't": "would not", "mightn't": "might not", "mustn't": "must not"
}

def expand_contractions(text: str) -> str:
    for contraction, expansion in CONTRACTIONS.items():
        pattern = r'\b' + re.escape(contraction) + r'\b'
        text = re.sub(pattern, expansion, text)
    return text

def is_emoji_or_punctuation_only(text: str) -> bool:
    cleaned = re.sub(r'[^\w\s]', '', text).strip()
    return len(cleaned) == 0

def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = expand_contractions(text)
    text = re.sub(r'([!?.]){2,}', r'\1', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

@lru_cache(maxsize=10000)
def detect_language(text: str) -> str:
    try:
        return detect(text)
    except LangDetectException:
        return "unknown"

def generate_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def preprocess_feedbacks(feedbacks: list[str]) -> dict:
    min_len = int(os.getenv("MIN_FEEDBACK_LENGTH", "3"))
    ignored_phrases = set(os.getenv("IGNORED_PHRASES", "ok,good,fine,nice,yes,no,n/a,-,none").lower().split(","))
    lang_whitelist = set(os.getenv("LANGUAGE_WHITELIST", "en").split(","))

    valid_items = []
    stats = {
        "total_input": len(feedbacks),
        "empty_or_short": 0,
        "ignored_phrases": 0,
        "emoji_punct_only": 0,
        "unsupported_lang": 0,
        "valid_count": 0,
        "language_distribution": {}
    }
    
    # Pre-deduplication: keep exact raw texts to avoid repeating NLP on exact duplicates
    # We will map multiple indices to one raw_text
    raw_dedup = {}
    for idx, raw_text in enumerate(feedbacks):
        if not isinstance(raw_text, str) or not raw_text.strip():
            stats["empty_or_short"] += 1
            continue
        if raw_text not in raw_dedup:
            raw_dedup[raw_text] = []
        raw_dedup[raw_text].append(idx)
        
    for raw_text, indices in raw_dedup.items():
        cleaned = clean_text(raw_text)
        
        if len(cleaned) < min_len:
            stats["empty_or_short"] += len(indices)
            continue
            
        if cleaned in ignored_phrases:
            stats["ignored_phrases"] += len(indices)
            continue
            
        if is_emoji_or_punctuation_only(cleaned):
            stats["emoji_punct_only"] += len(indices)
            continue
            
        lang = detect_language(cleaned)
        stats["language_distribution"][lang] = stats["language_distribution"].get(lang, 0) + len(indices)
        
        if lang_whitelist and lang not in lang_whitelist and "all" not in lang_whitelist:
            stats["unsupported_lang"] += len(indices)
            continue
            
        # We output one valid item per distinct original text, keeping track of all indices
        valid_items.append({
            "original_indices": indices, # We'll need to adapt deduplication.py for this array
            "original_text": raw_text,
            "cleaned_text": cleaned,
            "hash": generate_hash(cleaned),
            "language": lang
        })
        
    stats["valid_count"] = len(valid_items)
    return {"valid_items": valid_items, "stats": stats}
