# -*- coding: utf-8 -*-
"""
ALIRA languages — user apni language chune, ALIRA usi language mein sunegi aur bolegi.

    import ALIRA_lang as L
    L.current()                 # ("hi", "Hindi", "हिन्दी")  ya None (= Auto / Hinglish default)
    L.set_language("Spanish")   # naam, native naam ya code se
    L.prompt_block()            # system prompt ke liye saaf instruction ("" agar Auto)

Gemini Live voice dhai sau se zyada bhashaon ko samajhta hai (bol-chaal ki quality alag-alag hoti hai);
yahan sabse zyada bolne wali duniya ki bhashaon ki lambi list hai. Prefs key: "language".
"""
import re
import alira_prefs as prefs

AUTO = "auto"

# (code, English naam, native naam)
LANGUAGES = [
    # ── Bharat ──
    ("hi", "Hindi", "हिन्दी"), ("en-IN", "English (India)", "English (India)"), ("bn", "Bengali", "বাংলা"),
    ("te", "Telugu", "తెలుగు"), ("mr", "Marathi", "मराठी"), ("ta", "Tamil", "தமிழ்"), ("gu", "Gujarati", "ગુજરાતી"),
    ("kn", "Kannada", "ಕನ್ನಡ"), ("ml", "Malayalam", "മലയാളം"), ("pa", "Punjabi", "ਪੰਜਾਬੀ"), ("or", "Odia", "ଓଡ଼ିଆ"),
    ("as", "Assamese", "অসমীয়া"), ("ur", "Urdu", "اردو"), ("ne", "Nepali", "नेपाली"), ("sa", "Sanskrit", "संस्कृतम्"),
    ("sd", "Sindhi", "سنڌي"), ("ks", "Kashmiri", "کٲشُر"), ("kok", "Konkani", "कोंकणी"), ("mai", "Maithili", "मैथिली"),
    ("doi", "Dogri", "डोगरी"), ("mni", "Manipuri (Meitei)", "ꯃꯤꯇꯩꯂꯣꯟ"), ("brx", "Bodo", "बड़ो"), ("sat", "Santali", "ᱥᱟᱱᱛᱟᱲᱤ"),
    ("bho", "Bhojpuri", "भोजपुरी"), ("raj", "Rajasthani", "राजस्थानी"), ("hne", "Chhattisgarhi", "छत्तीसगढ़ी"),
    ("mag", "Magahi", "मगही"), ("awa", "Awadhi", "अवधी"), ("tcy", "Tulu", "ತುಳು"),
    # ── English & Europe ──
    ("en-US", "English (US)", "English (US)"), ("en-GB", "English (UK)", "English (UK)"), ("en-AU", "English (Australia)", "English (Australia)"),
    ("es", "Spanish", "Español"), ("es-MX", "Spanish (Mexico)", "Español (México)"), ("fr", "French", "Français"),
    ("fr-CA", "French (Canada)", "Français (Canada)"), ("de", "German", "Deutsch"), ("it", "Italian", "Italiano"),
    ("pt-BR", "Portuguese (Brazil)", "Português (Brasil)"), ("pt-PT", "Portuguese (Portugal)", "Português (Portugal)"),
    ("nl", "Dutch", "Nederlands"), ("sv", "Swedish", "Svenska"), ("da", "Danish", "Dansk"), ("no", "Norwegian", "Norsk"),
    ("fi", "Finnish", "Suomi"), ("is", "Icelandic", "Íslenska"), ("ru", "Russian", "Русский"), ("uk", "Ukrainian", "Українська"),
    ("pl", "Polish", "Polski"), ("cs", "Czech", "Čeština"), ("sk", "Slovak", "Slovenčina"), ("hu", "HungTABBUn", "Magyar"),
    ("ro", "Romanian", "Română"), ("bg", "BulgTABBUn", "Български"), ("el", "Greek", "Ελληνικά"), ("sr", "Serbian", "Српски"),
    ("hr", "Croatian", "Hrvatski"), ("bs", "Bosnian", "Bosanski"), ("sl", "Slovenian", "Slovenščina"), ("mk", "Macedonian", "Македонски"),
    ("sq", "Albanian", "Shqip"), ("lt", "Lithuanian", "Lietuvių"), ("lv", "Latvian", "Latviešu"), ("et", "Estonian", "Eesti"),
    ("be", "Belarusian", "Беларуская"), ("ca", "Catalan", "Català"), ("eu", "Basque", "Euskara"), ("gl", "Galician", "Galego"),
    ("ga", "Irish", "Gaeilge"), ("cy", "Welsh", "Cymraeg"), ("gd", "Scottish Gaelic", "Gàidhlig"), ("mt", "Maltese", "Malti"),
    ("lb", "Luxembourgish", "Lëtzebuergesch"), ("br", "Breton", "Brezhoneg"), ("la", "Latin", "Latina"), ("eo", "Esperanto", "Esperanto"),
    # ── Asia ──
    ("zh-CN", "Chinese (Mandarin, Simplified)", "简体中文"), ("zh-TW", "Chinese (Traditional)", "繁體中文"), ("yue", "Cantonese", "粵語"),
    ("ja", "Japanese", "日本語"), ("ko", "Korean", "한국어"), ("vi", "Vietnamese", "Tiếng Việt"), ("th", "Thai", "ไทย"),
    ("id", "Indonesian", "Bahasa Indonesia"), ("ms", "Malay", "Bahasa Melayu"), ("fil", "Filipino (Tagalog)", "Filipino"),
    ("my", "Burmese", "မြန်မာ"), ("km", "Khmer", "ខ្មែរ"), ("lo", "Lao", "ລາວ"), ("si", "Sinhala", "සිංහල"),
    ("mn", "Mongolian", "Монгол"), ("bo", "Tibetan", "བོད་སྐད།"), ("ug", "Uyghur", "ئۇيغۇرچە"), ("jv", "Javanese", "Basa Jawa"),
    ("su", "Sundanese", "Basa Sunda"), ("ceb", "Cebuano", "Cebuano"), ("ilo", "Ilocano", "Ilokano"), ("hmn", "Hmong", "Hmoob"),
    # ── Madhya Poorv, Central Asia, Caucasus ──
    ("ar", "Arabic", "العربية"), ("ar-EG", "Arabic (Egypt)", "العربية (مصر)"), ("he", "Hebrew", "עברית"), ("fa", "Persian (Farsi)", "فارسی"),
    ("tr", "Turkish", "Türkçe"), ("ku", "Kurdish", "Kurdî"), ("ps", "Pashto", "پښتو"), ("prs", "Dari", "دری"), ("az", "Azerbaijani", "Azərbaycanca"),
    ("hy", "Armenian", "Հայերեն"), ("ka", "Georgian", "ქართული"), ("kk", "Kazakh", "Қазақша"), ("uz", "Uzbek", "Oʻzbekcha"),
    ("ky", "Kyrgyz", "Кыргызча"), ("tg", "Tajik", "Тоҷикӣ"), ("tk", "Turkmen", "Türkmençe"), ("tt", "Tatar", "Татарча"),
    # ── Africa ──
    ("sw", "Swahili", "Kiswahili"), ("am", "Amharic", "አማርኛ"), ("ha", "Hausa", "Hausa"), ("yo", "Yoruba", "Yorùbá"), ("ig", "Igbo", "Igbo"),
    ("zu", "Zulu", "isiZulu"), ("xh", "Xhosa", "isiXhosa"), ("af", "Afrikaans", "Afrikaans"), ("st", "Sesotho", "Sesotho"),
    ("tn", "Tswana", "Setswana"), ("sn", "Shona", "chiShona"), ("so", "Somali", "Soomaali"), ("rw", "Kinyarwanda", "Ikinyarwanda"),
    ("mg", "Malagasy", "Malagasy"), ("ny", "Chichewa", "Chichewa"), ("wo", "Wolof", "Wolof"), ("ti", "Tigrinya", "ትግርኛ"),
    ("om", "Oromo", "Afaan Oromoo"), ("lg", "Luganda", "Luganda"), ("ln", "Lingala", "Lingála"), ("ff", "Fula", "Fulfulde"),
    ("ber", "Berber (Tamazight)", "ⵜⴰⵎⴰⵣⵉⵖⵜ"),
    # ── Americas & Pacific ──
    ("ht", "Haitian Creole", "Kreyòl ayisyen"), ("qu", "Quechua", "Runasimi"), ("gn", "Guarani", "Avañeʼẽ"), ("ay", "Aymara", "Aymar aru"),
    ("haw", "Hawaiian", "ʻŌlelo Hawaiʻi"), ("mi", "Maori", "Te Reo Māori"), ("sm", "Samoan", "Gagana Samoa"), ("to", "Tongan", "Lea faka-Tonga"),
    ("fj", "Fijian", "Vosa Vakaviti"), ("yi", "Yiddish", "ייִדיש"),
    # ── Mixed ──
    ("hi-Latn", "Hinglish (Hindi + English)", "Hinglish"),
]

