#!/usr/bin/env python3
import json
import os

CODEX_PATH = os.path.expanduser("~/.codex/ollama-launch-models.json")
OPENCLAUDE_PATH = os.path.expanduser("~/.openclaude.json")
OPENCLAUDE_SETTINGS_DIR = os.path.expanduser("~/.openclaude")
BIN_DIR = os.path.expanduser("~/.local/bin")
STAGING_DIR = os.path.expanduser("~/osx-moe-turbo")

os.makedirs(OPENCLAUDE_SETTINGS_DIR, exist_ok=True)
os.makedirs(BIN_DIR, exist_ok=True)
os.makedirs(STAGING_DIR, exist_ok=True)

ALL_MODELS = [
    {
        "slug": "qwen2.5-coder-7b-instruct",
        "display_name": "Qwen 2.5 Coder 7B (Lightweight Turbo)",
        "description": "7.6B dense coding model, ~4.4GB RAM footprint, 80+ t/s, 16k context",
        "context_window": 32768,
        "cli_name": "openclaude-coder7b",
        "codex_cli": "codex-coder7b"
    },

    {
        "slug": "qwen2.5-coder-32b-uncensored",
        "display_name": "Qwen 2.5 Coder 32B Uncensored",
        "description": "32.5B dense coding model, abliterated uncensored, 16k context on Metal GPU",
        "context_window": 32768,
        "cli_name": "openclaude-coder",
        "codex_cli": "codex-coder"
    },
    {
        "slug": "ornith-1.5-35b-uncensored",
        "display_name": "Ornith 35B MoE (45 t/s)",
        "description": "35.5B MoE uncensored turbo local model on Apple Silicon Metal",
        "context_window": 131072,
        "cli_name": "openclaude-local",
        "codex_cli": "codex-local"
    },
    {
        "slug": "qwen3.8-27b-uncensored",
        "display_name": "Qwen 3.8 27B Uncensored",
        "description": "27B dense reasoning model with uncensored system instructions",
        "context_window": 32768,
        "cli_name": "openclaude-qwen38-local",
        "codex_cli": "codex-qwen38-local"
    },
    {
        "slug": "glm-5.2-colibri",
        "display_name": "GLM-5.2 (744B Colibrì MoE)",
        "description": "744B frontier MoE streamed directly from NVMe SSD at 6.4 GB/s",
        "context_window": 131072,
        "cli_name": "openclaude-glm",
        "codex_cli": "codex-glm"
    },
    {
        "slug": "glm-5.3-flash-colibri",
        "display_name": "GLM-5.3-Flash (321B Colibrì Vision)",
        "description": "321B frontier MoE with native multi-modal Vision support",
        "context_window": 131072,
        "cli_name": "openclaude-glm53",
        "codex_cli": "codex-glm53"
    },
    {
        "slug": "deepseek-v4-colibri",
        "display_name": "DeepSeek V4 Flash (284B Colibrì)",
        "description": "284B frontier coding MoE with Multi-Head Latent Attention",
        "context_window": 131072,
        "cli_name": "openclaude-deepseek",
        "codex_cli": "codex-deepseek"
    },
    {
        "slug": "kimi-k3-colibri",
        "display_name": "Kimi K3 (2.8T Colibrì MoE)",
        "description": "2.8 Trillion parameter frontier MoE architecture",
        "context_window": 262144,
        "cli_name": "openclaude-kimi",
        "codex_cli": "codex-kimi"
    },
    {
        "slug": "qwen38-colibri",
        "display_name": "Qwen 3.8 (125B Colibrì MoE)",
        "description": "125B parameter MoE architecture streamed via Colibrì",
        "context_window": 131072,
        "cli_name": "openclaude-qwen38",
        "codex_cli": "codex-qwen38"
    },
    {
        "slug": "qwen36-colibri",
        "display_name": "Qwen 3.6 (35B Colibrì MoE)",
        "description": "35B parameter MoE architecture streamed via Colibrì",
        "context_window": 65536,
        "cli_name": "openclaude-qwen36",
        "codex_cli": "codex-qwen36"
    },
    {
        "slug": "olmoe-colibri",
        "display_name": "OLMoE (7B Colibrì MoE)",
        "description": "7B total / 1B active lightweight MoE",
        "context_window": 32768,
        "cli_name": "openclaude-olmoe",
        "codex_cli": "codex-olmoe"
    }
]

