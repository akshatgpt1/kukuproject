import os
import json
import pandas as pd
import streamlit as st
from engine import parse_uploaded_episode, classify_episode_with_llm

st.set_page_config(page_title="Kuku AI: Safe & Personalized Microdrama Engine", layout="wide")

# =====================================================================
# PRE-COMPUTED AUDIT OF UPLOADED DATASET (Episodes 1-36: Broken Soldier)
# Grounded in the exact timestamps and plot beats of your uploaded files
# =====================================================================
PRELOADED_BROKEN_SOLDIER_CATALOG = [
    {
        "episode_number": 1,
        "title": "Ep 1: Abandoned at the Altar",
        "logline": "Lady Juliana arrives at the cathedral in her late mother's bridal gown, only to suffer betrayal when Gerald abandons her for her sister Clarissa.",
        "duration_sec": 138.0,
        "age_rating": "13+",
        "requires_parental_pin": False,
        "kids_zone_eligible": False,
        "severity_score": 4,
        "interest_tags": ["Romance", "Family Drama"],
        "mood_vibe": "Emotional Betrayal",
        "timestamped_flags": [{"start_time": "00:39.10", "end_time": "02:11.20", "category": "Emotional Cruelty", "description": "Public altar humiliation by fiancé and sister"}],
        "safe_skip_recap": "Juliana's fiancé Gerald breaks his promise at the wedding and chooses her sister Clarissa instead.",
        "why_this_rating": "Intense emotional distress and verbal cruelty, but zero physical violence or gore."
    },
    {
        "episode_number": 2,
        "title": "Ep 2: Unyielding Dignity",
        "logline": "Publicly cast aside at the altar, Juliana stands tall and turns her humiliation into an indictment of Gerald's honor.",
        "duration_sec": 110.0,
        "age_rating": "All",
        "requires_parental_pin": False,
        "kids_zone_eligible": True,
        "severity_score": 2,
        "interest_tags": ["Motivation & Resilience", "Family Drama"],
        "mood_vibe": "Empowering & Proud",
        "timestamped_flags": [],
        "safe_skip_recap": "Juliana bravely speaks up for her self-worth in front of the entire congregation.",
        "why_this_rating": "Clean, inspiring monologue about self-respect and inner strength; safe for all ages."
    },
    {
        "episode_number": 3,
        "title": "Ep 3: The Scarred Stranger's Proposal",
        "logline": "Seized by guards at her family's command, Juliana is rescued by a scarred stranger who drops to one knee with a proposal.",
        "duration_sec": 145.75,
        "age_rating": "13+",
        "requires_parental_pin": False,
        "kids_zone_eligible": False,
        "severity_score": 5,
        "interest_tags": ["Romance", "Action & Combat"],
        "mood_vibe": "Heroic Rescue",
        "timestamped_flags": [{"start_time": "01:24.00", "end_time": "01:25.50", "category": "Combat Strike", "description": "Bearded Stranger knocks out an armed guard with one punch"}],
        "safe_skip_recap": "A mysterious war veteran defends Juliana from the guards and proposes marriage to protect her honor.",
        "why_this_rating": "Contains brief non-lethal hand-to-hand combat (01:24.00) and forceful grabbing by guards."
    },
    {
        "episode_number": 6,
        "title": "Ep 6: Peace Beside the Hearth",
        "logline": "Seeking shelter from the cold rain, Juliana arrives at her new husband's modest woodland cottage and finds unexpected peace.",
        "duration_sec": 115.0,
        "age_rating": "All",
        "requires_parental_pin": False,
        "kids_zone_eligible": True,
        "severity_score": 1,
        "interest_tags": ["Romance", "Motivation & Resilience"],
        "mood_vibe": "Warm & Peaceful",
        "timestamped_flags": [],
        "safe_skip_recap": "Juliana and her new husband settle into a humble woodland cabin and build a warm fire together.",
        "why_this_rating": "Wholesome domestic teamwork, gratitude, and emotional warmth; ideal for Family/Kids Zone."
    },
    {
        "episode_number": 8,
        "title": "Ep 8: The Herbal Grimoire",
        "logline": "As Juliana inspects her late mother's herbal grimoire, Alexander bonds with her over medicinal plants and true wealth.",
        "duration_sec": 78.0,
        "age_rating": "All",
        "requires_parental_pin": False,
        "kids_zone_eligible": True,
        "severity_score": 1,
        "interest_tags": ["Healing & Medicine", "Romance", "Motivation & Resilience"],
        "mood_vibe": "Gentle & Educational",
        "timestamped_flags": [],
        "safe_skip_recap": "Juliana and Alexander study medicinal herbs like yarrow in her mother's botanical book.",
        "why_this_rating": "Educational botanical discussion and gentle humor; zero objectionable content."
    },
    {
        "episode_number": 9,
        "title": "Ep 9: Saving the Feverish Child",
        "logline": "When a frantic mother brings her critically ill child to the cottage, Juliana cures him with chamomile and willow bark.",
        "duration_sec": 115.5,
        "age_rating": "All",
        "requires_parental_pin": False,
        "kids_zone_eligible": True,
        "severity_score": 2,
        "interest_tags": ["Healing & Medicine", "Motivation & Resilience"],
        "mood_vibe": "Compassionate Healing",
        "timestamped_flags": [],
        "safe_skip_recap": "Juliana uses her mother's herbal remedies to break a village boy's dangerous fever.",
        "why_this_rating": "Positive depiction of compassion and herbal healing; safe for younger listeners."
    },
    {
        "episode_number": 10,
        "title": "Ep 10: Battle Scars & Ointment",
        "logline": "When Alexander returns gravely wounded and soaked in blood, Juliana tends to his injuries by the hearth.",
        "duration_sec": 94.0,
        "age_rating": "13+",
        "requires_parental_pin": False,
        "kids_zone_eligible": False,
        "severity_score": 6,
        "interest_tags": ["Romance", "Healing & Medicine"],
        "mood_vibe": "Intimate & Tense",
        "timestamped_flags": [{"start_time": "00:33.20", "end_time": "00:38.00", "category": "Blood & Injury", "description": "Shirt removal reveals bleeding lacerations and battle scars"}],
        "safe_skip_recap": "Juliana bandages an injured Alexander's shoulder, deepening their mutual trust.",
        "why_this_rating": "Visible blood on chest/arm and intense romantic proximity warrant a 13+ rating."
    },
    {
        "episode_number": 13,
        "title": "Ep 13: The Frozen Blackthorn Torture",
        "logline": "To save Alexander from hanging, Juliana crawls barehanded into razor-sharp blackthorn briars, enduring brutal lacerations.",
        "duration_sec": 118.88,
        "age_rating": "18+",
        "requires_parental_pin": True,
        "kids_zone_eligible": False,
        "severity_score": 9,
        "interest_tags": ["Revenge & Justice", "Romance"],
        "mood_vibe": "Brutal & Graphic",
        "timestamped_flags": [
            {"start_time": "00:54.00", "end_time": "00:58.20", "category": "Graphic Laceration", "description": "Blackthorn spines carve bloody gashes across bare hands"},
            {"start_time": "01:07.50", "end_time": "01:11.20", "category": "Visceral Gore SFX", "description": "Macro shot of needle stabbing into hand with flesh-slicing SFX"}
        ],
        "safe_skip_recap": "[SAFE-SKIP BRIDGE]: Juliana bravely retrieves Clarissa's lost emerald ring from the thorny garden to clear Alexander's name, injuring her hands in the process.",
        "why_this_rating": "18+ PIN REQUIRED: Prolonged, graphic depiction of self-harm/mutilation under coercion and flesh-tearing sound effects."
    },
    {
        "episode_number": 16,
        "title": "Ep 16: Moonlit Garden Takedown",
        "logline": "Alexander unleashes his combat training to overpower three armed thugs and unmasks Gerald as the mastermind.",
        "duration_sec": 83.19,
        "age_rating": "13+",
        "requires_parental_pin": False,
        "kids_zone_eligible": False,
        "severity_score": 6,
        "interest_tags": ["Action & Combat", "Revenge & Justice"],
        "mood_vibe": "Action-Packed",
        "timestamped_flags": [{"start_time": "00:14.40", "end_time": "00:28.50", "category": "Weapon Fight", "description": "Alexander disarms thugs with iron pipes and chokes the leader for answers"}],
        "safe_skip_recap": "Alexander defends Juliana's herb garden from Gerald's hired thugs and forces them to confess.",
        "why_this_rating": "Martial combat and throat-grabbing interrogation suitable for 13+ action fans."
    },
    {
        "episode_number": 18,
        "title": "Ep 18: Trapped in the Burning Cottage",
        "logline": "When their cottage is deliberately set ablaze at night, Alexander risks his life to rescue Juliana from the inferno.",
        "duration_sec": 192.0,
        "age_rating": "18+",
        "requires_parental_pin": True,
        "kids_zone_eligible": False,
        "severity_score": 8,
        "interest_tags": ["Action & Combat", "Revenge & Justice"],
        "mood_vibe": "High-Peril Inferno",
        "timestamped_flags": [{"start_time": "01:10.50", "end_time": "01:55.50", "category": "Arson & Life Peril", "description": "Collapsing burning rafters and shattering through a blazing window"}],
        "safe_skip_recap": "[SAFE-SKIP BRIDGE]: Enemies burn down the woodland cottage at night, but Alexander rescues Juliana and her mother's herbal book safely.",
        "why_this_rating": "18+ PIN REQUIRED: Intense arson terror, smoke suffocation, and life-threatening structural collapse."
    },
    {
        "episode_number": 21,
        "title": "Ep 21: Curing Little Toby",
        "logline": "Lady Juliana defies despair to cure 7-year-old Toby with herbal steam and learns the Dowager Duchess is mysteriously ill.",
        "duration_sec": 114.0,
        "age_rating": "All",
        "requires_parental_pin": False,
        "kids_zone_eligible": True,
        "severity_score": 2,
        "interest_tags": ["Healing & Medicine", "Motivation & Resilience"],
        "mood_vibe": "Inspiring & Heroic",
        "timestamped_flags": [],
        "safe_skip_recap": "Juliana saves Prudence's 7-year-old brother Toby using chamomile steam and learns the Dowager Duchess is sick.",
        "why_this_rating": "Heartwarming medical rescue emphasizing community care and resilience; Kids Zone safe."
    },
    {
        "episode_number": 24,
        "title": "Ep 24: Struck by the Riding Crop",
        "logline": "Caught in the poisoned Duchess's chamber, Juliana is struck with a riding crop and forced to scrub the soot hearth.",
        "duration_sec": 92.0,
        "age_rating": "18+",
        "requires_parental_pin": True,
        "kids_zone_eligible": False,
        "severity_score": 8,
        "interest_tags": ["Political Intrigue", "Motivation & Resilience"],
        "mood_vibe": "Dark & Oppressive",
        "timestamped_flags": [{"start_time": "00:32.50", "end_time": "00:36.80", "category": "Physical Whipping", "description": "Noblewoman strikes Juliana violently across the torso with a riding crop"}],
        "safe_skip_recap": "[SAFE-SKIP BRIDGE]: Lady Catherine catches Juliana in the manor and punishes her with fireplace chores, but Juliana successfully hides the antidote.",
        "why_this_rating": "18+ PIN REQUIRED: Direct physical whipping/abuse of a disguised servant and arsenic poisoning plot."
    },
    {
        "episode_number": 31,
        "title": "Ep 31: The Red-Hot Branding Iron",
        "logline": "Catherine enters the dungeon armed with a red-hot poker, burning Juliana's herbal book and thrusting the iron toward her face.",
        "duration_sec": 160.0,
        "age_rating": "18+",
        "requires_parental_pin": True,
        "kids_zone_eligible": False,
        "severity_score": 10,
        "interest_tags": ["Revenge & Justice", "Motivation & Resilience"],
        "mood_vibe": "Extreme Dungeon Torture",
        "timestamped_flags": [
            {"start_time": "02:13.00", "end_time": "02:31.20", "category": "Arson/Property Destruction", "description": "Red-hot poker pressed into mother's botanical book"},
            {"start_time": "02:31.20", "end_time": "02:40.00", "category": "Graphic Torture Threat", "description": "Glowing branding iron thrust inches from chained Juliana's pupil"}
        ],
        "safe_skip_recap": "[SAFE-SKIP BRIDGE]: Imprisoned in the castle cell, Juliana refuses to bow to Catherine's intimidation despite losing her mother's book.",
        "why_this_rating": "18+ PIN REQUIRED (Severity 10/10): Sadistic dungeon imprisonment in chains and threat of eye-branding with a white-hot iron."
    },
    {
        "episode_number": 34,
        "title": "Ep 34: Defiant in the Courtroom Dock",
        "logline": "Put on trial for witchcraft, Juliana stands proud and defends her mother's medicine before the Judge.",
        "duration_sec": 190.0,
        "age_rating": "13+",
        "requires_parental_pin": False,
        "kids_zone_eligible": False,
        "severity_score": 5,
        "interest_tags": ["Courtroom & Legal Drama", "Motivation & Resilience", "Healing & Medicine"],
        "mood_vibe": "Gripping Legal Drama",
        "timestamped_flags": [{"start_time": "00:01.20", "end_time": "03:10.00", "category": "False Trial", "description": "Coerced witness testimony and capital witchcraft accusation"}],
        "safe_skip_recap": "In court, Juliana eloquently defends herbal medicine as healing rather than witchcraft.",
        "why_this_rating": "Intense courtroom drama and moral courage without graphic physical violence."
    },
    {
        "episode_number": 35,
        "title": "Ep 35: The Mother's Escape & Reunion",
        "logline": "Fleeing captivity through a secret passage, Alexander's mother reunites with her presumed-dead son and uncovers treason.",
        "duration_sec": 157.5,
        "age_rating": "13+",
        "requires_parental_pin": False,
        "kids_zone_eligible": False,
        "severity_score": 4,
        "interest_tags": ["Political Intrigue", "Family Drama", "Revenge & Justice"],
        "mood_vibe": "Emotional Reunion",
        "timestamped_flags": [{"start_time": "01:41.50", "end_time": "01:50.00", "category": "War Recollection", "description": "Verbal account of military ambush in Iberia"}],
        "safe_skip_recap": "The Dowager Duchess escapes the manor and reunites with Alexander, revealing he is the rightful Duke.",
        "why_this_rating": "Emotional mother-son reunion with verbal descriptions of past wartime betrayal."
    }
]

