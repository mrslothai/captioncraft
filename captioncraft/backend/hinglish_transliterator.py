"""
Permanent Hinglish Transliteration: Devanagari → Natural WhatsApp-style Roman Hindi.

Uses indic-transliteration library (ITRANS scheme) as base, then applies
Hindi phonological rules to produce output matching how Indians type on WhatsApp.

Key insight: ITRANS uses uppercase for long vowels (A=आ, I=ई, U=ऊ) and 
lowercase 'a' for schwa. We use markers to distinguish them, apply schwa 
deletion only on true schwas, then convert markers to casual vowels.
"""

import re
from typing import List
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate as _transliterate


# ── English loanword map: Devanagari phonetic spelling → correct English ──
# Applied BEFORE ITRANS transliteration so English words come out correctly
LOANWORD_MAP = {
    # Education
    'कॉलेज': 'college', 'कालेज': 'college', 'काॅलेज': 'college',
    'स्कूल': 'school', 'स्कुल': 'school',
    'यूनिवर्सिटी': 'university', 'यूनिवर्सिटि': 'university',
    'कोर्स': 'course', 'क्लास': 'class', 'सिलेबस': 'syllabus',
    'एग्जाम': 'exam', 'टेस्ट': 'test', 'प्रोजेक्ट': 'project',
    'प्रोजेक्ट्स': 'projects', 'असाइनमेंट': 'assignment',

    # Numbers as words (AssemblyAI sometimes returns these)
    'साठ': '60', 'सत्तर': '70', 'अस्सी': '80', 'नब्बे': '90',
    'सौ': '100', 'हजार': '1000', 'लाख': 'lakh', 'करोड़': 'crore',
    'पाँच': '5', 'छह': '6', 'सात': '7', 'आठ': '8', 'नौ': '9',
    'दस': '10', 'बारह': '12', 'सोलह': '16', 'बीस': '20',
    'पचास': '50', 'पचहत्तर': '75',

    # Apple / MacBook specific
    'मैकबुक': 'MacBook', 'मैकबुक': 'MacBook',
    'एयर': 'Air', 'प्रो': 'Pro', 'मैक': 'Mac',
    'आईफोन': 'iPhone', 'आइफोन': 'iPhone',
    'आईपैड': 'iPad', 'एपल': 'Apple',
    'चिप': 'chip', 'चीप': 'chip',
    'टच': 'touch', 'टचआईडी': 'Touch ID', 'टच आईडी': 'Touch ID',
    'रेटिना': 'Retina', 'लिक्विड': 'liquid',
    'डिस्प्ले': 'display', 'डिसप्ले': 'display',
    'सोलर': 'solar',

    # Tech specs
    'जीबी': 'GB', 'टीबी': 'TB', 'एमबी': 'MB',
    'रैम': 'RAM', 'एसएसडी': 'SSD',
    'वेरिएंट': 'variant', 'वैरिएंट': 'variant',
    'वेरियंट': 'variant',
    'टाइप-सी': 'Type-C', 'टाइप सी': 'Type-C', 'टाइपसी': 'Type-C',

    # Commerce
    'ओरिजिनल': 'original', 'ओरिजिनल': 'original',
    'स्टूडेंट': 'student', 'स्टूडेंट्स': 'students',
    'डिस्काउंट': 'discount', 'डिस्काउंट्स': 'discounts',
    'प्राइस': 'price', 'प्राइसिंग': 'pricing',
    'बजट': 'budget', 'अफोर्डेबल': 'affordable',
    'कैशबैक': 'cashback', 'ऑफर': 'offer', 'डील': 'deal',

    # Common Hinglish filler/connector words that should stay as Hindi
    # (these are fine as transliterated, skip)

    # Tech - Devices
    'लैपटॉप': 'laptop', 'लैपटाप': 'laptop',
    'मोबाइल': 'mobile', 'मोबाईल': 'mobile',
    'फोन': 'phone', 'स्मार्टफोन': 'smartphone',
    'कंप्यूटर': 'computer', 'कम्प्यूटर': 'computer',
    'डेस्कटॉप': 'desktop', 'टैबलेट': 'tablet',
    'स्क्रीन': 'screen', 'मॉनिटर': 'monitor',
    'कीबोर्ड': 'keyboard', 'माउस': 'mouse',
    'प्रिंटर': 'printer', 'स्पीकर': 'speaker',
    'हेडफोन': 'headphone', 'चार्जर': 'charger',
    'केबल': 'cable', 'एडाप्टर': 'adapter',
    'बैटरी': 'battery', 'प्रोसेसर': 'processor',
    'रैम': 'RAM', 'जीबी': 'GB', 'टीबी': 'TB', 'एमबी': 'MB',
    'स्टोरेज': 'storage',
    # Education
    'कॉलेज': 'college', 'कालेज': 'college', 'स्कूल': 'school',
    'स्टूडेंट': 'student', 'स्टूडेंट्स': 'students',
    # Chips & specs
    'चिप': 'chip', 'चीप': 'chip', 'प्रोचिप': 'Pro chip',
    'वेरिएंट': 'variant', 'वेरिअंट': 'variant',
    'टचआईडी': 'Touch ID', 'टच': 'touch',
    # Numbers spoken as words (common in Hinglish)
    'सिक्सटीन': '16', 'सिक्सटी': '60',
    'एटीन': '18', 'ट्वेल्व': '12', 'थर्टीन': '13',
    'फिफ्टी': '50', 'फिफ्टीटू': '512', 'फाइव': '5',
    'सेवेंटी': '70', 'एटी': '80', 'नाइंटी': '90',
    'थाउजेंड': '000',
    # Common English words transcribed in Devanagari
    'ओरिजिनल': 'original', 'ओरिजिनली': 'originally',
    'बेसिकली': 'basically', 'एक्चुअली': 'actually',
    'मैसिव': 'massive', 'टाइप': 'type',
    'कमेंट': 'comment', 'कमेंट्स': 'comments',
    'नियो': 'Neo', 'एयर': 'Air',
    'एसएसडी': 'SSD', 'हार्डडिस्क': 'hard disk',
    'कैमरा': 'camera', 'माइक': 'mic',
    # Tech - Software/Internet
    'इंटरनेट': 'internet', 'वाईफाई': 'WiFi', 'वाई-फाई': 'WiFi',
    'ब्लूटूथ': 'Bluetooth', 'नेटवर्क': 'network',
    'सर्वर': 'server', 'क्लाउड': 'cloud',
    'डेटा': 'data', 'बैकअप': 'backup',
    'ऐप': 'app', 'एप': 'app', 'एप्प': 'app',
    'सॉफ्टवेयर': 'software', 'सॉफ़्टवेयर': 'software',
    'अपडेट': 'update', 'अपग्रेड': 'upgrade',
    'डाउनलोड': 'download', 'अपलोड': 'upload',
    'इंस्टॉल': 'install', 'इंस्टाल': 'install',
    'पासवर्ड': 'password', 'लॉगिन': 'login',
    'अकाउंट': 'account', 'प्रोफाइल': 'profile', 'प्रोफ़ाइल': 'profile',
    'लिंक': 'link', 'बटन': 'button',
    'क्लिक': 'click', 'स्क्रॉल': 'scroll',
    'सेटिंग': 'setting', 'सेटिंग्स': 'settings',
    'सिक्योरिटी': 'security', 'प्राइवेसी': 'privacy',
    'नोटिफिकेशन': 'notification', 'नोटिफिकेशंस': 'notifications',
    'वेबसाइट': 'website', 'वेब': 'web',
    'ब्राउज़र': 'browser', 'ब्राउजर': 'browser',
    'सर्च': 'search', 'फ़िल्टर': 'filter', 'फिल्टर': 'filter',
    'एरर': 'error', 'बग': 'bug', 'क्रैश': 'crash',
    # Tech - AI/Coding
    'एआई': 'AI', 'आर्टिफिशियल': 'artificial',
    'टेक': 'tech', 'टेक्नोलॉजी': 'technology',
    'कोडिंग': 'coding', 'कोड': 'code',
    'प्रोग्रामिंग': 'programming', 'प्रोग्राम': 'program',
    'डेवलपर': 'developer', 'डेवलपर्स': 'developers',
    'डेवलपिंग': 'developing', 'डेवलपमेंट': 'development',
    'डिज़ाइन': 'design', 'डिजाइन': 'design',
    'फ्रेमवर्क': 'framework', 'लाइब्रेरी': 'library',
    'एपीआई': 'API', 'डेटाबेस': 'database',
    'फ्रंटएंड': 'frontend', 'बैकएंड': 'backend',
    'फुलस्टैक': 'fullstack', 'डिप्लॉय': 'deploy',
    # Brands
    'गूगल': 'Google', 'यूट्यूब': 'YouTube',
    'इंस्टाग्राम': 'Instagram', 'ट्विटर': 'Twitter',
    'फेसबुक': 'Facebook', 'व्हाट्सएप': 'WhatsApp', 'व्हाट्सअप': 'WhatsApp',
    'एंड्रॉयड': 'Android', 'एंड्राइड': 'Android',
    'आईफोन': 'iPhone', 'एपल': 'Apple',
    'मैकबुक': 'MacBook', 'मैकबुक': 'MacBook',
    'विंडोज': 'Windows', 'लिनक्स': 'Linux',
    'माइक्रोसॉफ्ट': 'Microsoft', 'अमेजन': 'Amazon',
    'नेटफ्लिक्स': 'Netflix', 'स्पॉटिफाई': 'Spotify',
    'टेस्ला': 'Tesla', 'ओपनएआई': 'OpenAI',
    'चैटजीपीटी': 'ChatGPT', 'क्लॉड': 'Claude',
    # Social Media
    'वीडियो': 'video', 'रील': 'reel', 'रील्स': 'reels',
    'शॉर्ट्स': 'shorts', 'स्टोरी': 'story', 'स्टोरीज': 'stories',
    'पोस्ट': 'post', 'पोस्ट्स': 'posts',
    'लाइक': 'like', 'लाइक्स': 'likes',
    'कमेंट': 'comment', 'कमेंट्स': 'comments',
    'शेयर': 'share', 'सब्सक्राइब': 'subscribe',
    'फॉलो': 'follow', 'फॉलोअर्स': 'followers', 'फॉलोअर': 'follower',
    'कंटेंट': 'content', 'क्रिएटर': 'creator',
    'चैनल': 'channel', 'पेज': 'page',
    'व्यूज': 'views', 'रीच': 'reach',
    'इम्प्रेशन': 'impression', 'इम्प्रेशंस': 'impressions',
    'एंगेजमेंट': 'engagement', 'वायरल': 'viral',
    'ट्रेंड': 'trend', 'ट्रेंडिंग': 'trending',
    'हैशटैग': 'hashtag', 'मीम': 'meme',
    'थंबनेल': 'thumbnail', 'टाइटल': 'title',
    'डिस्क्रिप्शन': 'description', 'कैप्शन': 'caption',
    # Business/Finance
    'बिजनेस': 'business', 'बिज़नेस': 'business',
    'स्टार्टअप': 'startup', 'फाउंडर': 'founder',
    'प्रोडक्ट': 'product', 'फीचर': 'feature', 'फ़ीचर': 'feature',
    'यूजर': 'user', 'यूज़र': 'user', 'यूजर्स': 'users',
    'कस्टमर': 'customer', 'कस्टमर्स': 'customers',
    'मार्केटिंग': 'marketing', 'ब्रांड': 'brand',
    'कैंपेन': 'campaign', 'एड': 'ad', 'एड्स': 'ads',
    'सेल्स': 'sales', 'रेवेन्यू': 'revenue',
    'प्रॉफिट': 'profit', 'इन्वेस्टमेंट': 'investment',
    'फंडिंग': 'funding', 'पिच': 'pitch',
    'बजट': 'budget', 'पेमेंट': 'payment',
    'ऑफर': 'offer', 'डील': 'deal', 'डिस्काउंट': 'discount',
    'डिस्काउंट्स': 'discounts', 'कैशबैक': 'cashback',
    'सब्सक्रिप्शन': 'subscription', 'प्रीमियम': 'premium',
    'फ्री': 'free', 'प्राइस': 'price', 'प्राइसिंग': 'pricing',
    'ईएमआई': 'EMI', 'लोन': 'loan',
    # Common adjectives/adverbs used in Hinglish
    'बेस्ट': 'best', 'वर्स्ट': 'worst',
    'बेटर': 'better', 'ग्रेट': 'great',
    'परफेक्ट': 'perfect', 'अमेजिंग': 'amazing',
    'ऑसम': 'awesome', 'कूल': 'cool',
    'फास्ट': 'fast', 'स्लो': 'slow',
    'स्मार्ट': 'smart', 'लाइट': 'light',
    'हेवी': 'heavy', 'पावरफुल': 'powerful',
    'लेवल': 'level', 'नेक्स्ट': 'next',
    'टाइट': 'tight', 'लूज़': 'loose',
    # Common English words used in Hinglish
    'ऑन': 'on', 'ऑफ': 'off',
    'योर': 'your', 'माय': 'my',
    'सिचुएशन': 'situation', 'कंडीशन': 'condition',
    'सजेशन': 'suggestion', 'सजेस्ट': 'suggest',
    'डिपेंडिंग': 'depending', 'डिपेंड': 'depend',
    'अवेलेबल': 'available', 'अवेलेबिलिटी': 'availability',
    'लॉन्च': 'launch', 'लांच': 'launch',
    'स्टूडेंट': 'student', 'स्टूडेंट्स': 'students',
    'एक्सटेंड': 'extend', 'एक्सटेंशन': 'extension',
    'डिटेल': 'detail', 'डिटेल्स': 'details',
    'टास्क': 'task', 'टास्क्स': 'tasks',
    'इंफॉर्मेशन': 'information', 'इन्फो': 'info',
    'टाइम': 'time', 'डेट': 'date',
    'डे': 'day', 'वीक': 'week', 'मंथ': 'month', 'ईयर': 'year',
    'मिनट': 'minute', 'सेकंड': 'second',
    'प्लान': 'plan', 'प्लानिंग': 'planning',
    'टिप्स': 'tips', 'ट्रिक्स': 'tricks',
    'गाइड': 'guide', 'ट्यूटोरियल': 'tutorial',
    'रिव्यू': 'review', 'रेटिंग': 'rating',
    'स्कोर': 'score', 'रिजल्ट': 'result',
    'प्रॉब्लम': 'problem', 'सॉल्यूशन': 'solution',
    'चेंज': 'change', 'अपडेट': 'update',
    'वर्क': 'work', 'जॉब': 'job', 'करियर': 'career',
    'टीम': 'team', 'मीटिंग': 'meeting',
    'प्रेजेंटेशन': 'presentation', 'प्रोजेक्ट': 'project',
    'रिपोर्ट': 'report', 'डेडलाइन': 'deadline',
    'स्किल': 'skill', 'स्किल्स': 'skills',
    'लर्निंग': 'learning', 'कोर्स': 'course',
    'सर्टिफिकेट': 'certificate', 'डिग्री': 'degree',
    'पोर्टफोलियो': 'portfolio', 'रिज्यूमे': 'resume',
    'इंटरव्यू': 'interview', 'सैलरी': 'salary',
    'पैकेज': 'package', 'बोनस': 'bonus',
}

