"""Natural Hinglish transliteration from Devanagari using AI."""
import os
import re
from typing import Optional, List
import anthropic

# Cache for transliterations to avoid repeated API calls
_transliteration_cache = {}

# API client (lazy initialization)
_anthropic_client: Optional[anthropic.Anthropic] = None


def get_anthropic_client() -> anthropic.Anthropic:
    """Get or create Anthropic client."""
    global _anthropic_client
    if _anthropic_client is None:
        # Try multiple sources for API key
        api_key = os.getenv("ANTHROPIC_API_KEY")
        
        if not api_key:
            # Try loading from config
            try:
                from config import get_settings
                settings = get_settings()
                api_key = settings.anthropic_api_key
            except Exception:
                pass
        
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")
        
        _anthropic_client = anthropic.Anthropic(api_key=api_key)
    return _anthropic_client


def is_devanagari(text: str) -> bool:
    """Check if text contains Devanagari script."""
    # Devanagari Unicode range: 0900-097F
    return bool(re.search(r'[\u0900-\u097F]', text))


def is_english(text: str) -> bool:
    """Check if text is primarily English (Latin script)."""
    # Remove punctuation and spaces
    clean_text = re.sub(r'[^\w]', '', text)
    if not clean_text:
        return False
    # If more than 80% is ASCII letters, consider it English
    ascii_letters = sum(1 for c in clean_text if c.isascii() and c.isalpha())
    return ascii_letters / len(clean_text) > 0.8


def transliterate_with_llm(text: str) -> str:
    """
    Transliterate Devanagari to natural Hinglish using Claude Haiku.
    
    This produces the most natural output - like how Indians type on WhatsApp.
    """
    # Check cache first
    if text in _transliteration_cache:
        return _transliteration_cache[text]
    
    # Skip if already English
    if not is_devanagari(text):
        return text
    
    try:
        client = get_anthropic_client()
        
        prompt = f"""Convert this Hindi Devanagari text to natural Hinglish (Roman script). Write EXACTLY how Indians type Hindi in WhatsApp.

Rules:
- Use natural phonetic spelling (e.g., "main" not "maiN", "theek" not "thik")
- Keep English words as-is (developer, video, etc.)
- Use casual spelling like WhatsApp (e.g., "hoon" not "hun", "kaise" not "kese")
- No diacritics, no academic transliteration
- Only output the converted text, nothing else

Text: {text}"""

        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=512,
            temperature=0.3,  # Low temperature for consistency
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        # Extract transliterated text
        transliterated = response.content[0].text.strip()
        
        # Clean up any extra formatting
        transliterated = transliterated.strip('"\'')
        
        # Cache the result
        _transliteration_cache[text] = transliterated
        
        return transliterated
        
    except Exception as e:
        print(f"LLM transliteration error: {e}")
        # Fallback to simple character-by-character
        return transliterate_char_by_char(text)