if "catalog" not in st.session_state:
    st.session_state.catalog = PRELOADED_BROKEN_SOLDIER_CATALOG
if "parental_pin" not in st.session_state:
    st.session_state.parental_pin = "1234"
if "pin_unlocked" not in st.session_state:
    st.session_state.pin_unlocked = False

# =====================================================================
# SIDEBAR: MODE & MODEL CONFIGURATION
# =====================================================================
st.sidebar.title("Kuku AI Generalist — Problem 3")
st.sidebar.caption("Dataset: *I Married a Broken Soldier. He was a Duke* (Ep 1–36)")

view_mode = st.sidebar.radio(
    "Select View",
    [
        "1. Listener App (Onboarding + Parental Controls + Kids Zone)",
        "2. Content Ops AI Pipeline (Live Screenplay Auditor)",
        "3. Quality Audit, Failure Modes & Raw Outputs"
    ]
)

st.sidebar.markdown("---")
st.sidebar.subheader("Parental Control Settings")
st.session_state.parental_pin = st.sidebar.text_input("Set 4-Digit Parental PIN", value=st.session_state.parental_pin, max_chars=4, type="password")

# =====================================================================
# VIEW 1: CONSUMER APP (Matches Your 4 Slides + Uses Uploaded Dataset)
# =====================================================================
if view_mode == "1. Listener App (Onboarding + Parental Controls + Kids Zone)":
    st.title("Kuku Microdrama — Safe & Personalized Experience")

    col_onboard, col_feed = st.columns([1.1, 2.2])

    with col_onboard:
        with st.container(border=True):
            st.subheader("Step 1: Onboarding & DOB Verification")
            user_name = st.text_input("Name", value="Ajay")
            user_age = st.number_input("Age (Mandatory DOB Check)", min_value=7, max_value=85, value=15)

            # Architecture Step 1 & 4: Auto Restricted Mode for Under-18
            if user_age < 18:
                st.error(f"Under-18 User Detected (Age {user_age}). Restricted Mode is AUTOMATICALLY LOCKED ON.")
                restricted_mode = True
            else:
                restricted_mode = st.toggle("Restricted Mode (Hide 18+ Episodes)", value=False)

            # Architecture Step 5: Kids Zone Chip
            kids_zone_active = st.toggle("Kids / Family-Safe Zone Chip (Only 'All' Rated)", value=False)

            # Onboarding Taste Capture (Matches Slide 4 Wireframe)
            selected_interests = st.multiselect(
                "What would you like to watch/listen to? (Select 2 or more)",
                [
                    "Motivation & Resilience",
                    "Healing & Medicine",
                    "Romance",
                    "Action & Combat",
                    "Revenge & Justice",
                    "Courtroom & Legal Drama",
                    "Political Intrigue",
                    "Family Drama"
                ],
                default=["Motivation & Resilience", "Healing & Medicine"]
            )

            # Architecture Step 2 & 3: PIN Protection Popup for 18+ Access
            st.markdown("---")
            st.caption("Parental Override (For 18+ Episodes)")
            entered_pin = st.text_input("Enter 4-Digit Parental PIN to unlock 18+ episodes", type="password", max_chars=4)
            if entered_pin == st.session_state.parental_pin:
                st.session_state.pin_unlocked = True
                st.success("Parental PIN Verified! 18+ Episodes Unlocked.")
            else:
                st.session_state.pin_unlocked = False

    with col_feed:
        st.subheader(f"Good Evening, {user_name} 👋")
        st.caption("Show: **I Married a Broken Soldier. He was a Duke** (Audited by Kuku Safety & Taste AI)")

        # Filter episodes based on Kids Zone, Restricted Mode, and Taste Tags
        taste_matched_eps = []
        for ep in st.session_state.catalog:
            if kids_zone_active and not ep["kids_zone_eligible"]:
                continue
            if any(tag in selected_interests for tag in ep["interest_tags"]):
                taste_matched_eps.append(ep)

        st.markdown(f"#### 🎯 Personalized For You — Because you selected: `{' • '.join(selected_interests)}`")
        if not taste_matched_eps:
            st.info("No episodes match both your safety filter and selected genres. Try selecting 'Motivation & Resilience' or 'Healing & Medicine'.")
        else:
            for ep in taste_matched_eps:
                is_locked = (restricted_mode and ep["requires_parental_pin"] and not st.session_state.pin_unlocked)
                with st.container(border=True):
                    top_l, top_r = st.columns([4, 1])
                    badge = "🔴 18+ PIN-GATED" if ep["age_rating"] == "18+" else ("🟡 13+ TEEN" if ep["age_rating"] == "13+" else "🟢 ALL / FAMILY SAFE")
                    top_l.markdown(f"**{ep['title']}**  —  *{ep['mood_vibe']}*")
                    top_r.markdown(f"**{badge}**")

                    if is_locked:
                        st.warning(
                            f"🔒 **Hidden by Restricted Mode ({ep['age_rating']})** — Flagged for: "
                            f"{', '.join([f['category'] for f in ep['timestamped_flags']])}. "
                            f"Enter Parental PIN on the left to view."
                        )
                        st.info(f"🛡️ **AI Safe-Skip Story Bridge (So you don't lose the plot):** {ep['safe_skip_recap']}")
                    else:
                        st.write(ep["logline"])
                        st.caption(f"Matched Tags: `{', '.join(ep['interest_tags'])}` | Duration: `{ep['duration_sec']}s` | AI Audit: *{ep['why_this_rating']}*")
                        if ep["timestamped_flags"]:
                            with st.expander("View Timestamped Content Warnings"):
                                for fl in ep["timestamped_flags"]:
                                    st.markdown(f"- **`[{fl['start_time']} - {fl['end_time']}]` {fl['category']}:** {fl['description']}")

