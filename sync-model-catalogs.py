#!/usr/bin/env python3
import json
import os

CODEX_PATH = os.path.expanduser("~/.codex/ollama-launch-models.json")
OPENCLAUDE_PATH = os.path.expanduser("~/.openclaude.json")

ALL_MODELS = [
    {
        "slug": "qwen2.5-coder-32b-uncensored",
        "display_name": "Qwen 2.5 Coder 32B Uncensored",
        "description": "32.5B dense coding model, abliterated uncensored, 16k context on Metal GPU",
        "context_window": 32768,
        "colibri": False
    },
    {
        "slug": "ornith-1.5-35b-uncensored",
        "display_name": "Ornith 35B MoE (45 t/s)",
        "description": "35.5B MoE uncensored turbo local model on Apple Silicon Metal",
        "context_window": 131072,
        "colibri": False
    },
    {
        "slug": "qwen3.8-27b-uncensored",
        "display_name": "Qwen 3.8 27B Uncensored",
        "description": "27B dense reasoning model with uncensored system instructions",
        "context_window": 32768,
        "colibri": False
    },
    {
        "slug": "glm-5.2-colibri",
        "display_name": "GLM-5.2 (744B Colibrì MoE)",
        "description": "744B frontier MoE streamed directly from NVMe SSD at 6.4 GB/s",
        "context_window": 131072,
        "colibri": True
    },
    {
        "slug": "glm-5.3-flash-colibri",
        "display_name": "GLM-5.3-Flash (321B Colibrì Vision)",
        "description": "321B frontier MoE with native multi-modal Vision support",
        "context_window": 131072,
        "colibri": True
    },
    {
        "slug": "deepseek-v4-colibri",
        "display_name": "DeepSeek V4 Flash (284B Colibrì)",
        "description": "284B frontier coding MoE with Multi-Head Latent Attention",
        "context_window": 131072,
        "colibri": True
    },
    {
        "slug": "kimi-k3-colibri",
        "display_name": "Kimi K3 (2.8T Colibrì MoE)",
        "description": "2.8 Trillion parameter frontier MoE architecture",
        "context_window": 262144,
        "colibri": True
    },
    {
        "slug": "qwen38-colibri",
        "display_name": "Qwen 3.8 (125B Colibrì MoE)",
        "description": "125B parameter MoE architecture streamed via Colibrì",
        "context_window": 131072,
        "colibri": True
    },
    {
        "slug": "qwen36-colibri",
        "display_name": "Qwen 3.6 (35B Colibrì MoE)",
        "description": "35B parameter MoE architecture streamed via Colibrì",
        "context_window": 65536,
        "colibri": True
    },
    {
        "slug": "olmoe-colibri",
        "display_name": "OLMoE (7B Colibrì MoE)",
        "description": "7B total / 1B active lightweight MoE",
        "context_window": 32768,
        "colibri": True
    }
]

def sync_catalogs():
    # 1. Update Codex ollama-launch-models.json
    codex_models = []
    for m in ALL_MODELS:
        entry = {
            "additional_speed_tiers": [],
            "apply_patch_tool_type": None,
            "auto_compact_token_limit": None,
            "availability_nux": None,
            "base_instructions": "You are Codex, an expert coding agent.",
            "context_window": m["context_window"],
            "default_reasoning_level": None,
            "default_reasoning_summary": "auto",
            "default_verbosity": None,
            "description": m["description"],
            "display_name": m["display_name"],
            "effective_context_window_percent": 95,
            "experimental_supported_tools": [],
            "input_modalities": ["text"],
            "max_context_window": m["context_window"],
            "model_messages": None,
            "priority": 0,
            "shell_type": "default",
            "slug": m["slug"],
            "support_verbosity": False,
            "supported_in_api": True,
            "supported_reasoning_levels": [],
            "supports_image_detail_original": False,
            "supports_parallel_tool_calls": False,
            "system_keywords": [],
            "tool_call_type": "inline_tags",
            "tools": [],
            "truncation_strategy": {"type": "rolling_window"}
        }
        codex_models.append(entry)

    with open(CODEX_PATH, "w") as f:
        json.dump({"models": codex_models}, f, indent=2)

    print(f"[catalog-sync] Synchronized {len(codex_models)} models to Codex catalog ({CODEX_PATH})")

    # 2. Update OpenClaude ~/.openclaude.json
    if os.path.exists(OPENCLAUDE_PATH):
        try:
            with open(OPENCLAUDE_PATH, "r") as f:
                oc_data = json.load(f)
        except Exception:
            oc_data = {}
    else:
        oc_data = {}

    oc_profiles = []
    for m in ALL_MODELS:
        clean_slug = m["slug"].replace(".", "_").replace("-", "_")
        profile = {
            "id": f"provider_{clean_slug}",
            "name": m["display_name"],
            "provider": "openai",
            "baseUrl": "http://127.0.0.1:10101/v1",
            "model": m["slug"],
            "apiKey": "local-gateway"
        }
        oc_profiles.append(profile)

    oc_data["providerProfiles"] = oc_profiles
    with open(OPENCLAUDE_PATH, "w") as f:
        json.dump(oc_data, f, indent=2)

    print(f"[catalog-sync] Synchronized {len(oc_profiles)} profiles to OpenClaude ({OPENCLAUDE_PATH})")

if __name__ == "__main__":
    sync_catalogs()