_BY_KEY = {}
for _c, _e, _n in LANGUAGES:
    for _k in (_c, _e, _n):
        _BY_KEY.setdefault(re.sub(r"[^\w]+", "", _k.lower()), (_c, _e, _n))
_BY_KEY.update({"hinglish": ("hi-Latn", "Hinglish (Hindi + English)", "Hinglish"), "english": ("en-US", "English (US)", "English (US)"),
                "chinese": ("zh-CN", "Chinese (Mandarin, Simplified)", "简体中文"), "mandarin": ("zh-CN", "Chinese (Mandarin, Simplified)", "简体中文"),
                "portuguese": ("pt-BR", "Portuguese (Brazil)", "Português (Brasil)"), "farsi": ("fa", "Persian (Farsi)", "فارسی"),
                "tagalog": ("fil", "Filipino (Tagalog)", "Filipino"), "punjabi": ("pa", "Punjabi", "ਪੰਜਾਬੀ"),
                "arabic": ("ar", "Arabic", "العربية"), "french": ("fr", "French", "Français")})


def display(item) -> str:
    c, e, n = item
    return e if e == n else f"{e} — {n}"


def find(text):
    """Naam / native naam / code se language dhundo. Nahi mili to None."""
    k = re.sub(r"[^\w]+", "", str(text or "").lower())
    if not k or k in ("auto", "default"):
        return None
    if k in _BY_KEY:
        return _BY_KEY[k]
    for key, v in _BY_KEY.items():                      # "spanish language" / "in japanese" jaise
        if len(key) > 4 and key in k:
            return v
    return None


