#!/usr/bin/env python3
"""
Comprehensive test suite for Hinglish transliteration.
Tests 30+ diverse cases covering all edge cases.
"""

from hinglish_transliterator import devanagari_to_hinglish


# Comprehensive test cases
TEST_CASES = [
    # === BASIC GREETINGS ===
    ("नमस्ते", "namaste", "Basic greeting"),
    ("नमस्ते दोस्तों", "namaste doston", "Greeting with plural"),
    ("नमस्कार", "namaskar", "Formal greeting"),
    
    # === COMMON QUESTIONS ===
    ("क्या", "kya", "What"),
    ("कैसे हो", "kaise ho", "How are you"),
    ("कैसे हैं", "kaise hain", "How are you (formal)"),
    ("क्यों", "kyu", "Why"),
    ("कब", "kab", "When"),
    ("कहां", "kahan", "Where"),
    
    # === PRONOUNS ===
    ("मैं", "main", "I"),
    ("हम", "hum", "We"),
    ("तुम", "tum", "You (informal)"),
    ("आप", "aap", "You (formal)"),
    ("यह", "yeh", "This"),
    ("वह", "woh", "That"),
    
    # === COMMON VERBS ===
    ("हूँ", "hoon", "Am (with chandrabindu)"),
    ("हैं", "hain", "Are (plural)"),
    ("है", "hai", "Is"),
    ("था", "tha", "Was"),
    ("करना", "karna", "To do"),
    ("करेंगे", "karenge", "Will do"),
    ("कर सकते हैं", "kar sakte hain", "Can do"),
    
    # === ADJECTIVES ===
    ("अच्छा", "accha", "Good (masculine)"),
    ("अच्छी", "acchi", "Good (feminine)"),
    ("अच्छे", "acche", "Good (plural)"),
    ("बहुत", "bahut", "Very/Much"),
    ("ठीक", "theek", "Fine/OK"),
    ("बड़ा", "bada", "Big"),
    ("छोटा", "chhota", "Small"),
    
    # === CONJUNCTS (HALF-LETTERS) ===
    ("प्रभु", "prabhu", "Lord (pr conjunct)"),
    ("स्त्री", "stree", "Woman (str conjunct)"),
    ("क्षेत्र", "kshetra", "Field (ksh conjunct)"),
    ("त्रिकोण", "trikon", "Triangle (tr conjunct)"),
    
    # === NASALS ===
    ("हूँ", "hoon", "Chandrabindu nasal"),
    ("हैं", "hain", "Anusvara nasal"),
    ("मैं", "main", "Anusvara in mein"),
    ("में", "mein", "In (anusvara)"),
    
    # === NUQTA CHARACTERS (URDU SOUNDS) ===
    ("ज़रूरी", "zaroori", "Necessary (za with nuqta)"),
    ("फ़िल्म", "film", "Film (fa with nuqta)"),
    ("क़िस्मत", "qismat", "Fate (qa with nuqta)"),
    ("ख़राब", "kharab", "Bad (kha with nuqta)"),
    ("ग़लत", "ghalat", "Wrong (gha with nuqta)"),
    
    # === COMMON NOUNS ===
    ("दोस्त", "dost", "Friend"),
    ("दोस्तों", "doston", "Friends"),
    ("बात", "baat", "Talk/Thing"),
    ("वीडियो", "video", "Video (English word in Devanagari)"),
    ("मौसम", "mausam", "Weather"),
    
    # === LONG VOWELS ===
    ("आज", "aaj", "Today (long aa)"),
    ("ईमान", "eemaan", "Faith (long ee)"),
    ("ऊपर", "oopar", "Above (long oo)"),
    
    # === COMMON SENTENCES ===
    ("मैं ठीक हूं", "main theek hoon", "I am fine"),
    ("आप कैसे हैं?", "aap kaise hain?", "How are you?"),
    ("यह बहुत अच्छा है", "yeh bahut accha hai", "This is very good"),
    ("आज मौसम बहुत गर्म है", "aaj mausam bahut garam hai", "Today weather is very hot"),
    ("मैं एक developer हूं", "main ek developer hoon", "I am a developer"),
    ("यह video बहुत अच्छा है", "yeh video bahut accha hai", "This video is very good"),
    ("क्या आप मेरी मदद कर सकते हैं?", "kya aap meri madad kar sakte hain?", "Can you help me?"),
    ("हम सब दोस्त मिलकर पार्टी करेंगे", "hum sab dost milkar party karenge", "We all friends will party together"),
    
    # === MIXED DEVANAGARI-ENGLISH ===
    ("मैं एक Python developer हूं", "main ek Python developer hoon", "Mixed: I am a Python developer"),
    ("यह AI tool बहुत अच्छा है", "yeh AI tool bahut accha hai", "Mixed: This AI tool is very good"),
    ("Instagram पर video upload करो", "Instagram par video upload karo", "Mixed: Upload video on Instagram"),
    ("WhatsApp में message भेजो", "WhatsApp mein message bhejo", "Mixed: Send message on WhatsApp"),
    
    # === SCHWA DELETION TESTS ===
    ("बहुत गर्म", "bahut garam", "Schwa deletion at word end"),
    ("सब ठीक", "sab theek", "Schwa deletion: sab, theek"),
    ("एक दोस्त", "ek dost", "Schwa deletion: ek, dost"),
    
    # === EDGE CASES ===
    ("", "", "Empty string"),
    ("Hello", "Hello", "Pure English"),
    ("123", "123", "Numbers"),
    ("।", ".", "Devanagari danda"),
]


