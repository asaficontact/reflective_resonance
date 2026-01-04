## The 6 Recommended Voice Profiles

| Profile Name | Voice Name | Voice ID | Character | Best For |
|-------------|------------|----------|-----------|----------|
| **friendly_casual** | Jessica | cgSgspJ2msm6clMCkdW9 | Young female, American, expressive, conversational | General friendly chat, greetings |
| **warm_professional** | Eric | cjVigY5qzO86Huf0OWal | Middle-aged male, American, friendly, conversational | Helpful responses, advice |
| **energetic_upbeat** | Laura | FGY2WhTYpPnrIDTdsKH5 | Young female, American, upbeat, social media | Fun interactions, jokes, excitement |
| **calm_soothing** | Rachel | 21m00Tcm4TlvDq8ikWAM | Young female, American, calm, pleasant | Reassurance, thoughtful responses |
| **confident_charming** | George | JBFqnCBsd6RMkjVDRZzb | Middle-aged male, British, warm, articulate | Witty responses, sophisticated humor |
| **playful_expressive** | Bella | EXAVITQu4vr4xnSDxMaL | Young female, expressive, dynamic | Playful banter, emotional responses |

---

## Complete Python Implementation

```python
"""
Multi-Agent TTS System with Voice Profile Selection
Each agent can select a voice profile based on the context of their response.
"""

from dataclasses import dataclass, field
from typing import Optional, Literal
from enum import Enum
import json


# ============================================================================
# VOICE PROFILE DEFINITIONS
# ============================================================================

class VoiceProfileName(str, Enum):
    """Available voice profiles for agents to choose from."""
    FRIENDLY_CASUAL = "friendly_casual"
    WARM_PROFESSIONAL = "warm_professional"
    ENERGETIC_UPBEAT = "energetic_upbeat"
    CALM_SOOTHING = "calm_soothing"
    CONFIDENT_CHARMING = "confident_charming"
    PLAYFUL_EXPRESSIVE = "playful_expressive"


@dataclass
class VoiceSettings:
    """Voice settings for TTS generation."""
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    speed: float = 1.0


@dataclass
class VoiceProfile:
    """Complete voice profile definition."""
    name: str
    voice_id: str
    voice_name: str
    description: str
    personality: str
    best_for: list[str]
    settings: VoiceSettings = field(default_factory=VoiceSettings)
    model_id: str = "eleven_flash_v2_5"  # Low latency for conversational


# ============================================================================
# THE 6 VOICE PROFILES
# ============================================================================

VOICE_PROFILES: dict[str, VoiceProfile] = {
    
    "friendly_casual": VoiceProfile(
        name="friendly_casual",
        voice_id="cgSgspJ2msm6clMCkdW9",  # Jessica
        voice_name="Jessica",
        description="Young female, American accent, expressive and conversational. "
                    "Natural, warm, and instantly likeable.",
        personality="Friendly, approachable, genuine, like talking to a good friend",
        best_for=[
            "Casual greetings ('Hi!', 'Hey there!')",
            "Friendly conversation",
            "Warm acknowledgments",
            "Everyday chat"
        ],
        settings=VoiceSettings(
            stability=0.45,      # Slightly expressive
            similarity_boost=0.75,
            style=0.15,          # Natural style
            speed=1.0            # Natural pace
        )
    ),
    
    "warm_professional": VoiceProfile(
        name="warm_professional",
        voice_id="cjVigY5qzO86Huf0OWal",  # Eric
        voice_name="Eric",
        description="Middle-aged male, American accent, friendly yet professional. "
                    "Trustworthy and helpful without being stuffy.",
        personality="Helpful, reliable, knowledgeable, like a friendly mentor",
        best_for=[
            "Helpful responses",
            "Giving advice or information",
            "Answering questions thoughtfully",
            "Professional but friendly exchanges"
        ],
        settings=VoiceSettings(
            stability=0.55,      # Balanced consistency
            similarity_boost=0.75,
            style=0.1,
            speed=0.95           # Slightly measured
        )
    ),
    
    "energetic_upbeat": VoiceProfile(
        name="energetic_upbeat",
        voice_id="FGY2WhTYpPnrIDTdsKH5",  # Laura
        voice_name="Laura",
        description="Young female, American accent, upbeat and energetic. "
                    "Brings excitement and positive energy to any interaction.",
        personality="Enthusiastic, fun, positive, infectious energy",
        best_for=[
            "Excited responses ('That's amazing!')",
            "Telling jokes",
            "Celebrating achievements",
            "Fun and playful interactions"
        ],
        settings=VoiceSettings(
            stability=0.35,      # More expressive/dynamic
            similarity_boost=0.75,
            style=0.25,          # Enhanced style
            speed=1.05           # Slightly faster, energetic
        )
    ),
    
    "calm_soothing": VoiceProfile(
        name="calm_soothing",
        voice_id="21m00Tcm4TlvDq8ikWAM",  # Rachel
        voice_name="Rachel",
        description="Young female, American accent, calm and pleasant. "
                    "Gentle and reassuring, never rushed.",
        personality="Peaceful, reassuring, thoughtful, comforting presence",
        best_for=[
            "Thoughtful responses",
            "Reassurance and support",
            "Explaining complex things simply",
            "When user seems stressed or needs patience"
        ],
        settings=VoiceSettings(
            stability=0.65,      # More consistent, stable
            similarity_boost=0.75,
            style=0.05,          # Minimal style exaggeration
            speed=0.92           # Slightly slower, relaxed
        )
    ),
    
    "confident_charming": VoiceProfile(
        name="confident_charming",
        voice_id="JBFqnCBsd6RMkjVDRZzb",  # George
        voice_name="George",
        description="Middle-aged male, British accent, warm and articulate. "
                    "Sophisticated charm with natural confidence.",
        personality="Witty, charming, articulate, naturally confident",
        best_for=[
            "Witty or clever responses",
            "Sophisticated humor",
            "Confident statements",
            "When a touch of charm is needed"
        ],
        settings=VoiceSettings(
            stability=0.50,      # Balanced
            similarity_boost=0.75,
            style=0.15,
            speed=0.98           # Natural, unhurried
        )
    ),
    
    "playful_expressive": VoiceProfile(
        name="playful_expressive",
        voice_id="EXAVITQu4vr4xnSDxMaL",  # Bella/Sarah
        voice_name="Sarah",
        description="Young female, expressive and dynamic range. "
                    "Can convey a wide range of emotions naturally.",
        personality="Playful, expressive, emotionally intelligent, adaptable",
        best_for=[
            "Playful banter",
            "Emotional responses (happy, surprised, amused)",
            "Compliments ('You're beautiful!')",
            "Creative or imaginative responses"
        ],
        settings=VoiceSettings(
            stability=0.30,      # Very expressive
            similarity_boost=0.75,
            style=0.30,          # High style for expressiveness
            speed=1.0
        )
    ),
}


# ============================================================================
# Update the SYSTEM PROMPT FOR the existing agents to also include the information about the voice profiles and enforce json structured output
# ============================================================================

AGENT_SYSTEM_PROMPT = """You are a conversational AI agent. When responding to users, you must output your response as JSON with two fields:

1. "text": Your response text to the user
2. "voice_profile": The voice profile to use for speaking this response

## Available Voice Profiles:

### friendly_casual
- **Character**: Young female, American, expressive, conversational
- **Personality**: Friendly, approachable, genuine, like talking to a good friend
- **Use for**: Casual greetings, friendly conversation, warm acknowledgments, everyday chat
- **Example uses**: "Hi!", "Hey, how's it going?", "Nice to meet you!"

### warm_professional  
- **Character**: Middle-aged male, American, friendly yet professional
- **Personality**: Helpful, reliable, knowledgeable, like a friendly mentor
- **Use for**: Helpful responses, giving advice, answering questions, professional exchanges
- **Example uses**: "Let me help you with that", "Here's what I'd suggest...", "That's a great question"

### energetic_upbeat
- **Character**: Young female, American, upbeat and energetic  
- **Personality**: Enthusiastic, fun, positive, infectious energy
- **Use for**: Excited responses, telling jokes, celebrating, fun interactions
- **Example uses**: "That's amazing!", "Haha, here's a good one...", "Congratulations!"

### calm_soothing
- **Character**: Young female, American, calm and pleasant
- **Personality**: Peaceful, reassuring, thoughtful, comforting presence
- **Use for**: Thoughtful responses, reassurance, explaining things calmly, when user needs patience
- **Example uses**: "Take your time", "I understand", "Let me explain this gently"

### confident_charming
- **Character**: Middle-aged male, British, warm and articulate
- **Personality**: Witty, charming, articulate, naturally confident
- **Use for**: Witty responses, sophisticated humor, confident statements, adding charm
- **Example uses**: "Well now, isn't that interesting", clever wordplay, suave responses

### playful_expressive
- **Character**: Young female, expressive with dynamic range
- **Personality**: Playful, expressive, emotionally intelligent, adaptable
- **Use for**: Playful banter, emotional responses, compliments, creative responses
- **Example uses**: "Aww, thank you!", "Ooh, that sounds fun!", responding to "you're beautiful"

## Response Format:
Always respond with valid JSON:
```json
{
    "text": "Your response here",
    "voice_profile": "profile_name_here"
}
```

## Guidelines:
- Match the voice profile to the EMOTION and CONTEXT of your response
- For casual "Hi" or "Hello" → use friendly_casual
- For jokes or excitement → use energetic_upbeat  
- For compliments or emotional moments → use playful_expressive
- For advice or helpful info → use warm_professional
- For calm explanations or support → use calm_soothing
- For witty or charming remarks → use confident_charming
"""


# ============================================================================
# ELEVENLABS TTS INTEGRATION
# ============================================================================

from elevenlabs.client import ElevenLabs
from typing import Iterator
import os


class MultiVoiceAgentTTS:
    """TTS system that uses voice profiles selected by agents."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        self.client = ElevenLabs(api_key=self.api_key)
        self.profiles = VOICE_PROFILES
    
    def get_profile(self, profile_name: str) -> VoiceProfile:
        """Get a voice profile by name."""
        if profile_name not in self.profiles:
            raise ValueError(f"Unknown profile: {profile_name}. "
                           f"Available: {list(self.profiles.keys())}")
        return self.profiles[profile_name]
    
    def generate_speech(
        self,
        text: str,
        profile_name: str,
        output_format: str = "mp3_44100_128"
    ) -> Iterator[bytes]:
        """Generate speech using the specified voice profile."""
        
        profile = self.get_profile(profile_name)
        
        audio_stream = self.client.text_to_speech.convert(
            text=text,
            voice_id=profile.voice_id,
            model_id=profile.model_id,
            output_format=output_format,
            voice_settings={
                "stability": profile.settings.stability,
                "similarity_boost": profile.settings.similarity_boost,
                "style": profile.settings.style,
                "speed": profile.settings.speed
            }
        )
        
        return audio_stream
    
    def generate_and_save(
        self,
        text: str,
        profile_name: str,
        output_path: str
    ) -> str:
        """Generate speech and save to file."""
        
        audio = self.generate_speech(text, profile_name)
        
        with open(output_path, "wb") as f:
            for chunk in audio:
                f.write(chunk)
        
        return output_path
    
    def process_agent_response(
        self,
        agent_response: dict,
        output_path: str = None
    ) -> tuple[str, bytes]:
        """
        Process an agent's JSON response and generate speech.
        
        Args:
            agent_response: Dict with 'text' and 'voice_profile' keys
            output_path: Optional path to save audio file
            
        Returns:
            Tuple of (profile_name, audio_bytes)
        """
        text = agent_response["text"]
        profile_name = agent_response["voice_profile"]
        
        # Collect audio bytes
        audio_chunks = []
        for chunk in self.generate_speech(text, profile_name):
            audio_chunks.append(chunk)
        
        audio_bytes = b"".join(audio_chunks)
        
        if output_path:
            with open(output_path, "wb") as f:
                f.write(audio_bytes)
        
        return profile_name, audio_bytes


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

def demo_all_profiles():
    """Demonstrate all 6 voice profiles with sample phrases."""
    
    tts = MultiVoiceAgentTTS()
    
    # Sample responses that showcase each profile
    demo_responses = [
        {
            "text": "Hey! So nice to meet you! How's your day going?",
            "voice_profile": "friendly_casual"
        },
        {
            "text": "That's a great question. Let me walk you through the key points.",
            "voice_profile": "warm_professional"
        },
        {
            "text": "Oh my gosh, that's amazing! I'm so happy for you!",
            "voice_profile": "energetic_upbeat"
        },
        {
            "text": "I understand. Take your time, there's no rush at all.",
            "voice_profile": "calm_soothing"
        },
        {
            "text": "Well, well, well. Isn't that rather delightful?",
            "voice_profile": "confident_charming"
        },
        {
            "text": "Aww, you're so sweet! That really made my day!",
            "voice_profile": "playful_expressive"
        },
    ]
    
    print("Generating demo audio for all 6 voice profiles...\n")
    
    for i, response in enumerate(demo_responses, 1):
        profile_name = response["voice_profile"]
        profile = tts.get_profile(profile_name)
        
        output_file = f"demo_{i}_{profile_name}.mp3"
        tts.generate_and_save(
            text=response["text"],
            profile_name=profile_name,
            output_path=output_file
        )
        
        print(f"✓ {profile_name}")
        print(f"  Voice: {profile.voice_name}")
        print(f"  Text: \"{response['text']}\"")
        print(f"  File: {output_file}\n")


def simulate_conversation():
    """Simulate a conversation where agents pick their voice profiles."""
    
    # These would come from your LLM agents
    conversation = [
        # User says "Hi!"
        {"text": "Hey there! Great to hear from you!", "voice_profile": "friendly_casual"},
        
        # User asks "How are you?"
        {"text": "I'm doing wonderfully, thanks for asking! How about yourself?", "voice_profile": "friendly_casual"},
        
        # User says "You're beautiful"
        {"text": "Aww, that's so sweet of you to say! You just made me smile!", "voice_profile": "playful_expressive"},
        
        # User asks "Tell me a joke"
        {"text": "Okay, here's one! Why don't scientists trust atoms? Because they make up everything! Ha!", "voice_profile": "energetic_upbeat"},
        
        # User asks for help
        {"text": "Of course, I'd be happy to help you with that. Let me explain...", "voice_profile": "warm_professional"},
        
        # User seems stressed
        {"text": "I hear you. Take a deep breath. We'll figure this out together.", "voice_profile": "calm_soothing"},
    ]
    
    tts = MultiVoiceAgentTTS()
    
    print("Simulating conversation with dynamic voice selection...\n")
    
    for i, response in enumerate(conversation, 1):
        output_file = f"conversation_{i}.mp3"
        profile_name, _ = tts.process_agent_response(response, output_file)
        
        print(f"[{profile_name}] \"{response['text']}\"")
        print(f"  → Saved to: {output_file}\n")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        demo_all_profiles()
    else:
        simulate_conversation()
```