# Build regex pattern for loanword replacement (longest match first)
_LOANWORD_PATTERN = re.compile(
    '(' + '|'.join(re.escape(k) for k in sorted(LOANWORD_MAP.keys(), key=len, reverse=True)) + ')'
)


def _apply_loanword_map(text: str) -> str:
    """Replace Devanagari phonetic spellings of English words with correct English."""
    return _LOANWORD_PATTERN.sub(lambda m: LOANWORD_MAP[m.group(0)], text)


def is_devanagari(text: str) -> bool:
    return bool(re.search(r'[\u0900-\u097F]', text))


def _process_itrans_word(w: str) -> str:
    """Convert one ITRANS word to casual Hinglish."""
    if not w:
        return w
    
    # Separate punctuation
    punct = ''
    while w and not w[-1].isalnum():
        punct = w[-1] + punct
        w = w[:-1]
    if not w:
        return punct
    
    # ── 1. Mark long vowels with placeholders ──
    # Protect diphthongs first
    w = w.replace('ai', '\x01')
    w = w.replace('au', '\x02')
    w = w.replace('A', '§')   # long aa
    w = w.replace('I', '£')   # long ee
    w = w.replace('U', '¥')   # long oo
    w = w.replace('\x01', 'ai')
    w = w.replace('\x02', 'au')
    
    # ── 2. Consonant conversions ──
    # Anusvara
    w = re.sub(r'M(?=[pbm])', 'm', w)
    w = w.replace('M', 'n')
    # Chandrabindu / visarga
    w = w.replace('~N', 'n'); w = w.replace('.n', 'n'); w = w.replace('.N', 'n')
    w = w.replace('H', 'h')
    # Retroflex dots
    w = w.replace('.Dh', 'dh'); w = w.replace('.D', 'd'); w = w.replace('.T', 't')
    # Danda
    w = w.replace('|', '.')
    # Vowel modifiers
    w = w.replace('RRi', 'ri'); w = w.replace('LLi', 'li')
    # Nuqta
    w = w.replace('.k', 'q'); w = w.replace('.g', 'gh')
    w = w.replace('.j', 'z'); w = w.replace('.f', 'f'); w = w.replace('.p', 'f')
    # Aspirated (order matters)
    w = w.replace('Ch', 'chh')
    w = w.replace('Th', 'th'); w = w.replace('Dh', 'dh'); w = w.replace('Bh', 'bh')
    w = w.replace('Gh', 'gh'); w = w.replace('Jh', 'jh'); w = w.replace('Kh', 'kh')
    w = w.replace('Ph', 'ph'); w = w.replace('Sh', 'sh'); w = w.replace('sh', 'sh')
    w = w.replace('GY', 'gy'); w = w.replace('NY', 'ny')
    # Remaining ITRANS capitals
    for c in 'TDNKG':
        w = w.replace(c, c.lower())
    
    # ── 3. Schwa deletion ──
    # Only delete lowercase 'a' (schwa), never markers (§£¥)
    
    consonants = set('bcdfghjklmnpqrstvwxyz')
    vowels_all = set('aeiou§£¥')
    
    # 3a. Word-final schwa
    if len(w) > 1 and w[-1] == 'a' and w[-2] in consonants:
        w = w[:-1]
    
    # 3b. Medial schwa deletion
    # Rule: delete 'a' between consonants C₁aC₂ when:
    #   - There's already a vowel before C₁ (not first syllable)
    #   - Followed by a vowel sound (next syllable exists)
    # This prevents "chalo" → "chlo" but allows "chalate" → "chalte"
    
    changed = True
    while changed:
        changed = False
        chars = list(w)
        new = []
        i = 0
        while i < len(chars):
            if (chars[i] in consonants and
                i + 1 < len(chars) and chars[i+1] == 'a' and
                i + 2 < len(chars) and chars[i+2] in consonants and
                i + 3 < len(chars) and chars[i+3] in vowels_all):
                # Check: is there already a vowel before this position?
                preceding = ''.join(chars[:i])
                has_prior_vowel = any(c in vowels_all for c in preceding)
                if has_prior_vowel:
                    new.append(chars[i])
                    i += 2  # skip the schwa
                    changed = True
                else:
                    new.append(chars[i])
                    i += 1
            else:
                new.append(chars[i])
                i += 1
        w = ''.join(new)
    
    # ── 4. Convert markers to casual Hinglish vowels ──
    
    # § (long aa) conversion rules:
    # - Word-final → 'a' (tumhArA → tumhara)
    # - Word-initial → 'aa' (aaj, aap, aai)
    # - Internal in short words (≤4 chars) → 'aa' (naam, baat, kaam)
    # - Internal in longer words → 'a' (khana, tumhara, chahiye)
    
    # Word-final §
    if w.endswith('§'):
        w = w[:-1] + 'a'
    
    # Word-initial §
    if w.startswith('§'):
        w = 'aa' + w[1:]
    
    # Remaining internal §: depends on word length
    if '§' in w:
        if len(w) <= 4:
            w = w.replace('§', 'aa')
        else:
            w = w.replace('§', 'a')
    
    # £ (long ee):
    # - Word-final → 'i' (most casual: ladkee → ladki)  
    # - Internal → 'ee' (theek, neela)
    if w.endswith('£'):
        w = w[:-1] + 'i'
    # £ before 'n' at word end → 'i' + 'n' (naheen → nahin)
    w = re.sub(r'£n$', 'in', w)
    w = w.replace('£', 'ee')
    
    # ¥ (long oo):
    # - Generally → 'oo' (hoon, poora)
    # - Word-final before nothing → 'oo'
    w = w.replace('¥', 'oo')
    
    # ── 5. Consonant cluster cleanup ──
    w = w.replace('chchh', 'cch')  # अच्छ → acch not achchh
    
    # ── 6. Common word-specific fixes ──
    # 'ie' at word end from चाहिए → should be 'iye'
    if w.endswith('hie'):
        w = w[:-2] + 'iye'
    
    # ── 7. Word override dictionary ──
    overrides = {
        'yeh': 'yeh', 'yah': 'yeh',
        'woh': 'woh', 'vah': 'woh', 'voh': 'woh',
        'ham': 'hum', 'hum': 'hum',
        'nahi': 'nahi', 'nahin': 'nahi',
        'theek': 'theek', 'thik': 'theek',
        'accha': 'accha', 'acchi': 'acchi',
        'party': 'party', 'parti': 'party', 'paarti': 'party',
        'film': 'film',
        'bhai': 'bhai', 'bhaai': 'bhai',
        'men': 'mein',
        'dhanyvad': 'dhanyavaad', 'dhnyvad': 'dhanyavaad',
        'to': 'toh',
        'lie': 'liye',
    }
    w_lower = w.lower()
    if w_lower in overrides:
        w = overrides[w_lower]
    
    return w + punct