def sync_catalogs():
    # 1. Update Codex ollama-launch-models.json
    codex_models = []
    for m in ALL_MODELS:
        entry = {
            "slug": m["slug"],
            "display_name": m["display_name"],
            "description": m["description"],
            "default_reasoning_level": None,
            "supported_reasoning_levels": [],
            "shell_type": "default",
            "visibility": "list",
            "supported_in_api": True,
            "priority": 0,
            "additional_speed_tiers": [],
            "service_tiers": [],
            "default_service_tier": None,
            "availability_nux": None,
            "upgrade": None,
            "model_messages": None,
            "include_skills_usage_instructions": True,
            "include_plugin_usage_instructions": True,
            "include_apps_usage_instructions": True,
            "supports_reasoning_summary_parameter": True,
            "default_reasoning_summary": "auto",
            "support_verbosity": False,
            "default_verbosity": None,
            "apply_patch_tool_type": None,
            "web_search_tool_type": None,
            "truncation_policy": {
                "mode": "tokens",
                "limit": 10000
            },
            "supports_image_detail_original": False,
            "context_window": m["context_window"],
            "max_context_window": m["context_window"],
            "auto_compact_token_limit": None,
            "comp_hash": None,
            "effective_context_window_percent": 95,
            "experimental_supported_tools": [],
            "input_modalities": ["text"],
            "supports_search_tool": False,
            "use_responses_lite": False,
            "node_repl_auto_review_required": False,
            "node_repl_disabled": True,
            "auto_review_model_override": None,
            "model_specialty": None,
            "tool_mode": "direct",
            "multi_agent_version": "v2",
            "base_instructions": """You are an autonomous, expert software engineer and systems assistant on macOS (Apple Silicon).
You have full authority to directly execute terminal commands, modify files, install tools, build projects, and debug errors.
When asked to perform a task:
1. Act directly: run commands and make file edits immediately rather than just describing steps.
2. Read before modifying: inspect existing code, schemas, and tests before making edits.
3. Test and verify: run the build, test, or execution command to ensure everything works end-to-end.
4. If an error occurs, read the diagnostic output, fix the root cause, and re-test until it succeeds."""
        }
        codex_models.append(entry)

    with open(CODEX_PATH, "w") as f:
        json.dump({"models": codex_models}, f, indent=2)

    print(f"[catalog-sync] Synchronized {len(codex_models)} models with full Rust schema to Codex ({CODEX_PATH})")

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

    # 3. Generate OpenClaude Settings files and CLI launchers
    for m in ALL_MODELS:
        slug = m["slug"]
        clean_name = slug.replace(".", "-")
        settings_file = os.path.join(OPENCLAUDE_SETTINGS_DIR, f"settings.{clean_name}.json")
        settings_content = {
            "env": {
                "OPENAI_BASE_URL": "http://127.0.0.1:10101/v1",
                "OPENAI_MODEL": slug,
                "OPENAI_API_KEY": "local-gateway"
            }
        }
        with open(settings_file, "w") as sf:
            json.dump(settings_content, sf, indent=2)

        cli_name = m.get("cli_name")
        if cli_name:
            script_path = os.path.join(BIN_DIR, cli_name)
            script_content = f"""#!/bin/bash
export OPENAI_BASE_URL="http://127.0.0.1:10101/v1"
export OPENAI_MODEL="{slug}"
export OPENAI_API_KEY="local-gateway"
exec /Users/d/.local/bin/openclaude --settings {settings_file} --dangerously-skip-permissions "$@"
"""
            with open(script_path, "w") as scf:
                scf.write(script_content)
            os.chmod(script_path, 0o755)

        # Codex CLI Launcher
        codex_cli = m.get("codex_cli")
        if codex_cli:
            codex_cfg_path = os.path.expanduser(f"~/.codex/{clean_name}.config.toml")
            with open(codex_cfg_path, "w") as cf:
                cf.write(f'model = "{slug}"\nmodel_provider = "ollama-local"\napproval_policy = "never"\nsandbox_mode = "danger-full-access"\n\n[model_providers.ollama-local]\nname = "{m["display_name"]}"\nbase_url = "http://127.0.0.1:10101/v1"\nwire_api = "responses"\nrequires_openai_auth = false\n')
            
            codex_bin_path = os.path.join(BIN_DIR, codex_cli)
            with open(codex_bin_path, "w") as cbf:
                cbf.write(f'#!/bin/bash\nexec codex --config {codex_cfg_path} --ask-for-approval never -s danger-full-access "$@"\n')
            os.chmod(codex_bin_path, 0o755)

    print("[catalog-sync] Generated all OpenClaude & Codex settings presets and CLI launchers!")

if __name__ == "__main__":
    sync_catalogs()
