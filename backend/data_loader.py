import pandas as pd
import json
import os
from config import DATA_DIR

def load_file(filename: str) -> pd.DataFrame:
    """Loads a CSV or JSON file from the DATA_DIR into a pandas DataFrame."""
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        # Fallback to check if it's an absolute path
        if os.path.exists(filename):
            filepath = filename
        else:
            raise FileNotFoundError(f"File not found: {filename}")
    
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext == '.csv':
        df = pd.read_csv(filepath)
    elif ext == '.json':
        df = pd.read_json(filepath)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Only .csv and .json are supported.")
        
    return df
