import os
import re
import glob
import json
import zipfile
from typing import List, Dict, Any
from pydantic import BaseModel, Field

from google import genai
from google.genai import types
from openai import OpenAI

# =====================================================================
# 1. STRUCTURED OUTPUT SCHEMA (Pydantic)
# =====================================================================

class TimestampedFlag(BaseModel):
    start_time: str = Field(description="Start timestamp e.g. 00:32.50")
    end_time: str = Field(description="End timestamp e.g. 00:36.80")
    category: str = Field(description="e.g., Graphic Torture, Weapon Violence, Poisoning, Self-Harm, Emotional Abuse")
    description: str = Field(description="What happens in this exact timestamp window")

class EpisodeAuditMetadata(BaseModel):
    episode_number: int
    age_rating: str = Field(description="Strictly 'All' (Kids/Family Safe), '13+' (Teen/Mild Drama), or '18+' (Explicit Violence/Torture/Poison)")
    requires_parental_pin: bool = Field(description="True if age_rating is '18+'")
    kids_zone_eligible: bool = Field(description="True ONLY if age_rating is 'All' and free of violence/abuse")
    severity_score: int = Field(description="1 to 10 maturity/intensity score")
    interest_tags: List[str] = Field(
        description="Select 2-3 matching user onboarding tags from: "
        "['Romance', 'Motivation & Resilience', 'Healing & Medicine', 'Action & Combat', 'Revenge & Justice', 'Courtroom & Legal Drama', 'Political Intrigue', 'Family Drama']"
    )
    mood_vibe: str = Field(description="Short 2-3 word vibe e.g. 'Heartwarming & Peaceful', 'High-Stakes Suspense', 'Dark & Brutal'")
    timestamped_flags: List[TimestampedFlag] = Field(description="Exact timestamps of mature or intense moments")
    safe_skip_recap: str = Field(
        description="A gentle, non-graphic 1-sentence plot bridge so an Under-18 / Restricted Mode viewer can skip this 18+ episode without losing the story thread."
    )
    why_this_rating: str = Field(description="1-line explanation of why this rating was assigned")

# =====================================================================
# 2. DETERMINISTIC CODE LAYER ($0 Cost Regex Parser & Guardrail)
# =====================================================================

SEVERITY_LEXICON = {
    "Graphic Torture & Branding (18+)": [r"branding iron", r"hot poker", r"white-hot", r"red-hot", r"cornea", r"wet cells"],
    "Severe Blood & Laceration (18+)": [r"blood-soaked", r"bloodied", r"slicing through flesh", r"puncture wounds", r"shredded to ribbons", r"bleeding gashes"],
    "Poison & Lethal Harm (18+)": [r"arsenic", r"poisoning", r"gallows", r"hangs from the gallows", r"noose"],
    "Physical Assault & Abuse (13+/18+)": [r"riding crop", r"whip crack", r"welt", r"slams him violently", r"bone-rattling punch", r"choking"],
    "Arson & Life Peril (13+/18+)": [r"inferno", r" engulfed in roaring fire", r"burning rafters"]
}

def parse_uploaded_episode(raw_text: str, fallback_ep_num: int = 1) -> Dict[str, Any]:
    """Deterministically parses the 'I Married a Broken Soldier' screenplay format."""
    ep_match = re.search(r"EPISODE NUMBER:\s*Episode\s*(\d+)", raw_text, re.IGNORECASE)
    ep_num = int(ep_match.group(1)) if ep_match else fallback_ep_num

    logline_match = re.search(r"EPISODE LOGLINE:\s*(.+?)(?:CONTINUITY NOTES:|--- SCRIPT START ---)", raw_text, re.DOTALL)
    logline = logline_match.group(1).strip().replace("\n", " ") if logline_match else "No logline found."

    cont_match = re.search(r"CONTINUITY NOTES:\s*(.+?)(?:--- SCRIPT START ---)", raw_text, re.DOTALL)
    continuity = cont_match.group(1).strip().replace("\n", " ") if cont_match else ""

    # Calculate total duration from the final timestamp in the script
    timestamps = re.findall(r"End:\s*\((\d{2}):(\d{2}\.\d{2})\)", raw_text)
    if timestamps:
        last_min, last_sec = timestamps[-1]
        duration_sec = round(int(last_min) * 60 + float(last_sec), 1)
    else:
        duration_sec = 120.0

    # Extract timestamped blocks for deterministic keyword scanning
    deterministic_hits = []
    for category, patterns in SEVERITY_LEXICON.items():
        for pat in patterns:
            for m in re.finditer(pat, raw_text, re.IGNORECASE):
                # Find nearest preceding timestamp
                preceding_text = raw_text[max(0, m.start() - 250):m.start()]
                ts_find = re.findall(r"Start:\s*\((\d{2}:\d{2}\.\d{2})\)\s*\|\s*End:\s*\((\d{2}:\d{2}\.\d{2})\)", preceding_text)
                ts_range = f"{ts_find[-1][0]} - {ts_find[-1][1]}" if ts_find else "In Episode"
                deterministic_hits.append({
                    "category": category,
                    "matched_term": m.group(0),
                    "timestamp": ts_range
                })

    return {
        "episode_number": ep_num,
        "logline": logline,
        "continuity_notes": continuity,
        "duration_sec": duration_sec,
        "deterministic_hits": deterministic_hits,
        "raw_text": raw_text
    }

