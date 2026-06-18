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

def calculate_heuristics(
    title: str, 
    text: str, 
    page_count: int = 1, 
    file_size_bytes: int = 0,
    all_circulars: List[Any] | None = None,
    current_hash: str = ""
) -> Dict[str, Any]:
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
    legal_terms_count = sum(1 for w in filtered_words if w in {"shall", "pursuant", "hereby", "notwithstanding", "provided"})
    
    if word_count > 5000 or legal_terms_count > 30:
        complexity = "Complex"
    elif word_count > 1500 or legal_terms_count > 10:
        complexity = "Medium"
    else:
        complexity = "Easy"

    # 4. Extract Circular Number
    circ_num_match = re.search(r"RBI/\d{4}-\d{2,4}/\d+", title)
    circular_number = circ_num_match.group(0) if circ_num_match else "UNKNOWN"

    # 5. Classify Department & Category
    rbi_department = "Department of Regulation (DoR)"
    title_lower = title.lower()
    if any(k in title_lower for k in ["dpss", "payment", "settlement", "card", "prepaid", "aggregator"]):
        rbi_department = "Dept. of Payment and Settlement Systems (DPSS)"
    elif any(k in title_lower for k in ["fema", "foreign exchange", "remittance", "export", "import", "fed"]):
        rbi_department = "Foreign Exchange Department (FED)"
    elif any(k in title_lower for k in ["fidd", "priority sector", "lending", "inclusion"]):
        rbi_department = "Financial Inclusion and Development Dept. (FIDD)"
    elif any(k in title_lower for k in ["supervision", "dos", "audit"]):
        rbi_department = "Department of Supervision (DoS)"
    
    category = "Circular"
    if "master direction" in title_lower:
        category = "Master Direction"
    elif "master circular" in title_lower:
        category = "Master Circular"
    elif "notification" in title_lower:
        category = "Notification"

    # 6. Calculate Related Circulars using Jaccard Similarity on title words
    related = []
    if all_circulars:
        def get_title_words(t: str) -> set[str]:
            return {w for w in re.split(r'\W+', t.lower()) if w not in STOP_WORDS and len(w) > 3}
        
        current_title_words = get_title_words(title)
        
        for c in all_circulars:
            if c.hash == current_hash:
                continue
            
            c_words = get_title_words(c.title)
            if not current_title_words or not c_words:
                similarity = 0.0
            else:
                similarity = len(current_title_words.intersection(c_words)) / len(current_title_words.union(c_words))
            
            # Boost if same department or category
            c_title_lower = c.title.lower()
            if ("master direction" in title_lower and "master direction" in c_title_lower) or \
               ("master circular" in title_lower and "master circular" in c_title_lower):
                similarity += 0.2
            
            related.append({
                "title": c.title,
                "date": c.date,
                "pdf_url": c.pdf_url,
                "hash": c.hash,
                "circular_number": getattr(c, "circular_number", "N/A"),
                "similarity": min(100, round(similarity * 100))
            })
        
        # Sort by similarity, then date
        related.sort(key=lambda x: (x["similarity"], x["date"]), reverse=True)
        related = related[:3]  # top 3 similar circulars

    document_size_kb = round(file_size_bytes / 1024, 1) if file_size_bytes > 0 else 0.0

    return {
        "reading_time": f"{reading_time_mins} min",
        "word_count": word_count,
        "keywords": top_keywords,
        "complexity": complexity,
        "page_count": page_count,
        "document_size_kb": f"{document_size_kb} KB" if document_size_kb > 0 else "N/A",
        "circular_number": circular_number,
        "rbi_department": rbi_department,
        "category": category,
        "related_circulars": related
    }