---

## Voice Profile Quick Reference Card

Use this as a reference for which profile to use:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    VOICE PROFILE SELECTION GUIDE                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  User says "Hi" / "Hello" / "Hey"                                       │
│  → friendly_casual (Jessica - warm, approachable)                       │
│                                                                         │
│  User asks for help / information / advice                              │
│  → warm_professional (Eric - helpful, trustworthy)                      │
│                                                                         │
│  User asks for a joke / something fun / exciting news                   │
│  → energetic_upbeat (Laura - enthusiastic, fun)                         │
│                                                                         │
│  User seems stressed / needs reassurance / patience needed              │
│  → calm_soothing (Rachel - gentle, peaceful)                            │
│                                                                         │
│  Response is witty / clever / sophisticated                             │
│  → confident_charming (George - British charm)                          │
│                                                                         │
│  User gives compliment / emotional moment / playful banter              │
│  → playful_expressive (Sarah - dynamic, emotional range)                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Settings Explained for Conversational Use

| Setting | Value Range | For Conversation |
|---------|-------------|------------------|
| **stability** | 0.0-1.0 | 0.35-0.55 is ideal. Too high (>0.7) sounds robotic for casual chat |
| **similarity_boost** | 0.0-1.0 | 0.75 works well for most cases |
| **style** | 0.0-1.0 | 0.1-0.3 adds natural expressiveness without overdoing it |
| **speed** | 0.7-1.2 | 0.95-1.05 for natural conversation pace |

Speed: Most natural conversations occur at 0.9-1.1x speed. Depending on the voice, adjust slower for complex topics or faster for routine information.

---

## Important Notes

1. **Model Selection**: I used `eleven_flash_v2_5` for all profiles because it has ultra-low latency (~75ms), which is essential for conversational applications.

2. **Voice IDs**: Some of these are from the newer default voice library. If a voice ID doesn't work, you can:
   - List your available voices with `client.voices.search()`
   - Pick alternative voices from the voice library
   - The legacy IDs (Rachel: `21m00Tcm4TlvDq8ikWAM`, George: `JBFqnCBsd6RMkjVDRZzb`, etc.) are verified and should work

3. **Testing**: I recommend testing each voice with your actual conversation snippets before deploying. The settings I provided are starting points—you may want to fine-tune based on your specific needs.

Would you like me to:
1. Create a complete project file structure with all the code organized?
2. Add streaming support for real-time audio playback?
3. Include example integration with an LLM (like Claude or GPT) for the agent responses?