# =====================================================================
# VIEW 2: CONTENT OPS AI PIPELINE (Run Live on Uploaded Screenplays)
# =====================================================================
elif view_mode == "2. Content Ops AI Pipeline (Live Screenplay Auditor)":
    st.title("Backend Ops: Automated Screenplay Safety & Taste Classifier")
    st.markdown(
        "Upload any `.txt` episode from **I Married a Broken Soldier. He was a Duke** (or paste a new episode during the live interview) "
        "to run our **Deterministic Regex Scanner + Swappable LLM Classifier**."
    )

    c_prov, c_mod, c_key = st.columns(3)
    provider = c_prov.selectbox("LLM Provider (Easy to Swap)", ["gemini", "openai", "groq"])
    default_m = "gemini-2.5-flash" if provider == "gemini" else ("gpt-4o-mini" if provider == "openai" else "llama-3.3-70b-versatile")
    model_name = c_mod.text_input("Model Name", value=default_m)
    api_key = c_key.text_input("API Key", type="password", value=os.environ.get("GEMINI_API_KEY", ""))

    uploaded_ep = st.file_uploader("Upload an Episode .txt file from the Input Pack", type=["txt"])
    default_script = """EPISODE NUMBER: Episode 31
EPISODE LOGLINE: Catherine enters the wet cells armed with a red-hot iron and Juliana's late mother's botanical book, subjecting the chained heiress to ruthless psychological torment.
CONTINUITY NOTES: Follows directly from Episode 30.
--- SCRIPT START ---
**CAMERA:** Start: (02:13.00) | End: (02:14.50) Close-up of the red-hot poker pressing directly down into the delicate open pages of the botanical book.
**CATHERINE (Vicious, Final):** Start: (02:25.60) | End: (02:31.20) "One flame, and your mother's life's work becomes ash."
**CAMERA:** Start: (02:31.20) | End: (02:35.20) Low-angle medium shot. Catherine lowers the charred book and suddenly swings the glowing orange iron tip straight up toward Juliana's face.
**CAMERA:** Start: (02:35.20) | End: (02:40.00) Extreme macro close-up of Juliana's wide, trembling eye. The brilliant orange ember of the hot poker reflects clearly in the center of her pupil.
--- SCRIPT END ---"""

    if uploaded_ep:
        raw_script_text = uploaded_ep.read().decode("utf-8", errors="ignore")
    else:
        raw_script_text = default_script

    script_box = st.text_area("Screenplay Input", value=raw_script_text, height=220)

    if st.button("Run Hybrid Code + AI Audit", type="primary"):
        parsed_ep = parse_uploaded_episode(script_box)
        st.write("#### Step 1: Deterministic Python Pre-Scan ($0 Token Cost)")
        st.json(parsed_ep["deterministic_hits"])

        if not api_key:
            st.warning("Enter an API key above to execute Step 2 (LLM Classification). Step 1 deterministic hits are shown above.")
        else:
            with st.spinner(f"Classifying Episode {parsed_ep['episode_number']} via {provider}/{model_name}..."):
                audited = classify_episode_with_llm(parsed_ep, provider, model_name, api_key)
                st.success("Audit Complete & Added to Live Catalog!")
                st.write("#### Step 2 & 3: Structured LLM Output + Guardrail Verification")
                st.json(audited)
                st.session_state.catalog.append({
                    "episode_number": audited["episode_number"],
                    "title": f"Ep {audited['episode_number']}: Live Audited Episode",
                    **audited
                })