def _process_devanagari_segment(text: str) -> str:
    # Apply loanword map first — replaces Devanagari phonetic English with correct English
    text = _apply_loanword_map(text)
    # Remove candra-O (ॉ U+093B) which bleeds into roman output
    text = text.replace('\u093b', 'o').replace('\u0911', 'o')
    # After loanword substitution, text may be mixed (Devanagari + English tokens)
    # Split into Devanagari and non-Devanagari sub-segments and process separately
    parts = re.split(r'([\u0900-\u097F\u0964\u0965]+)', text)
    result_parts = []
    for part in parts:
        if not part:
            continue
        if re.search(r'[\u0900-\u097F]', part):
            # Pure Devanagari — transliterate
            itrans = _transliterate(part, sanscript.DEVANAGARI, sanscript.ITRANS)
            words = itrans.split()
            result_parts.append(' '.join(_process_itrans_word(w) for w in words))
        else:
            # English/numbers/punctuation — keep as-is (trim whitespace)
            stripped = part.strip()
            if stripped:
                result_parts.append(stripped)
    return ' '.join(result_parts)


def devanagari_to_hinglish(text: str) -> str:
    """Convert Devanagari (or mixed) text to natural Hinglish."""
    if not text or not text.strip():
        return text
    if not is_devanagari(text):
        return text
    
    segments = re.split(r'([\u0900-\u097F\u0964\u0965]+)', text)
    parts = []
    for seg in segments:
        if not seg:
            continue
        if is_devanagari(seg) or seg in ('।', '॥'):
            parts.append(_process_devanagari_segment(seg))
        else:
            parts.append(seg)
    return ''.join(parts)


