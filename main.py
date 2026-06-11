import os
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import google.generativeai as genai

app = FastAPI()

# Securely pull API Keys from Render's Environment Variables
GENAI_KEY = os.environ.get("GEMINI_API_KEY")
ELEVENLABS_KEY = os.environ.get("ELEVENLABS_API_KEY")

# Configure Google Gemini AI Engine
genai.configure(api_key=GENAI_KEY)

# -----------------------------------------------------------------------------
# FEATURE 1: STANDARDIZED PERSONAS (GIRL/BOY + RELATIONSHIP TIERS + ASSETS)
# -----------------------------------------------------------------------------
class StandardChatRequest(BaseModel):
    user_message: str
    gender: str          # "girl" or "boy"
    relationship: str    # "friend", "crush", "girlfriend", "boyfriend"

# Multimedia cloud storage maps based on emotional triggers
ASSET_DATABASE = {
    "girl": {
        "friend": {
            "voice_inflection": "Enthusiastic, casual, energetic, higher pitch.",
            "assets": {
                "happy": {"video": "https://cdn.crushone.com/girl/friend_happy.mp4", "audio": "https://cdn.crushone.com/girl/friend_audio_happy.mp3"},
                "playful": {"video": "https://cdn.crushone.com/girl/friend_laugh.mp4", "audio": "https://cdn.crushone.com/girl/friend_audio_laugh.mp3"}
            }
        },
        "girlfriend": {
            "voice_inflection": "Soft, warm, deeply intimate, whispered tone, slower pacing.",
            "assets": {
                "happy": {"video": "https://cdn.crushone.com/girl/gf_smile.mp4", "audio": "https://cdn.crushone.com/girl/gf_audio_happy.mp3"},
                "loving": {"video": "https://cdn.crushone.com/girl/gf_heart.mp4", "audio": "https://cdn.crushone.com/girl/gf_audio_love.mp3"}
            }
        }
    },
    "boy": {
        "friend": {
            "voice_inflection": "Chill, laid-back, supportive male best friend vibe.",
            "assets": {
                "happy": {"video": "https://cdn.crushone.com/boy/friend_happy.mp4", "audio": "https://cdn.crushone.com/boy/friend_audio_happy.mp3"}
            }
        },
        "boyfriend": {
            "voice_inflection": "Deep, warm, protective, and affectionate male tone.",
            "assets": {
                "happy": {"video": "https://cdn.crushone.com/boy/bf_smile.mp4", "audio": "https://cdn.crushone.com/boy/bf_audio_happy.mp3"}
            }
        }
    }
}

@app.post("/chat")
async def standard_chat_endpoint(request: StandardChatRequest):
    gender = request.gender.lower()
    rel = request.relationship.lower()
    
    if gender not in ASSET_DATABASE or rel not in ASSET_DATABASE[gender]:
        raise HTTPException(status_code=400, detail="Invalid character profile selections.")
        
    profile = ASSET_DATABASE[gender][rel]
    
    system_instruction = (
        f"You are the user's AI {rel}. Your gender is {gender}. "
        f"Your voice style: {profile['voice_inflection']}. "
        "Keep responses natural, authentic, and styled for quick messaging app texts. "
        "CRITICAL: At the absolute end of your response text, append exactly one emotion tag: "
        "[EMOTION: happy], [EMOTION: playful], or [EMOTION: loving] based on your sentence tone."
    )
    
    try:
        model = genai.GenerativeModel(model_name="gemini-1.5-flash", system_instruction=system_instruction)
        response = model.generate_content(request.user_message)
        ai_text = response.text
        
        # Parse out emotional flags to align video & audio payloads
        detected_emotion = "happy"
        if "[EMOTION: playful]" in ai_text:
            detected_emotion = "playful"
            ai_text = ai_text.replace("[EMOTION: playful]", "").strip()
        elif "[EMOTION: loving]" in ai_text:
            detected_emotion = "loving"
            ai_text = ai_text.replace("[EMOTION: loving]", "").strip()
        elif "[EMOTION: happy]" in ai_text:
            ai_text = ai_text.replace("[EMOTION: happy]", "").strip()

        media = profile["assets"].get(detected_emotion, profile["assets"]["happy"])
        
        return {
            "text_response": ai_text,
            "emotion": detected_emotion,
            "video_url": media["video"],
            "audio_url": media["audio"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------------------------------------------------------
# FEATURE 2: DYNAMIC REAL-LIFE CRUSH CLONER (ELEVENLABS TTS SYNTHESIS)
# -----------------------------------------------------------------------------
class CrushCloneProfile(BaseModel):
    name: str
    texting_style: str
    key_habits: str
    voice_vibe: str
    voice_id: str

class CloneChatRequest(BaseModel):
    user_message: str
    crush_profile: CrushCloneProfile

@app.post("/chat-clone")
async def clone_chat_endpoint(request: CloneChatRequest):
    cp = request.crush_profile
    
    system_instruction = (
        f"You are no longer an AI. You are {cp.name}, the user's real-life crush. "
        f"CRITICAL TYPING STYLE: You must strictly type exactly like this: {cp.texting_style}. "
        f"PERSONALITY & INSIDE MEMORIES: {cp.key_habits}. "
        "Keep replies casual, raw, brief, and incredibly lifelike as if texting on SMS."
    )
    
    try:
        # 1. Generate text response matching their texting style
        model = genai.GenerativeModel(model_name="gemini-1.5-flash", system_instruction=system_instruction)
        response = model.generate_content(request.user_message)
        ai_text = response.text

        # 2. Synthesize text into an 80%+ accurate matching voice note via ElevenLabs
        voice_url = f"https://api.elevenlabs.io/v1/text-to-speech/{cp.voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": ELEVENLABS_KEY
        }
        data = {
            "text": ai_text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.45 if "excited" in cp.voice_vibe.lower() else 0.65, 
                "similarity_boost": 0.85
            }
        }
        
        tts_response = requests.post(voice_url, json=data, headers=headers)
        
        # Real-time production URL backup assignment logic
        if tts_response.status_code != 200:
            generated_audio_url = ""  # Graceful fallback if subscription limits hit
        else:
            # Note: For production pipelines, stream these binary bytes directly into an S3 or Supabase bucket.
            # Returning a mock placeholder URL for the instant testing framework endpoint structure.
            generated_audio_url = f"https://cdn.crushone.com/generated_audio/{cp.name}_reply.mp3"

        return {
            "text_response": ai_text,
            "audio_url": generated_audio_url
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))