def transliterate_char_by_char(text: str) -> str:
    """
    Fallback: Context-aware Devanagari to Hinglish transliteration.
    Handles inherent vowels (schwa) properly for natural output.
    """
    # Consonants (produce inherent 'a' unless followed by virama or vowel sign)
    CONSONANTS = {
        'क': 'k', 'ख': 'kh', 'ग': 'g', 'घ': 'gh', 'ङ': 'ng',
        'च': 'ch', 'छ': 'chh', 'ज': 'j', 'झ': 'jh', 'ञ': 'ny',
        'ट': 't', 'ठ': 'th', 'ड': 'd', 'ढ': 'dh', 'ण': 'n',
        'त': 't', 'थ': 'th', 'द': 'd', 'ध': 'dh', 'न': 'n',
        'प': 'p', 'फ': 'f', 'ब': 'b', 'भ': 'bh', 'म': 'm',
        'य': 'y', 'र': 'r', 'ल': 'l', 'व': 'v',
        'श': 'sh', 'ष': 'sh', 'स': 's', 'ह': 'h',
        'ड़': 'r', 'ढ़': 'rh',
    }
    
    # Independent vowels (at start of word or after another vowel)
    VOWELS = {
        'अ': 'a', 'आ': 'aa', 'इ': 'i', 'ई': 'ee',
        'उ': 'u', 'ऊ': 'oo', 'ए': 'e', 'ऐ': 'ai',
        'ओ': 'o', 'औ': 'au', 'ऋ': 'ri',
    }
    
    # Vowel signs (matras - replace inherent 'a')
    MATRAS = {
        'ा': 'aa', 'ि': 'i', 'ी': 'ee', 'ु': 'u', 'ू': 'oo',
        'े': 'e', 'ै': 'ai', 'ो': 'o', 'ौ': 'au', 'ृ': 'ri',
    }
    
    # Special marks
    VIRAMA = '्'  # Halant - kills inherent vowel
    ANUSVARA = 'ं'  # Nasal
    CHANDRABINDU = 'ँ'  # Nasal
    VISARGA = 'ः'  # Aspiration
    
    # Nukta combinations
    NUKTA_MAP = {'ड़': 'r', 'ढ़': 'rh', 'क़': 'q', 'ख़': 'kh', 'ग़': 'gh', 'ज़': 'z', 'फ़': 'f'}
    
    result = []
    i = 0
    chars = list(text)
    n = len(chars)
    
    while i < n:
        ch = chars[i]
        
        # Check nukta combinations (2-char)
        if i + 1 < n and ch + chars[i+1] in NUKTA_MAP:
            result.append(NUKTA_MAP[ch + chars[i+1]])
            # Check if next is virama or matra
            if i + 2 < n and chars[i+2] == VIRAMA:
                i += 3
            elif i + 2 < n and chars[i+2] in MATRAS:
                result.append(MATRAS[chars[i+2]])
                i += 3
            else:
                result.append('a')  # Inherent vowel
                i += 2
            continue
        
        # Consonant
        if ch in CONSONANTS:
            result.append(CONSONANTS[ch])
            # Look ahead for virama or matra
            if i + 1 < n and chars[i+1] == VIRAMA:
                # Virama kills inherent vowel
                i += 2
            elif i + 1 < n and chars[i+1] in MATRAS:
                result.append(MATRAS[chars[i+1]])
                i += 2
            else:
                # Add inherent 'a' vowel
                # But apply schwa deletion for word-final consonants
                # Simple heuristic: add 'a' always, fix in post-processing
                result.append('a')
                i += 1
            continue
        
        # Independent vowel
        if ch in VOWELS:
            result.append(VOWELS[ch])
            i += 1
            continue
        
        # Matra without consonant (shouldn't happen but handle)
        if ch in MATRAS:
            result.append(MATRAS[ch])
            i += 1
            continue
        
        # Anusvara
        if ch == ANUSVARA:
            result.append('n')
            i += 1
            continue
        
        # Chandrabindu
        if ch == CHANDRABINDU:
            result.append('n')
            i += 1
            continue
        
        # Visarga
        if ch == VISARGA:
            result.append('h')
            i += 1
            continue
        
        # Virama alone
        if ch == VIRAMA:
            i += 1
            continue
        
        # Devanagari danda
        if ch == '।':
            result.append('.')
            i += 1
            continue
        if ch == '॥':
            result.append('.')
            i += 1
            continue
        
        # Everything else (English, punctuation, spaces)
        result.append(ch)
        i += 1
    
    raw = ''.join(result)
    
    # Post-process: schwa deletion (remove trailing 'a' from words where unnatural)
    # In Hindi, word-final schwa is typically dropped
    words = raw.split()
    processed = []
    for word in words:
        # Remove trailing 'a' if word has multiple syllables and ends in consonant+a
        if len(word) > 2 and word.endswith('a') and word[-2].isalpha() and not word[-2] in 'aeiou':
            # But keep 'a' for short words and common patterns
            if len(word) > 3:
                word = word[:-1]
        processed.append(word)
    raw = ' '.join(processed)
    
    # Comprehensive word corrections for natural Hinglish
    corrections = {
        # Common greeting/basic words
        'namast': 'namaste', 'nmste': 'namaste', 'namaste': 'namaste',
        'doston': 'doston', 'dosaton': 'doston',
        'kaise': 'kaise', 'kais': 'kaise',
        'main': 'main', 'maiN': 'main',
        'hun': 'hoon', 'hoon': 'hoon', 'hooN': 'hoon',
        'hm': 'hum', 'ham': 'hum',
        'yh': 'yeh', 'yah': 'yeh', 'yeh': 'yeh',
        'bt': 'baat', 'bat': 'baat', 'baat': 'baat',
        'kreng': 'karenge', 'karenge': 'karenge', 'krenge': 'karenge',
        'bar': 'baare', 'bare': 'baare', 'baare': 'baare',
        'men': 'mein', 'mein': 'mein', 'maiN': 'main',
        'bhut': 'bahut', 'bahut': 'bahut', 'bhaut': 'bahut',
        'achchha': 'accha', 'achchh': 'accha', 'accha': 'accha', 'achha': 'accha',
        'achchhaa': 'accha', 'achchhaa': 'accha',
        'achchhe': 'acche',
        'eka': 'ek',
        'kaa': 'ka', 'kee': 'ki',
        'banavaaen': 'banwayen', 'banavaen': 'banwayen', 'banavaaen': 'banwayen',
        'thik': 'theek', 'theek': 'theek', 'thiik': 'theek',
        'aap': 'aap', 'aapa': 'aap',
        'hain': 'hain', 'haiN': 'hain',
        'hai': 'hai',
        'mausm': 'mausam', 'mausam': 'mausam',
        'grm': 'garam', 'garm': 'garam', 'garam': 'garam',
        'aaj': 'aaj',
        'ek': 'ek',
        'aur': 'aur', 'or': 'aur',
        'mujh': 'mujhe', 'mujhe': 'mujhe',
        'psnd': 'pasand', 'pasand': 'pasand', 'psanda': 'pasand',
        'shadi': 'shaadi', 'shaadi': 'shaadi', 'shaadee': 'shaadi',
        'bnvaen': 'banwayen', 'banvaen': 'banwayen', 'banwayen': 'banwayen',
        'tin': 'teen', 'teen': 'teen', 'tiin': 'teen',
        'jo': 'jo',
        'ke': 'ke', 'ka': 'ka', 'ki': 'ki',
        'ko': 'ko', 'se': 'se', 'me': 'mein',
        'par': 'par', 'pr': 'par',
        'kr': 'kar', 'kar': 'kar',
        'krna': 'karna', 'karna': 'karna',
        'krte': 'karte', 'karte': 'karte',
        'krta': 'karta', 'karta': 'karta',
        'kro': 'karo', 'karo': 'karo',
        'ho': 'ho', 'hua': 'hua', 'hui': 'hui',
        'rha': 'raha', 'raha': 'raha',
        'rhi': 'rahi', 'rahi': 'rahi',
        'gya': 'gaya', 'gaya': 'gaya',
        'gyi': 'gayi', 'gayi': 'gayi',
        'tha': 'tha', 'thi': 'thi', 'the': 'the',
        'nhi': 'nahi', 'nahi': 'nahi', 'naheen': 'nahi',
        'kya': 'kya', 'kyaa': 'kya',
        'kyu': 'kyu', 'kyun': 'kyun', 'kyunki': 'kyunki',
        'lekin': 'lekin', 'lkin': 'lekin',
        'agar': 'agar', 'agr': 'agar',
        'abhi': 'abhi', 'ab': 'ab',
        'bhi': 'bhi',
        'sab': 'sab', 'sb': 'sab',
        'kuch': 'kuch', 'kuchh': 'kuch',
        'dost': 'dost', 'dosata': 'dost',
        'pyar': 'pyaar', 'pyaar': 'pyaar',
        'log': 'log', 'loga': 'log',
        'video': 'video', 'vidio': 'video',
        # English words commonly written in Devanagari by STT
        'eaaee': 'AI', 'eeaai': 'AI', 'eaai': 'AI', 'eai': 'AI',
        'devalapar': 'developer', 'develapar': 'developer', 'devalpar': 'developer',
        'devaloper': 'developer', 'devloper': 'developer',
        'koding': 'coding', 'kooding': 'coding',
        'tools': 'tools', 'toolsa': 'tools', 'tool': 'tool',
        'teknolojee': 'technology', 'teknoloji': 'technology',
        'kompyutar': 'computer', 'kampyutar': 'computer',
        'softveyar': 'software', 'saphtveyar': 'software',
        'vebinaara': 'webinar', 'vebinaara': 'webinar',
        'instaagraam': 'instagram', 'instagraam': 'instagram',
        'youtyoob': 'youtube', 'yootyoob': 'youtube',
        'phon': 'phone', 'fon': 'phone',
        'apap': 'app', 'aip': 'app',
        'onalain': 'online', 'onlain': 'online',
        'frree': 'free', 'phree': 'free', 'fri': 'free',
        'bisanes': 'business', 'bijnes': 'business', 'bijanes': 'business',
        'maarketing': 'marketing', 'maarketinga': 'marketing',
        'kontenta': 'content', 'kontent': 'content',
        'freelaansing': 'freelancing', 'frelaansing': 'freelancing',
    }
    
    words = raw.split()
    corrected = []
    for word in words:
        # Separate trailing punctuation
        punct = ''
        clean = word
        while clean and not clean[-1].isalnum():
            punct = clean[-1] + punct
            clean = clean[:-1]
        
        clean_lower = clean.lower()
        if clean_lower in corrections:
            corrected.append(corrections[clean_lower] + punct)
        else:
            corrected.append(word)
    
    return ' '.join(corrected)