def run_tests():
    """Run all test cases and report results."""
    print("=" * 100)
    print("COMPREHENSIVE HINGLISH TRANSLITERATION TEST SUITE")
    print("=" * 100)
    print(f"Testing {len(TEST_CASES)} cases...\n")
    
    passed = 0
    failed = 0
    failures = []
    
    for i, (devanagari, expected, description) in enumerate(TEST_CASES, 1):
        result = devanagari_to_hinglish(devanagari)
        
        # Normalize for comparison (lowercase, remove extra spaces/punctuation)
        result_norm = result.lower().replace(" ", "").replace("?", "").replace(".", "")
        expected_norm = expected.lower().replace(" ", "").replace("?", "").replace(".", "")
        
        # Check if match
        is_match = result_norm == expected_norm
        
        if is_match:
            passed += 1
            status = "✓ PASS"
        else:
            failed += 1
            status = "✗ FAIL"
            failures.append((i, devanagari, expected, result, description))
        
        print(f"{status} | Test {i:02d}: {description}")
        print(f"         Input:    {devanagari}")
        print(f"         Expected: {expected}")
        print(f"         Got:      {result}")
        if not is_match:
            print(f"         ⚠ MISMATCH!")
        print()
    
    # Summary
    print("=" * 100)
    print("TEST SUMMARY")
    print("=" * 100)
    print(f"Total tests:  {len(TEST_CASES)}")
    print(f"Passed:       {passed} ({100*passed//len(TEST_CASES)}%)")
    print(f"Failed:       {failed} ({100*failed//len(TEST_CASES)}%)")
    print()
    
    if failures:
        print("=" * 100)
        print("FAILED TESTS DETAILS")
        print("=" * 100)
        for i, devanagari, expected, result, description in failures:
            print(f"\nTest {i}: {description}")
            print(f"  Input:    {devanagari}")
            print(f"  Expected: {expected}")
            print(f"  Got:      {result}")
    
    print("\n" + "=" * 100)
    if failed == 0:
        print("🎉 ALL TESTS PASSED! 🎉")
    else:
        print(f"⚠ {failed} test(s) failed. Review above for details.")
    print("=" * 100)
    
    return passed, failed


if __name__ == "__main__":
    passed, failed = run_tests()
    exit(0 if failed == 0 else 1)
