"""
Deterministic heuristics engine for fast document classification.
Zero AI required.
"""

import re
from typing import Dict, Any, List

# Basic legal/compliance stopwords to filter out
STOP_WORDS = {
    "the", "and", "to", "of", "in", "for", "a", "is", "that", "by", "on", "as", 
    "with", "it", "this", "be", "are", "shall", "will", "has", "have", "or",
    "from", "at", "an", "not", "we", "rbi", "bank", "banks", "india", "reserve",
    "all", "such", "any", "which", "under", "these", "their", "other", "may"
}

def calculate_heuristics(title: str, text: str) -> Dict[str, Any]:
    """Calculate all non-AI metrics deterministically."""
    
    words = [w for w in re.split(r'\W+', text.lower()) if w]
    word_count = len(words)
    
    # 1. Reading Time
    reading_time_mins = max(1, round(word_count / 220))
    
    # 2. Keywords
    filtered_words = [w for w in words if w not in STOP_WORDS and len(w) > 3]
    freq: Dict[str, int] = {}
    for w in filtered_words:
        freq[w] = freq.get(w, 0) + 1
    
    sorted_keywords = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    top_keywords = [k[0] for k in sorted_keywords[:10]]
    
    # 3. Complexity Score
    # Simple heuristic: lots of words + 'shall'/'pursuant' = complex
    legal_terms_count = sum(1 for w in filtered_words if w in {"shall", "pursuant", "hereby", "notwithstanding", "provided"})
    
    if word_count > 5000 or legal_terms_count > 30:
        complexity = "Complex"
    elif word_count > 1500 or legal_terms_count > 10:
        complexity = "Medium"
    else:
        complexity = "Easy"

    return {
        "reading_time": f"{reading_time_mins} min",
        "word_count": word_count,
        "keywords": top_keywords,
        "complexity": complexity
    }