def transliterate_batch(texts: List[str], batch_size: int = 20) -> List[str]:
    """
    Transliterate multiple texts in batch for efficiency.
    Groups Devanagari texts and sends them together to LLM.
    """
    results = []
    devanagari_texts = []
    devanagari_indices = []
    
    # Separate Devanagari from English
    for i, text in enumerate(texts):
        if is_devanagari(text):
            devanagari_texts.append(text)
            devanagari_indices.append(i)
            results.append(None)  # Placeholder
        else:
            results.append(text)  # Keep English as-is
    
    # Transliterate Devanagari texts in batches
    if devanagari_texts:
        try:
            client = get_anthropic_client()
            
            # Process in batches
            for batch_start in range(0, len(devanagari_texts), batch_size):
                batch_end = min(batch_start + batch_size, len(devanagari_texts))
                batch = devanagari_texts[batch_start:batch_end]
                
                # Format batch as numbered list
                batch_text = "\n".join(f"{i+1}. {text}" for i, text in enumerate(batch))
                
                prompt = f"""Convert these Hindi Devanagari texts to natural Hinglish (Roman script). Write EXACTLY how Indians type Hindi in WhatsApp.

Rules:
- Use natural phonetic spelling (e.g., "main" not "maiN", "theek" not "thik")
- Keep English words as-is (developer, video, etc.)
- Use casual spelling like WhatsApp
- No diacritics, no academic transliteration
- Output each line with its number

Texts:
{batch_text}"""

                response = client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=2048,
                    temperature=0.3,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )
                
                # Parse numbered response
                response_text = response.content[0].text.strip()
                lines = response_text.split('\n')
                
                for i, line in enumerate(lines):
                    if batch_start + i >= len(devanagari_indices):
                        break
                    # Remove number prefix if present
                    clean_line = re.sub(r'^\d+\.\s*', '', line).strip('"\'')
                    original_idx = devanagari_indices[batch_start + i]
                    results[original_idx] = clean_line
                    
                    # Cache individual results
                    _transliteration_cache[batch[i]] = clean_line
                    
        except Exception as e:
            print(f"Batch LLM transliteration error: {e}")
            # Fallback for failed items
            for i, idx in enumerate(devanagari_indices):
                if results[idx] is None:
                    results[idx] = transliterate_char_by_char(devanagari_texts[i])
    
    return results