def enforce_deterministic_safety_guardrail(ai_result: EpisodeAuditMetadata, parsed_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    HYBRID CODE GUARDRAIL:
    If the LLM hallucinates a '13+' or 'All' rating on an episode where our deterministic
    scanner detected 'Graphic Torture & Branding (18+)' or 'Poison & Lethal Harm (18+)',
    Python overrides the rating to '18+' and locks it behind the Parental PIN.
    """
    data = ai_result.model_dump()
    hits = parsed_info["deterministic_hits"]
    severe_categories = {"Graphic Torture & Branding (18+)", "Severe Blood & Laceration (18+)", "Poison & Lethal Harm (18+)"}

    triggered_severe = [h for h in hits if h["category"] in severe_categories]
    guardrail_override = False

    if triggered_severe and data["age_rating"] != "18+":
        data["age_rating"] = "18+"
        data["requires_parental_pin"] = True
        data["kids_zone_eligible"] = False
        data["severity_score"] = max(data["severity_score"], 8)
        guardrail_override = True

    if data["age_rating"] == "18+":
        data["requires_parental_pin"] = True
        data["kids_zone_eligible"] = False

    data["logline"] = parsed_info["logline"]
    data["duration_sec"] = parsed_info["duration_sec"]
    data["deterministic_rule_hits"] = hits
    data["guardrail_overrode_llm"] = guardrail_override
    return data

# =====================================================================
# 3. SWAPPABLE AI LAYER (Gemini / OpenAI / Groq)
# =====================================================================

SYSTEM_PROMPT = """You are the Trust, Safety & Personalization AI Architect for Kuku TV.
Analyze the provided microdrama screenplay and output structured JSON metadata for:
1. MANDATORY AGE VERIFICATION & PARENTAL CONTROLS:
   - 'All': Safe for Kids Zone & family listening (e.g., warm hearthside bonding, herbal healing, gentle resilience).
   - '13+': Teen melodrama (e.g., verbal altar insults, social humiliation, mild scuffles without gore).
   - '18+': Requires 4-digit Parental PIN (e.g., riding-crop whipping, branding-iron torture, deep thorn blood lacerations, arsenic poisoning, arson terror, threats of hanging).
2. ONBOARDING TASTE TAGS:
   Tag the episode with 2-3 genres from:
   ['Romance', 'Motivation & Resilience', 'Healing & Medicine', 'Action & Combat', 'Revenge & Justice', 'Courtroom & Legal Drama', 'Political Intrigue', 'Family Drama']
3. SAFE-SKIP RECAP FOR UNDER-18 USERS:
   Write a 1-sentence non-graphic bridge summary so an underage user with Restricted Mode ON can understand the story continuity even when an 18+ episode is hidden.
"""

def classify_episode_with_llm(
    parsed_ep: Dict[str, Any],
    provider: str = "gemini",
    model_name: str = "gemini-2.5-flash",
    api_key: str = ""
) -> Dict[str, Any]:
    prompt = f"""Analyze Episode {parsed_ep['episode_number']} of 'I Married a Broken Soldier. He was a Duke'.
Deterministic Regex Scanner pre-detected {len(parsed_ep['deterministic_hits'])} potential maturity triggers: {json.dumps(parsed_ep['deterministic_hits'][:8])}

SCREENPLAY:
{parsed_ep['raw_text']}
"""
    if provider.lower() == "gemini":
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=EpisodeAuditMetadata,
                temperature=0.1
            )
        )
        ai_obj = EpisodeAuditMetadata.model_validate_json(resp.text)

    elif provider.lower() in ["openai", "groq"]:
        base_url = "https://api.groq.com/openai/v1" if provider.lower() == "groq" else None
        client = OpenAI(api_key=api_key, base_url=base_url)
        comp = client.beta.chat.completions.parse(
            model=model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            response_format=EpisodeAuditMetadata,
            temperature=0.1
        )
        ai_obj = comp.choices[0].message.parsed
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    return enforce_deterministic_safety_guardrail(ai_obj, parsed_ep)

# =====================================================================
# 4. DATASET LOADER (Loads .zip, Folder of .txt, or Concatenated Stream)
# =====================================================================

def load_broken_soldier_dataset(path: str) -> Dict[int, Dict[str, Any]]:
    """Loads all episodes from the uploaded zip/folder/file."""
    episodes = {}
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path, "r") as z:
            for fname in sorted(z.namelist()):
                if fname.endswith(".txt") and "episode-" in fname.lower():
                    raw = z.read(fname).decode("utf-8", errors="ignore")
                    parsed = parse_uploaded_episode(raw)
                    episodes[parsed["episode_number"]] = parsed
    elif os.path.isdir(path):
        for fpath in sorted(glob.glob(os.path.join(path, "*.txt"))):
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                parsed = parse_uploaded_episode(f.read())
                episodes[parsed["episode_number"]] = parsed
    elif os.path.isfile(path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        chunks = re.split(r"PK\s+.*?episode-\d+-Episode\s+\d+\.txt", content)
        for idx, ch in enumerate(chunks):
            if "EPISODE NUMBER:" in ch:
                parsed = parse_uploaded_episode(ch, idx)
                episodes[parsed["episode_number"]] = parsed
    return dict(sorted(episodes.items()))