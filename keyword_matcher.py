"""
Keyword-based text comparison module using RAKE
Returns 1 if texts match, 0 if they don't
"""

from rake_nltk import Rake


def extract_words_from_phrases(phrases):
    """Convert multi-word phrases to individual words"""
    words = set()
    for phrase in phrases:
        words.update(phrase.lower().split())
    return words


def compare_texts(text1, text2, threshold=50, verbose=False):
    
    # Initialize RAKE
    rake = Rake()
    
    # Extract keywords from text 1
    rake.extract_keywords_from_text(text1)
    keywords1 = rake.get_ranked_phrases()
    
    # Extract keywords from text 2
    rake.extract_keywords_from_text(text2)
    keywords2 = rake.get_ranked_phrases()
    
    # Convert phrases to single words
    words1 = extract_words_from_phrases(keywords1)
    words2 = extract_words_from_phrases(keywords2)
    
    # Find common words
    common = words1 & words2
    
    # Calculate overlap percentage
    overlap_percentage = (len(common) / len(words1)) * 100 if words1 else 0
    
    # Verbose output
    if verbose:
        # print(f"KEYWORD COMPARISON-")
        # print(f"Text 1 keywords: {len(words1)} words")
        # print(f"Text 2 keywords: {len(words2)} words")
        # print(f"Common keywords: {len(common)} words")
        # print(f"Overlap: {overlap_percentage:.1f}%")
        # print(f"Threshold: {threshold}%")
        
        if common:
            print(f"\nMatching keywords: {', '.join(sorted(list(common)[:10]))}")
            if len(common) > 10:
                print(f"... and {len(common) - 10} more")
        
        if overlap_percentage >= threshold:
            print(f"\nMATCH: Overlap {overlap_percentage:.1f}% >= {threshold}%")
        else:
            print(f"\nNO MATCH: Overlap {overlap_percentage:.1f}% < {threshold}%")

    
    # Return 1 for match, 0 for no match
    return 1 if overlap_percentage >= threshold else 0