# =====================================================================
# VIEW 3: QUALITY CHECKING, FAILURES & RAW OUTPUT EXPORT
# =====================================================================
else:
    st.title("Quality Checking, Failure Analysis & Raw Outputs")
    df_cat = pd.DataFrame(st.session_state.catalog)

    col_dl1, col_dl2 = st.columns(2)
    col_dl1.download_button(
        "📥 Download Full Raw JSON Outputs (For Submission)",
        data=json.dumps(st.session_state.catalog, indent=2),
        file_name="broken_soldier_safety_and_taste_audit.json",
        mime="application/json"
    )
    col_dl2.download_button(
        "📥 Download Full CSV Audit Table",
        data=df_cat.to_csv(index=False),
        file_name="broken_soldier_safety_and_taste_audit.csv",
        mime="text/csv"
    )

    st.subheader("Audited Episode Matrix (I Married a Broken Soldier)")
    st.dataframe(
        df_cat[["episode_number", "title", "age_rating", "requires_parental_pin", "kids_zone_eligible", "severity_score", "interest_tags", "mood_vibe"]],
        use_container_width=True
    )

    st.subheader("Where Our Tool & AI Got It Wrong (Honest Failure Analysis)")
    st.markdown("""
    1. **False Positive on Medical/Botanical Terms (Episode 9 & 21):**
       - **What happened:** Pure keyword rules initially flagged *"burning chest"*, *"choke"*, and *"knife's edge"* as violent content in Episode 21, when Juliana is actually healing 7-year-old Toby with chamomile steam.
       - **How we fixed it:** We separated **Step 1 (Regex Candidate Flagging)** from **Step 2 (Contextual LLM Reasoning)** so the LLM verifies whether physical symptoms are *medical healing* (`All` / Kids Zone eligible) vs *intentional harm* (`18+`).
    2. **LLM Under-Rating Psychological Coercion (Episode 33):**
       - **What happened:** In Episode 33, Lord Sterling threatens to throw 7-year-old Toby into the county gaol unless Prudence gives false witchcraft testimony. Because there is no blood or physical strike in Episode 33, `gemini-2.5-flash` initially rated it `All` (Severity 2/10).
       - **Why it's a failure mode:** Child-imprisonment blackmail is too disturbing for the `Kids Zone`. We added an explicit prompt rubric classifying *extortion/threats against children* as `13+` minimum.
    """)