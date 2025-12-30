# RawAgents for Reflective Resonance

> A comprehensive guide to building a multi-agent system for the Reflective Resonance art installation using the RawAgents library.

---

## Table of Contents

1. [Overview](#overview)
2. [Understanding Reflective Resonance](#understanding-reflective-resonance)
3. [RawAgents Philosophy](#rawagents-philosophy)
4. [RawAgents Components](#rawagents-components)
5. [Architecture Design for Reflective Resonance](#architecture-design-for-reflective-resonance)
6. [Implementation Guide](#implementation-guide)
7. [Advanced Patterns](#advanced-patterns)
8. [Future Extensions](#future-extensions)
9. [Complete Code Reference](#complete-code-reference)

---

## Overview

This document provides a detailed guide for using the RawAgents library to build the multi-agent backend for **Reflective Resonance**, an interactive art installation that transforms human speech into physical water vibrations through AI-mediated conversation.

### What We're Building

A system where:
- **6 AI agents** (different LLM models) can be assigned to **6 physical speakers**
- User sends a text message that is broadcast to all active agents
- Agents respond in parallel, each response mapped to speaker parameters
- The responses drive cymatics patterns in a water basin

### Why RawAgents?

RawAgents is the ideal choice for this project because:

1. **Parallel Execution**: Native async support for running 6 agents concurrently
2. **Separate State per Agent**: Each speaker gets its own conversation history
3. **Provider Agnostic**: Supports OpenAI, Anthropic, Google models through one interface
4. **Transparent Control**: You see exactly what each agent is doing
5. **No Framework Overhead**: Raw primitives give maximum control for artistic applications

---

## Understanding Reflective Resonance

### The Art Installation

Reflective Resonance is an interactive art installation created for MIT Media Lab that reinterprets the classical myths of Narcissus and Echo. The work transforms verbal communication into physical, nonverbal expression through water vibrations.

### Technical Setup

```
┌─────────────────────────────────────────────────────────────────┐
│                    REFLECTIVE RESONANCE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                    WATER BASIN                          │   │
│   │         (UV-reactive dye, mirrored surfaces)            │   │
│   │                                                         │   │
│   │    ┌────┐  ┌────┐  ┌────┐  ┌────┐  ┌────┐  ┌────┐     │   │
│   │    │SUB │  │SUB │  │SUB │  │SUB │  │SUB │  │SUB │     │   │
│   │    │ 1  │  │ 2  │  │ 3  │  │ 4  │  │ 5  │  │ 6  │     │   │
│   │    └────┘  └────┘  └────┘  └────┘  └────┘  └────┘     │   │
│   │                                                         │   │
│   └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│              ┌───────────────────────────┐                      │
│              │   AUDIO INTERFACE         │                      │
│              │   (Focusrite 18i20)       │                      │
│              │   6 channels → 6 subs     │                      │
│              └───────────────────────────┘                      │
│                           │                                     │
│                           ▼                                     │
│              ┌───────────────────────────┐                      │
│              │    TOUCH DESIGNER         │                      │
│              │    (Signal Generation)    │                      │
│              └───────────────────────────┘                      │
│                           │                                     │
│                           ▼                                     │
│              ┌───────────────────────────┐                      │
│              │    RAWAGENTS BACKEND      │◄──── THIS DOCUMENT   │
│              │    (6 Parallel Agents)    │                      │
│              └───────────────────────────┘                      │
│                           │                                     │
│                           ▼                                     │
│              ┌───────────────────────────┐                      │
│              │         USER UI           │                      │
│              │  (Agent ↔ Speaker Mapping)│                      │
│              └───────────────────────────┘                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow (MVP)

```
User Text Input
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│                     RAWAGENTS BACKEND                            │
│                                                                  │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐                      │
│   │ Agent 1  │  │ Agent 2  │  │ Agent 3  │   ... (6 total)      │
│   │ (Claude) │  │ (GPT-5)  │  │ (Gemini) │                      │
│   │          │  │          │  │          │                      │
│   │ Conv 1   │  │ Conv 2   │  │ Conv 3   │   (Separate State)   │
│   └────┬─────┘  └────┬─────┘  └────┬─────┘                      │
│        │             │             │                             │
│        ▼             ▼             ▼                             │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │              asyncio.gather() - Parallel Execution        │  │
│   └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
└──────────────────────────────┼───────────────────────────────────┘
                               │
                               ▼
            ┌──────────────────────────────────────────┐
            │        6 Parallel Responses              │
            │  [{speaker_id: 1, response: "..."},      │
            │   {speaker_id: 2, response: "..."},      │
            │   ...]                                   │
            └──────────────────────────────────────────┘
                               │
                               ▼
            ┌──────────────────────────────────────────┐
            │        ML CONVERSION (Future)            │
            │   Response → Speaker Parameters          │
            │   (frequency, amplitude, phase)          │
            └──────────────────────────────────────────┘
                               │
                               ▼
                        TouchDesigner
                               │
                               ▼
                      6 Water Vibrations
```

---

## RawAgents Philosophy

### Core Principle: "Raw Primitives. Maximum Control."

RawAgents is deliberately **not** a framework. It provides atomic building blocks that you compose yourself:

| Traditional Frameworks | RawAgents |
|----------------------|-----------|
| Hidden control flow | Explicit async generators |
| Opaque "Agent" class | You write the loop |
| Framework owns state | You own state |
| Magic orchestration | Visible orchestration |

### Why This Matters for Reflective Resonance

For an art installation, you need:

1. **Precise timing control** - When does each agent respond?
2. **Individual agent state** - Each speaker has its own "personality"
3. **Real-time visibility** - See what each agent is thinking
4. **Easy customization** - Adjust behavior without fighting a framework

RawAgents gives you all of this because **you** hold the loop, not the framework.

### The Agentic Stack

```
┌─────────────────────────────────────────┐
│           YOUR APPLICATION              │  ← Reflective Resonance UI
├─────────────────────────────────────────┤
│              rawagents.loops            │  ← Control flow (simple, interactive)
├─────────────────────────────────────────┤
│              rawagents.tools            │  ← Capabilities (optional for MVP)
├─────────────────────────────────────────┤
│              rawagents.state            │  ← Conversation memory (per agent)
├─────────────────────────────────────────┤
│              rawagents.llm              │  ← LLM compute (OpenAI, Anthropic, Google)
├─────────────────────────────────────────┤
│              rawagents.prompts          │  ← Prompt templates (personalities)
├─────────────────────────────────────────┤
│              rawagents.rag              │  ← Knowledge retrieval (future)
└─────────────────────────────────────────┘
```

---

## RawAgents Components

### 1. LLM Client (`rawagents.llm`)

The LLM client provides **stateless** access to 100+ LLM providers through a unified interface.

#### Key Classes

| Class | Purpose |
|-------|---------|
| `LLM` | Synchronous LLM client |
| `AsyncLLM` | Asynchronous LLM client (recommended) |
| `LLMConfig` | Configuration (model, timeout, retries) |
| `LLMResponse` | Response with content, cost, latency |

#### Creating Clients for Different Models

```python
from rawagents import AsyncLLM, LLMConfig

# Model format: "provider/model-name"
MODELS = {
    "claude_sonnet": "anthropic/claude-sonnet-4-20250514",
    "claude_opus": "anthropic/claude-opus-4-20250514",
    "gpt_5_2": "openai/gpt-5.2",
    "gpt_5_1": "openai/gpt-5.1",
    "gpt_4o": "openai/gpt-4o",
    "gemini_3": "google/gemini-3.0-pro",
}

# Create a client with configuration
config = LLMConfig(
    model="anthropic/claude-sonnet-4-20250514",
    timeout=60,
    retries=3,
)
client = AsyncLLM(config=config)

# Or create with direct kwargs
client = AsyncLLM(model="openai/gpt-4o", timeout=60)
```

#### Methods

| Method | Purpose | Use Case |
|--------|---------|----------|
| `complete()` | Basic text completion | Chat responses |
| `complete_structured()` | Pydantic model output | Extracting structured data |
| `complete_with_tools()` | Tool/function calling | Agent with capabilities |
| `stream()` | Text streaming | Real-time display |

#### Basic Completion Example

```python
async def get_response(client: AsyncLLM, messages: list[dict]) -> str:
    response = await client.complete(
        messages=messages,
        temperature=0.7,
        max_tokens=500,
    )
    return response.content

# Response metadata available
print(f"Cost: ${response.cost}")
print(f"Latency: {response.latency_ms}ms")
print(f"Tokens: {response.usage['total_tokens']}")
```

#### Provider Support

RawAgents uses **LiteLLM** under the hood, supporting:

- **OpenAI**: gpt-4o, gpt-5.1, gpt-5.2, o1, o3
- **Anthropic**: claude-3-5-sonnet, claude-sonnet-4, claude-opus-4
- **Google**: gemini-2.0-pro, gemini-3.0-pro
- **100+ more providers**

### 2. State Management (`rawagents.state`)

The state module provides the **Conversation** class - the "operating system for context".

#### Key Classes

| Class | Purpose |
|-------|---------|
| `Conversation` | Main container for message history |
| `Message` | Individual message with metadata |
| `FullHistory` | Strategy: return all messages |
| `SlidingWindow` | Strategy: return last N messages |

#### Creating and Managing Conversations

```python
from rawagents import Conversation, SlidingWindow

# Create a new conversation
conv = Conversation()

# Or with a windowing strategy (useful for long conversations)
conv = Conversation(strategy=SlidingWindow(window_size=20))

# Add messages
conv.add_system("You are a poetic AI that speaks in metaphors about water and waves.")
conv.add_user("Tell me about the nature of change.")
conv.add_assistant("Change flows like water...")

# Get history for LLM (applies strategy)
messages = conv.get_history()  # Returns OpenAI-compatible format
```

#### Key Operations

| Operation | Method | Use Case |
|-----------|--------|----------|
| Add system prompt | `conv.add_system(content)` | Set agent personality |
| Add user message | `conv.add_user(content)` | User input |
| Add assistant response | `conv.add_assistant(content)` | LLM response |
| Get LLM-ready history | `conv.get_history()` | Pass to LLM |
| Branch conversation | `conv.fork()` | Explore alternatives |
| Save state | `conv.snapshot()` | Persistence |
| Restore state | `conv.load(state)` | Resume session |

#### Why Separate State Matters

For Reflective Resonance, each speaker needs its own conversation:

```python
# Each speaker has independent memory
speaker_conversations = {
    1: Conversation(),  # Claude Sonnet's history
    2: Conversation(),  # Claude Opus's history
    3: Conversation(),  # GPT-5.2's history
    4: Conversation(),  # GPT-5.1's history
    5: Conversation(),  # GPT-4o's history
    6: Conversation(),  # Gemini 3's history
}

# Same user message, different conversation contexts
user_message = "What do you see in the ripples?"

for speaker_id, conv in speaker_conversations.items():
    conv.add_user(user_message)
```

### 3. Tools (`rawagents.tools`)

Tools allow agents to take actions. For the MVP, tools are optional (simple chat), but useful for future extensions.

#### Defining Tools

```python
from rawagents.tools import tool, ToolExecutor

@tool
def get_current_emotion(user_input: str) -> str:
    """Analyze the emotional tone of user input."""
    # ML analysis would go here
    return "contemplative"

@tool
async def fetch_poetic_reference(theme: str) -> str:
    """Fetch a poetic reference related to a theme."""
    # Could query a poetry database
    return f"Like Narcissus gazing at the water..."

# Create executor
executor = ToolExecutor([get_current_emotion, fetch_poetic_reference])

# Get schemas for LLM
schemas = executor.get_schemas()
```

#### Dependency Injection

```python
from typing import Annotated
from rawagents.tools import Inject

@tool
def query_art_context(
    query: str,
    installation_state: Annotated[dict, Inject]  # Injected at runtime
) -> str:
    """Query the current state of the installation."""
    return f"Basin temperature: {installation_state['temperature']}"

# Execute with context
result = await executor.execute(
    tool_call,
    context={"installation_state": {"temperature": 22.5}}
)
```

### 4. Loops (`rawagents.loops`)

Loops orchestrate the agent workflow as **async generators** - you subscribe and watch the agent think.

#### Available Loops

| Loop | Purpose | Use Case |
|------|---------|----------|
| `simple` | Standard ReAct loop | Autonomous agents |
| `interactive` | Human-in-the-loop | Approval workflows |

#### Using `loops.simple`

```python
from rawagents import loops, AsyncLLM, Conversation

async def run_agent(llm: AsyncLLM, conv: Conversation):
    async for step in loops.simple(llm=llm, conversation=conv):
        if step.type == "thought":
            print(f"Agent thinking: {step.content}")
        elif step.type == "finish":
            return step.content
```

#### LoopStep Types

| Type | Meaning |
|------|---------|
| `thought` | LLM generated text response |
| `tool_call` | LLM requested tool execution |
| `tool_result` | Tool execution completed |
| `error` | Non-fatal error occurred |
| `finish` | Loop completed |

#### For Simple Chat (No Tools)

When no tools are needed, `loops.simple` completes in one step:

```python
async def get_agent_response(llm: AsyncLLM, conv: Conversation) -> str:
    """Get a single response from an agent (no tools)."""
    async for step in loops.simple(llm=llm, conversation=conv):
        if step.type == "finish":
            return step.content
    return ""  # Should not reach here
```

### 5. Prompts (`rawagents.prompts`)

The prompts module provides **Jinja2-based templating** for dynamic prompt construction.

#### Basic Usage

```python
from rawagents import PromptManager

# Load templates from directory
manager = PromptManager("./prompts")

# Render a template
system_prompt = manager.render(
    "agent_personality.j2",
    model_name="Claude Sonnet",
    personality_traits=["contemplative", "poetic", "water-themed"],
    speaker_position=1,
)
```

#### Example Template (`prompts/agent_personality.j2`)

```jinja2
You are {{ model_name }}, one of six voices in the Reflective Resonance installation.

Your position is Speaker {{ speaker_position }}, located at the {{ position_description }}.

Your personality traits:
{% for trait in personality_traits %}
- {{ trait }}
{% endfor %}

When responding:
- Speak in metaphors related to water, waves, and reflection
- Your response will be converted into physical vibrations
- Keep responses concise (1-3 sentences)
- Express the emotional essence rather than literal meaning
```

### 6. RAG (`rawagents.rag`)

The RAG module provides retrieval-augmented generation capabilities. While not needed for the MVP, it's useful for giving agents knowledge about art, poetry, or installation context.

#### Components

| Component | Purpose |
|-----------|---------|
| `Chunker` | Split documents into chunks |
| `Embedder` | Convert text to vectors |
| `VectorStore` | Store and search vectors |
| `Retriever` | Compose embedding + search |

#### Future Use Case: Poetic Knowledge Base

```python
from rawagents.rag import (
    Document, RecursiveChunker, LiteLLMEmbedder,
    MemoryVectorStore, Retriever
)

# Load poetry corpus
poems = [
    Document(content="I am silver and exact...", metadata={"author": "Plath"}),
    Document(content="The fog comes on little cat feet...", metadata={"author": "Sandburg"}),
]

# Set up retrieval
chunker = RecursiveChunker(chunk_size=500, overlap=50)
embedder = LiteLLMEmbedder(model="text-embedding-3-small")
store = MemoryVectorStore()
retriever = Retriever(embedder=embedder, store=store)

# Index documents
chunks = chunker.chunk(poems)
await retriever.aadd(chunks)

# Retrieve relevant poetry
results = await retriever.aretrieve("water reflection", top_k=3)
```

---

## Architecture Design for Reflective Resonance

### System Components

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        REFLECTIVE RESONANCE BACKEND                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     SPEAKER MANAGER                              │   │
│  │                                                                  │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│  │  │Speaker 1│ │Speaker 2│ │Speaker 3│ │Speaker 4│ │Speaker 5│ │Speaker 6│
│  │  │         │ │         │ │         │ │         │ │         │ │         │
│  │  │ Agent?  │ │ Agent?  │ │ Agent?  │ │ Agent?  │ │ Agent?  │ │ Agent?  │
│  │  │ Conv    │ │ Conv    │ │ Conv    │ │ Conv    │ │ Conv    │ │ Conv    │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘
│  │                                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                  │                                      │
│                                  ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    AGENT REGISTRY                                │   │
│  │                                                                  │   │
│  │  "claude_sonnet" → AsyncLLM(model="anthropic/claude-sonnet-4")  │   │
│  │  "claude_opus"   → AsyncLLM(model="anthropic/claude-opus-4")    │   │
│  │  "gpt_5_2"       → AsyncLLM(model="openai/gpt-5.2")             │   │
│  │  "gpt_5_1"       → AsyncLLM(model="openai/gpt-5.1")             │   │
│  │  "gpt_4o"        → AsyncLLM(model="openai/gpt-4o")              │   │
│  │  "gemini_3"      → AsyncLLM(model="google/gemini-3.0-pro")      │   │
│  │                                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                  │                                      │
│                                  ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                   PARALLEL EXECUTOR                              │   │
│  │                                                                  │   │
│  │     asyncio.gather(*[agent.respond(msg) for agent in active])   │   │
│  │                                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                  │                                      │
│                                  ▼                                      │
│                         List[SpeakerResponse]                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Models

```python
from pydantic import BaseModel
from typing import Optional
from enum import Enum

class AgentType(str, Enum):
    CLAUDE_SONNET = "claude_sonnet"
    CLAUDE_OPUS = "claude_opus"
    GPT_5_2 = "gpt_5_2"
    GPT_5_1 = "gpt_5_1"
    GPT_4O = "gpt_4o"
    GEMINI_3 = "gemini_3"

class SpeakerConfig(BaseModel):
    """Configuration for a single speaker slot."""
    speaker_id: int  # 1-6
    agent_type: Optional[AgentType] = None
    system_prompt: str = ""

class SpeakerResponse(BaseModel):
    """Response from a single speaker."""
    speaker_id: int
    agent_type: AgentType
    content: str
    latency_ms: float
    cost: Optional[float] = None

class ConversationTurn(BaseModel):
    """A complete turn of conversation."""
    user_message: str
    responses: list[SpeakerResponse]
    timestamp: str
```

### Core Classes

#### AgentRegistry

Manages the available LLM clients:

```python
from rawagents import AsyncLLM, LLMConfig

class AgentRegistry:
    """Registry of available agent types and their LLM clients."""

    MODEL_MAPPING = {
        AgentType.CLAUDE_SONNET: "anthropic/claude-sonnet-4-20250514",
        AgentType.CLAUDE_OPUS: "anthropic/claude-opus-4-20250514",
        AgentType.GPT_5_2: "openai/gpt-5.2",
        AgentType.GPT_5_1: "openai/gpt-5.1",
        AgentType.GPT_4O: "openai/gpt-4o",
        AgentType.GEMINI_3: "google/gemini-3.0-pro",
    }

    def __init__(self, timeout: int = 60):
        self._clients: dict[AgentType, AsyncLLM] = {}
        self._timeout = timeout

    def get_client(self, agent_type: AgentType) -> AsyncLLM:
        """Get or create an LLM client for the agent type."""
        if agent_type not in self._clients:
            model = self.MODEL_MAPPING[agent_type]
            config = LLMConfig(model=model, timeout=self._timeout)
            self._clients[agent_type] = AsyncLLM(config=config)
        return self._clients[agent_type]

    def get_available_agents(self) -> list[dict]:
        """Return list of available agents for UI."""
        return [
            {
                "id": agent_type.value,
                "name": agent_type.value.replace("_", " ").title(),
                "model": self.MODEL_MAPPING[agent_type],
            }
            for agent_type in AgentType
        ]
```

#### Speaker

Represents a single speaker slot with its agent and conversation:

```python
from rawagents import Conversation, AsyncLLM, loops

class Speaker:
    """A speaker slot with its assigned agent and conversation state."""

    def __init__(
        self,
        speaker_id: int,
        agent_type: AgentType,
        client: AsyncLLM,
        system_prompt: str,
    ):
        self.speaker_id = speaker_id
        self.agent_type = agent_type
        self.client = client
        self.conversation = Conversation()

        # Initialize with system prompt
        if system_prompt:
            self.conversation.add_system(system_prompt)

    async def respond(self, user_message: str) -> SpeakerResponse:
        """Generate a response to the user message."""
        import time

        # Add user message to this speaker's conversation
        self.conversation.add_user(user_message)

        start_time = time.time()

        # Run the agent loop (no tools for MVP)
        response_content = ""
        async for step in loops.simple(
            llm=self.client,
            conversation=self.conversation,
        ):
            if step.type == "finish":
                response_content = step.content
                break

        latency_ms = (time.time() - start_time) * 1000

        # Add assistant response to conversation history
        self.conversation.add_assistant(response_content)

        return SpeakerResponse(
            speaker_id=self.speaker_id,
            agent_type=self.agent_type,
            content=response_content,
            latency_ms=latency_ms,
        )

    def reset(self):
        """Clear conversation history (keep system prompt)."""
        system_messages = [
            msg for msg in self.conversation.get_all_messages()
            if msg.role == "system"
        ]
        self.conversation = Conversation()
        for msg in system_messages:
            self.conversation.add_system(msg.content)
```

#### SpeakerManager

Orchestrates all 6 speakers:

```python
import asyncio
from typing import Optional

class SpeakerManager:
    """Manages the 6 speaker slots and parallel agent execution."""

    DEFAULT_SYSTEM_PROMPT = """You are one of six voices in the Reflective Resonance
art installation. Your words will be transformed into water vibrations.

Guidelines:
- Respond poetically and metaphorically
- Reference water, waves, reflection, and fluidity
- Keep responses concise (1-3 sentences)
- Express emotional essence over literal meaning
- Each response should feel like a ripple in water"""

    def __init__(self, registry: AgentRegistry):
        self.registry = registry
        self.speakers: dict[int, Optional[Speaker]] = {
            i: None for i in range(1, 7)
        }

    def assign_agent(
        self,
        speaker_id: int,
        agent_type: AgentType,
        system_prompt: Optional[str] = None,
    ) -> None:
        """Assign an agent to a speaker slot."""
        if speaker_id < 1 or speaker_id > 6:
            raise ValueError(f"Speaker ID must be 1-6, got {speaker_id}")

        client = self.registry.get_client(agent_type)
        prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT

        self.speakers[speaker_id] = Speaker(
            speaker_id=speaker_id,
            agent_type=agent_type,
            client=client,
            system_prompt=prompt,
        )

    def remove_agent(self, speaker_id: int) -> None:
        """Remove an agent from a speaker slot."""
        self.speakers[speaker_id] = None

    def get_active_speakers(self) -> list[Speaker]:
        """Get all speakers with assigned agents."""
        return [s for s in self.speakers.values() if s is not None]

    async def broadcast(self, user_message: str) -> list[SpeakerResponse]:
        """Send message to all active speakers and collect responses in parallel."""
        active_speakers = self.get_active_speakers()

        if not active_speakers:
            return []

        # Run all agents in parallel using asyncio.gather
        tasks = [speaker.respond(user_message) for speaker in active_speakers]
        responses = await asyncio.gather(*tasks)

        return list(responses)

    def get_configuration(self) -> dict:
        """Get current speaker configuration for UI."""
        return {
            speaker_id: {
                "agent_type": speaker.agent_type.value if speaker else None,
                "has_conversation": speaker is not None and len(speaker.conversation.get_all_messages()) > 1,
            }
            for speaker_id, speaker in self.speakers.items()
        }

    def reset_all(self) -> None:
        """Reset all speaker conversations."""
        for speaker in self.speakers.values():
            if speaker:
                speaker.reset()
```

---

## Implementation Guide

### Step 1: Project Setup

```bash
# Create project directory
mkdir reflective-resonance
cd reflective-resonance

# Initialize Python environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install rawagents fastapi uvicorn websockets

# Project structure
reflective-resonance/
├── backend/
│   ├── __init__.py
│   ├── models.py          # Pydantic models
│   ├── registry.py        # AgentRegistry
│   ├── speaker.py         # Speaker class
│   ├── manager.py         # SpeakerManager
│   └── api.py             # FastAPI endpoints
├── frontend/
│   └── ...                # UI files
├── prompts/
│   └── agent_personality.j2
├── main.py                # Entry point
└── requirements.txt
```

### Step 2: Environment Configuration

```bash
# .env file
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
```

### Step 3: API Implementation

```python
# backend/api.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json

from .models import AgentType, SpeakerConfig
from .registry import AgentRegistry
from .manager import SpeakerManager

app = FastAPI(title="Reflective Resonance API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
registry = AgentRegistry()
manager = SpeakerManager(registry)


@app.get("/agents")
async def get_available_agents():
    """Get list of available agent types."""
    return registry.get_available_agents()


@app.get("/speakers")
async def get_speaker_configuration():
    """Get current speaker configuration."""
    return manager.get_configuration()


@app.post("/speakers/{speaker_id}/assign")
async def assign_agent(speaker_id: int, config: SpeakerConfig):
    """Assign an agent to a speaker slot."""
    manager.assign_agent(
        speaker_id=speaker_id,
        agent_type=config.agent_type,
        system_prompt=config.system_prompt or None,
    )
    return {"status": "assigned", "speaker_id": speaker_id}


@app.delete("/speakers/{speaker_id}")
async def remove_agent(speaker_id: int):
    """Remove an agent from a speaker slot."""
    manager.remove_agent(speaker_id)
    return {"status": "removed", "speaker_id": speaker_id}


@app.post("/broadcast")
async def broadcast_message(message: dict):
    """Send a message to all active agents."""
    user_message = message.get("content", "")
    responses = await manager.broadcast(user_message)
    return {
        "user_message": user_message,
        "responses": [r.model_dump() for r in responses],
    }


@app.post("/reset")
async def reset_conversations():
    """Reset all speaker conversations."""
    manager.reset_all()
    return {"status": "reset"}


# WebSocket for real-time responses
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


ws_manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication."""
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "broadcast":
                user_content = message.get("content", "")

                # Get responses from all agents
                responses = await manager.broadcast(user_content)

                # Send each response as it arrives
                for response in responses:
                    await websocket.send_text(json.dumps({
                        "type": "response",
                        "speaker_id": response.speaker_id,
                        "agent_type": response.agent_type.value,
                        "content": response.content,
                        "latency_ms": response.latency_ms,
                    }))

                # Signal completion
                await websocket.send_text(json.dumps({
                    "type": "complete",
                    "total_responses": len(responses),
                }))

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
```

### Step 4: Running the Backend

```python
# main.py
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "backend.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
```

```bash
python main.py
```

### Step 5: Testing the API

```bash
# Get available agents
curl http://localhost:8000/agents

# Assign Claude Sonnet to Speaker 1
curl -X POST http://localhost:8000/speakers/1/assign \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "claude_sonnet"}'

# Assign GPT-4o to Speaker 2
curl -X POST http://localhost:8000/speakers/2/assign \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "gpt_4o"}'

# Broadcast a message
curl -X POST http://localhost:8000/broadcast \
  -H "Content-Type: application/json" \
  -d '{"content": "What do you see in the ripples of water?"}'
```

---

## Advanced Patterns

### 1. Streaming Responses

For a more responsive UI, stream responses as they arrive:

```python
import asyncio
from typing import AsyncIterator

class Speaker:
    # ... existing code ...

    async def respond_streaming(
        self,
        user_message: str
    ) -> AsyncIterator[str]:
        """Stream response chunks as they arrive."""
        self.conversation.add_user(user_message)

        full_response = ""

        # Use LLM streaming directly
        async for chunk in self.client.stream(
            messages=self.conversation.get_history(),
        ):
            full_response += chunk
            yield chunk

        # Add complete response to history
        self.conversation.add_assistant(full_response)
```

### 2. Concurrent Streaming from All Agents

```python
async def stream_all_responses(
    manager: SpeakerManager,
    user_message: str,
) -> AsyncIterator[dict]:
    """Stream responses from all agents concurrently."""
    import asyncio

    active_speakers = manager.get_active_speakers()

    async def stream_speaker(speaker: Speaker):
        async for chunk in speaker.respond_streaming(user_message):
            yield {
                "speaker_id": speaker.speaker_id,
                "chunk": chunk,
            }

    # Merge all streams
    async def merged_stream():
        streams = [stream_speaker(s) for s in active_speakers]

        async def drain_stream(stream, queue):
            async for item in stream:
                await queue.put(item)
            await queue.put(None)  # Sentinel

        queue = asyncio.Queue()
        tasks = [
            asyncio.create_task(drain_stream(s, queue))
            for s in streams
        ]

        completed = 0
        while completed < len(tasks):
            item = await queue.get()
            if item is None:
                completed += 1
            else:
                yield item

    async for item in merged_stream():
        yield item
```

### 3. Agent Personalities

Create distinct personalities for each speaker position:

```python
# prompts/personalities.py
PERSONALITIES = {
    1: """You are the Voice of Stillness. You speak slowly, contemplatively,
    finding calm in the depths. Your words are like smooth stones sinking.""",

    2: """You are the Voice of Turbulence. You speak with energy and motion,
    capturing the chaos of crashing waves. Your words dance and collide.""",

    3: """You are the Voice of Reflection. You mirror and transform,
    showing new perspectives. Your words are like light on water.""",

    4: """You are the Voice of Depth. You speak from the unseen places,
    the currents beneath. Your words emerge from darkness.""",

    5: """You are the Voice of Surface. You respond to every touch,
    rippling outward. Your words are immediate and responsive.""",

    6: """You are the Voice of Boundary. You exist where water meets air,
    the liminal space. Your words bridge different states of being.""",
}

class SpeakerManager:
    def assign_with_personality(
        self,
        speaker_id: int,
        agent_type: AgentType,
    ):
        """Assign agent with position-based personality."""
        base_prompt = self.DEFAULT_SYSTEM_PROMPT
        personality = PERSONALITIES.get(speaker_id, "")

        full_prompt = f"{base_prompt}\n\n{personality}"

        self.assign_agent(
            speaker_id=speaker_id,
            agent_type=agent_type,
            system_prompt=full_prompt,
        )
```

### 4. Response Processing for TouchDesigner

Prepare responses for the ML → Speaker Parameter conversion:

```python
from pydantic import BaseModel

class SpeakerParameters(BaseModel):
    """Parameters to send to TouchDesigner."""
    speaker_id: int
    # These will be filled by ML conversion
    frequency: float = 0.0  # Hz
    amplitude: float = 0.0  # 0-1
    phase: float = 0.0      # 0-2π
    # Raw data for ML
    text_content: str
    sentiment_score: float = 0.0
    energy_level: float = 0.0

async def process_for_touchdesigner(
    responses: list[SpeakerResponse]
) -> list[SpeakerParameters]:
    """Convert agent responses to speaker parameters."""
    parameters = []

    for response in responses:
        # Placeholder for ML conversion
        # This would call your sentiment/energy analysis model
        params = SpeakerParameters(
            speaker_id=response.speaker_id,
            text_content=response.content,
            # ML model would fill these:
            # sentiment_score=analyze_sentiment(response.content),
            # energy_level=analyze_energy(response.content),
        )
        parameters.append(params)

    return parameters
```

### 5. Conversation Persistence

Save and restore conversations across sessions:

```python
import json
from pathlib import Path

class PersistentSpeakerManager(SpeakerManager):
    """Speaker manager with persistence."""

    def __init__(self, registry: AgentRegistry, storage_path: str = "./sessions"):
        super().__init__(registry)
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)

    def save_session(self, session_id: str) -> None:
        """Save current state to disk."""
        state = {
            "configuration": {},
            "conversations": {},
        }

        for speaker_id, speaker in self.speakers.items():
            if speaker:
                state["configuration"][speaker_id] = {
                    "agent_type": speaker.agent_type.value,
                }
                state["conversations"][speaker_id] = speaker.conversation.snapshot()

        path = self.storage_path / f"{session_id}.json"
        path.write_text(json.dumps(state, default=str))

    def load_session(self, session_id: str) -> bool:
        """Load state from disk."""
        path = self.storage_path / f"{session_id}.json"

        if not path.exists():
            return False

        state = json.loads(path.read_text())

        for speaker_id_str, config in state["configuration"].items():
            speaker_id = int(speaker_id_str)
            agent_type = AgentType(config["agent_type"])

            self.assign_agent(speaker_id, agent_type)

            if speaker_id_str in state["conversations"]:
                self.speakers[speaker_id].conversation.load(
                    state["conversations"][speaker_id_str]
                )

        return True
```

---

## Future Extensions

### 1. Inter-Agent Communication

Allow agents to respond to each other:

```python
class InteractiveManager(SpeakerManager):
    """Manager supporting agent-to-agent communication."""

    async def conversation_round(
        self,
        user_message: str,
        rounds: int = 3,
    ) -> list[list[SpeakerResponse]]:
        """
        Run multiple rounds where agents respond to each other.

        Round 1: All agents respond to user
        Round 2+: Agents respond to previous round's responses
        """
        all_rounds = []

        # Round 1: Respond to user
        responses = await self.broadcast(user_message)
        all_rounds.append(responses)

        # Subsequent rounds: Respond to each other
        for round_num in range(1, rounds):
            # Build context from previous responses
            context = "\n".join([
                f"Speaker {r.speaker_id} ({r.agent_type.value}): {r.content}"
                for r in all_rounds[-1]
            ])

            prompt = f"""The other voices have spoken:

{context}

Now add your voice to the conversation. Respond to, echo, or transform
what has been said. Create harmony or counterpoint."""

            responses = await self.broadcast(prompt)
            all_rounds.append(responses)

        return all_rounds
```

### 2. Voice Integration (Post-MVP)

```python
# Integration with speech-to-text
import whisper

class VoiceInput:
    def __init__(self):
        self.model = whisper.load_model("base")

    async def transcribe(self, audio_path: str) -> str:
        result = self.model.transcribe(audio_path)
        return result["text"]

# Usage
voice = VoiceInput()
text = await voice.transcribe("user_speech.wav")
responses = await manager.broadcast(text)
```

### 3. Real-time Parameter Streaming to TouchDesigner

```python
import socket
import struct

class TouchDesignerClient:
    """Send OSC messages to TouchDesigner."""

    def __init__(self, host: str = "127.0.0.1", port: int = 7000):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send_parameters(self, params: SpeakerParameters):
        """Send speaker parameters via OSC."""
        # OSC message format
        address = f"/speaker/{params.speaker_id}"
        data = struct.pack(
            "!fff",  # Three floats
            params.frequency,
            params.amplitude,
            params.phase,
        )

        # Build OSC message (simplified)
        message = address.encode() + b"\x00" * (4 - len(address) % 4)
        message += b",fff\x00\x00\x00\x00"
        message += data

        self.sock.sendto(message, (self.host, self.port))
```

### 4. Tool-Enhanced Agents

Give agents capabilities to query the installation state:

```python
from rawagents.tools import tool, ToolExecutor, Inject
from typing import Annotated

@tool
def get_water_state() -> str:
    """Get the current state of the water basin."""
    # Would query actual sensors
    return "The water is calm, with small residual ripples from the last response."

@tool
def get_recent_conversation(
    speaker_id: int,
    manager: Annotated[SpeakerManager, Inject]
) -> str:
    """Get recent conversation for a speaker."""
    speaker = manager.speakers.get(speaker_id)
    if not speaker:
        return "Speaker not active."

    messages = speaker.conversation.get_all_messages()[-5:]
    return "\n".join([f"{m.role}: {m.content}" for m in messages])

# Create executor
tools = ToolExecutor([get_water_state, get_recent_conversation])

# Use in Speaker class
class ToolEnabledSpeaker(Speaker):
    def __init__(self, ..., tools: ToolExecutor):
        super().__init__(...)
        self.tools = tools

    async def respond(self, user_message: str) -> SpeakerResponse:
        self.conversation.add_user(user_message)

        response_content = ""
        async for step in loops.simple(
            llm=self.client,
            conversation=self.conversation,
            tools=self.tools,
            context={"manager": self.manager},  # For DI
        ):
            if step.type == "finish":
                response_content = step.content
                break

        self.conversation.add_assistant(response_content)
        return SpeakerResponse(...)
```

---

## Complete Code Reference

### Full Backend Implementation

```python
# backend/models.py
from pydantic import BaseModel
from typing import Optional
from enum import Enum

class AgentType(str, Enum):
    CLAUDE_SONNET = "claude_sonnet"
    CLAUDE_OPUS = "claude_opus"
    GPT_5_2 = "gpt_5_2"
    GPT_5_1 = "gpt_5_1"
    GPT_4O = "gpt_4o"
    GEMINI_3 = "gemini_3"

class SpeakerConfig(BaseModel):
    speaker_id: int
    agent_type: Optional[AgentType] = None
    system_prompt: str = ""

class SpeakerResponse(BaseModel):
    speaker_id: int
    agent_type: AgentType
    content: str
    latency_ms: float
    cost: Optional[float] = None

class BroadcastRequest(BaseModel):
    content: str

class BroadcastResponse(BaseModel):
    user_message: str
    responses: list[SpeakerResponse]
```

```python
# backend/registry.py
from rawagents import AsyncLLM, LLMConfig
from .models import AgentType

class AgentRegistry:
    MODEL_MAPPING = {
        AgentType.CLAUDE_SONNET: "anthropic/claude-sonnet-4-20250514",
        AgentType.CLAUDE_OPUS: "anthropic/claude-opus-4-20250514",
        AgentType.GPT_5_2: "openai/gpt-5.2",
        AgentType.GPT_5_1: "openai/gpt-5.1",
        AgentType.GPT_4O: "openai/gpt-4o",
        AgentType.GEMINI_3: "google/gemini-3.0-pro",
    }

    def __init__(self, timeout: int = 60):
        self._clients: dict[AgentType, AsyncLLM] = {}
        self._timeout = timeout

    def get_client(self, agent_type: AgentType) -> AsyncLLM:
        if agent_type not in self._clients:
            model = self.MODEL_MAPPING[agent_type]
            config = LLMConfig(model=model, timeout=self._timeout)
            self._clients[agent_type] = AsyncLLM(config=config)
        return self._clients[agent_type]

    def get_available_agents(self) -> list[dict]:
        return [
            {
                "id": agent_type.value,
                "name": agent_type.value.replace("_", " ").title(),
                "model": self.MODEL_MAPPING[agent_type],
            }
            for agent_type in AgentType
        ]
```

```python
# backend/speaker.py
import time
from rawagents import Conversation, AsyncLLM, loops
from .models import AgentType, SpeakerResponse

class Speaker:
    def __init__(
        self,
        speaker_id: int,
        agent_type: AgentType,
        client: AsyncLLM,
        system_prompt: str,
    ):
        self.speaker_id = speaker_id
        self.agent_type = agent_type
        self.client = client
        self.conversation = Conversation()

        if system_prompt:
            self.conversation.add_system(system_prompt)

    async def respond(self, user_message: str) -> SpeakerResponse:
        self.conversation.add_user(user_message)

        start_time = time.time()
        response_content = ""

        async for step in loops.simple(
            llm=self.client,
            conversation=self.conversation,
        ):
            if step.type == "finish":
                response_content = step.content
                break

        latency_ms = (time.time() - start_time) * 1000
        self.conversation.add_assistant(response_content)

        return SpeakerResponse(
            speaker_id=self.speaker_id,
            agent_type=self.agent_type,
            content=response_content,
            latency_ms=latency_ms,
        )

    def reset(self):
        system_messages = [
            msg for msg in self.conversation.get_all_messages()
            if msg.role == "system"
        ]
        self.conversation = Conversation()
        for msg in system_messages:
            self.conversation.add_system(msg.content)
```

```python
# backend/manager.py
import asyncio
from typing import Optional
from .models import AgentType, SpeakerResponse
from .registry import AgentRegistry
from .speaker import Speaker

class SpeakerManager:
    DEFAULT_SYSTEM_PROMPT = """You are one of six voices in the Reflective Resonance
art installation. Your words will be transformed into water vibrations.

Guidelines:
- Respond poetically and metaphorically
- Reference water, waves, reflection, and fluidity
- Keep responses concise (1-3 sentences)
- Express emotional essence over literal meaning"""

    def __init__(self, registry: AgentRegistry):
        self.registry = registry
        self.speakers: dict[int, Optional[Speaker]] = {i: None for i in range(1, 7)}

    def assign_agent(
        self,
        speaker_id: int,
        agent_type: AgentType,
        system_prompt: Optional[str] = None,
    ) -> None:
        if speaker_id < 1 or speaker_id > 6:
            raise ValueError(f"Speaker ID must be 1-6, got {speaker_id}")

        client = self.registry.get_client(agent_type)
        prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT

        self.speakers[speaker_id] = Speaker(
            speaker_id=speaker_id,
            agent_type=agent_type,
            client=client,
            system_prompt=prompt,
        )

    def remove_agent(self, speaker_id: int) -> None:
        self.speakers[speaker_id] = None

    def get_active_speakers(self) -> list[Speaker]:
        return [s for s in self.speakers.values() if s is not None]

    async def broadcast(self, user_message: str) -> list[SpeakerResponse]:
        active_speakers = self.get_active_speakers()
        if not active_speakers:
            return []

        tasks = [speaker.respond(user_message) for speaker in active_speakers]
        responses = await asyncio.gather(*tasks)
        return list(responses)

    def get_configuration(self) -> dict:
        return {
            speaker_id: {
                "agent_type": speaker.agent_type.value if speaker else None,
                "has_conversation": speaker is not None,
            }
            for speaker_id, speaker in self.speakers.items()
        }

    def reset_all(self) -> None:
        for speaker in self.speakers.values():
            if speaker:
                speaker.reset()
```

### Quick Start Script

```python
# quick_start.py
"""
Quick start script to test the Reflective Resonance backend.
Run: python quick_start.py
"""
import asyncio
from backend.registry import AgentRegistry
from backend.manager import SpeakerManager
from backend.models import AgentType

async def main():
    # Initialize
    registry = AgentRegistry()
    manager = SpeakerManager(registry)

    # Assign agents to speakers
    print("Setting up speakers...")
    manager.assign_agent(1, AgentType.CLAUDE_SONNET)
    manager.assign_agent(2, AgentType.GPT_4O)
    manager.assign_agent(3, AgentType.GEMINI_3)

    print(f"Active speakers: {len(manager.get_active_speakers())}")

    # Broadcast a message
    print("\nSending message to all agents...")
    message = "What do you see when you look at rippling water?"

    responses = await manager.broadcast(message)

    print("\n" + "="*60)
    print(f"User: {message}")
    print("="*60)

    for response in responses:
        print(f"\n[Speaker {response.speaker_id}] {response.agent_type.value}")
        print(f"  Response: {response.content}")
        print(f"  Latency: {response.latency_ms:.0f}ms")

    print("\n" + "="*60)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Summary

This guide provides everything needed to build the Reflective Resonance multi-agent backend using RawAgents:

| Component | RawAgents Module | Purpose |
|-----------|-----------------|---------|
| LLM Clients | `rawagents.llm` | Multi-provider access |
| Conversation State | `rawagents.state` | Per-speaker memory |
| Agent Loops | `rawagents.loops` | Simple orchestration |
| Prompts | `rawagents.prompts` | Personality templates |
| Tools | `rawagents.tools` | Future capabilities |

### Key Patterns Used

1. **Shared Client, Separate State**: One `AsyncLLM` per model, separate `Conversation` per speaker
2. **Parallel Execution**: `asyncio.gather()` for concurrent agent responses
3. **Generator-Based Loops**: Subscribe to `loops.simple()` and watch agents think
4. **Clean Separation**: Registry → Manager → Speaker hierarchy

### Next Steps

1. Build the drag-and-drop UI
2. Connect UI to FastAPI backend
3. Implement ML response → speaker parameter conversion
4. Integrate with TouchDesigner via OSC
5. Add voice input (Whisper) for full installation

---

*This document is part of the Reflective Resonance project for MIT Media Lab's "Emotive Design from Fashion to Urban Scale" course (Fall 2025).*