def transliterate_word_smart(word: str) -> str:
    """
    Smart per-word transliteration for AssemblyAI output.
    - Pure Latin/ASCII words (English, numbers) → keep as-is
    - Devanagari words → transliterate to Hinglish
    - Mixed → transliterate Devanagari parts, keep Latin parts
    """
    if not word:
        return word
    # Strip punctuation for check
    clean = word.strip('.,!?।|')
    # Pure Latin (English words, numbers, alphanumeric like "A18", "512GB") → keep
    if re.match(r'^[a-zA-Z0-9\-_/]+$', clean):
        return word
    # Has Devanagari → transliterate
    if is_devanagari(word):
        return devanagari_to_hinglish(word)
    return word


# Backward compat
transliterate_batch = lambda texts: [transliterate_word_smart(t) for t in texts]
transliterate_with_llm = devanagari_to_hinglish
transliterate_char_by_char = devanagari_to_hinglish
def clear_cache(): pass


if __name__ == "__main__":
    tests = [
        ("नमस्ते दोस्तों, कैसे हो?", "namaste doston, kaise ho?"),
        ("मैं एक developer हूं", "main ek developer hoon"),
        ("आज मौसम बहुत गर्म है", "aaj mausam bahut garm hai"),
        ("क्या तुम खाना खाओगे?", "kya tum khana khaoge?"),
        ("ज़रूरी फ़िल्म देखनी है", "zaroori film dekhni hai"),
        ("अच्छा चलो फिर मिलते हैं", "accha chalo phir milte hain"),
        ("तुम्हारा नाम क्या है?", "tumhara naam kya hai?"),
        ("मुझे पता नहीं", "mujhe pata nahi"),
        ("चलो घर चलते हैं", "chalo ghar chalte hain"),
        ("बोलो क्या चाहिए", "bolo kya chahiye"),
        ("पैसे कमाओ", "paise kamao"),
        ("सुनो भाई", "suno bhai"),
        ("यह बहुत अच्छी बात है", "yeh bahut acchi baat hai"),
        ("मैं ठीक हूं, आप कैसे हैं?", "main theek hoon, aap kaise hain?"),
        ("हम सब दोस्त मिलकर पार्टी करेंगे", "hum sab dost milkar party karenge"),
        ("मुझे यह फ़िल्म बहुत पसंद आई", "mujhe yeh film bahut pasand aai"),
        ("क्या आप मेरी मदद कर सकते हैं?", "kya aap meri madad kar sakte hain?"),
        ("123", "123"),
        ("Hello world", "Hello world"),
        ("", ""),
    ]
    
    print("=" * 90)
    print("HINGLISH TRANSLITERATION — NATURAL OUTPUT TEST")
    print("=" * 90)
    
    p = f = 0
    for inp, exp in tests:
        got = devanagari_to_hinglish(inp)
        if got == exp:
            p += 1; print(f"  ✓  {inp:40} → {got}")
        else:
            f += 1; print(f"  ✗  {inp:40}")
            print(f"       got:      {got}")
            print(f"       expected: {exp}")
    print(f"\nResults: {p}/{p+f} passed, {f} failed")