def current():
    """Chuni hui language (code, English, native) — Auto ho to None."""
    return find(prefs.get("language", AUTO))


def set_language(text):
    """Language save karo. 'auto' se reset. Return: (code, English, native) / None (auto). Galat naam par ValueError."""
    k = str(text or "").strip().lower()
    if k in ("", "auto", "default", "reset"):
        prefs.set_("language", AUTO)
        return None
    it = find(text)
    if not it:
        raise ValueError(f"'{text}' language list mein nahi mili")
    prefs.set_("language", it[0])
    return it


def prompt_block() -> str:
    it = current()
    if not it:
        return ""
    c, e, n = it
    if c == "hi-Latn":
        return ""                                       # default Hinglish persona pehle se hai
    return (
        f"\n## LANGUAGE (SABSE ZAROORI — baaki sab rules se upar):\n"
        f"- User ne apni language **{e} ({n})** chuni hai. Ab se SIRF {e} mein bolo aur likho — har jawab, greeting, "
        f"error, tool ke baad ka confirmation, sab kuch {e} mein.\n"
        f"- Is prompt ke Hinglish/Hindi example-shabdon ko copy mat karo; unka matlab samajh ke {e} mein hi bolo. "
        f"Natural, shuddh aur bol-chaal wali {e} use karo (script bhi sahi: {n}). Mushkil ya technical shabd chhod ke seedhe sahi {e} shabd lo.\n"
        f"- User koi doosri language mein bole to bhi samajh lo, par jawab {e} mein hi do — jab tak user khud na kahe "
        f"(jaise 'ab English mein bolo'); tab `set_language` tool se language badal do.\n"
        f"- Naam, app ke naam (Spotify, Chrome), website/URL aur code jaisa hai waisa hi rakho (translate mat karo).\n"
    )