def devanagari_to_hinglish(text: str) -> str:
    """
    Convert Devanagari text to natural Hinglish (Roman script).
    
    This is the main function used by the transcription pipeline.
    It uses Claude Haiku for the most natural output.
    
    Args:
        text: Devanagari text or mixed Devanagari-English text
    
    Returns:
        Natural Hinglish text (like WhatsApp typing)
    """
    if not text or not text.strip():
        return text
    
    # If already English, return as-is
    if not is_devanagari(text):
        return text
    
    # Use LLM for natural transliteration
    return transliterate_with_llm(text)


def clear_cache():
    """Clear the transliteration cache."""
    global _transliteration_cache
    _transliteration_cache.clear()


# Test function
if __name__ == "__main__":
    test_texts = [
        "नमस्ते, कैसे हो?",
        "मैं एक developer हूं",
        "यह video बहुत अच्छा है",
        "आज मौसम बहुत गर्म है",
        "मैं ठीक हूं, आप कैसे हैं? यह बहुत अच्छा है।"
    ]
    
    print("Testing LLM-based Hinglish transliteration:\n")
    for text in test_texts:
        try:
            result = devanagari_to_hinglish(text)
            print(f"Input:  {text}")
            print(f"Output: {result}")
            print()
        except Exception as e:
            print(f"Error with '{text}': {e}")
            print()
