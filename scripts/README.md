# AI Executive Assistant Scripts

A genericized Python package for AI-powered meeting notes processing. These scripts analyze meeting transcripts, generate summaries, extract action items, and maintain metadata.

## Features

- **Multi-provider AI support**: Works with Google Vertex AI, OpenAI, Anthropic Claude, or local Ollama
- **Meeting analysis**: Generates executive summaries, topic analysis, and action items
- **Frontmatter management**: Automatically updates YAML metadata (tags, categories, links)
- **Name normalization**: Standardizes common name/acronym variations
- **Flexible configuration**: Config-based paths instead of hardcoded values

## Quick Start

### 1. Installation

```bash
# Clone or download these scripts
cd ai-executive-assistant/scripts

# Install dependencies (only install what you need)
pip install -r requirements.txt

# Or install specific providers:
pip install pyyaml google-cloud-aiplatform  # For Vertex AI
pip install pyyaml openai                    # For OpenAI
pip install pyyaml anthropic                 # For Anthropic
pip install pyyaml requests                  # For Ollama
```

### 2. Configuration

```bash
# Copy example config and customize
cp config.example.yaml config.yaml

# Edit config.yaml with your settings:
# - Set vault_root to your notes directory
# - Configure AI provider and credentials
# - Customize folder paths and name replacements
```

### 3. Usage

```bash
# Process a meeting note
python process_meeting.py path/to/meeting.md

# Specify meeting type explicitly
python process_meeting.py path/to/meeting.md --type one-on-one

# Use custom config file
python process_meeting.py path/to/meeting.md --config /path/to/config.yaml
```

## Configuration

The `config.yaml` file controls all settings. Key sections:

### Paths

```yaml
paths:
  vault_root: "~/Documents/Notes"
  meetings_folder: "Meetings"
  people_folder: "People"
  reference_file: "Templates/Tag Reference.md"
```

### AI Provider

```yaml
ai:
  provider: "vertex"  # or openai, anthropic, ollama
  model: "gemini-2.5-pro"

  # Provider-specific settings
  vertex:
    project_id: "your-project"
    location: "us-central1"
```

### Processing

```yaml
processing:
  name_replacements:
    Eric: Erik
    UXC: UXE
```

## Module Reference

### config.py

Configuration loader with path resolution:

```python
from config import get_config

config = get_config()
vault_path = config.vault_path
meetings = config.meetings_folder
```

### ai_provider.py

AI provider abstraction:

```python
from ai_provider import generate_text, generate_embedding

# Generate text
summary = generate_text("Analyze this meeting...")

# Generate embedding (for vector search)
vector = generate_embedding("Some text to embed")
```

### process_meeting.py

Main meeting processor (see Usage above).

## AI Provider Setup

### Google Vertex AI

1. Set up GCP project and enable Vertex AI API
2. Authenticate: `gcloud auth application-default login`
3. Configure in `config.yaml`:

```yaml
ai:
  provider: "vertex"
  vertex:
    project_id: "your-gcp-project"
    location: "us-central1"
```

### OpenAI

1. Get API key from platform.openai.com
2. Set environment variable: `export OPENAI_API_KEY=sk-...`
3. Or configure in `config.yaml`:

```yaml
ai:
  provider: "openai"
  model: "gpt-4"
  openai:
    api_key: "sk-..."
```

### Anthropic Claude

1. Get API key from console.anthropic.com
2. Set environment variable: `export ANTHROPIC_API_KEY=sk-ant-...`
3. Or configure in `config.yaml`:

```yaml
ai:
  provider: "anthropic"
  model: "claude-3-5-sonnet-20241022"
```

### Ollama (Local)

1. Install Ollama: https://ollama.ai
2. Pull a model: `ollama pull llama2`
3. Configure in `config.yaml`:

```yaml
ai:
  provider: "ollama"
  model: "llama2"
  ollama:
    base_url: "http://localhost:11434"
```

## File Organization

Expected meeting notes format:

```markdown
---
date: 2024-03-15
category: team-meeting
tags: [sprint-planning, roadmap]
---

# Meeting Notes

[Your meeting transcript or notes here]
```

The scripts will:
1. Normalize names based on config
2. Generate summary and analysis
3. Extract action items
4. Update frontmatter with metadata
5. Add year/quarter from filename (MM-DD-YY format)

## Customization

### Custom Prompts

Edit the prompts in `process_meeting.py` to match your style:
- `GROUP_MEETING_PROMPT`: For team/group meetings
- `ONE_ON_ONE_PROMPT`: For 1:1 meetings
- `FRONTMATTER_PROMPT`: For metadata extraction

### Name Normalization

Add custom replacements in `config.yaml`:

```yaml
processing:
  name_replacements:
    Jon: John
    DevOps: Platform Engineering
```

## Troubleshooting

### "config.yaml not found"
- Ensure `config.yaml` exists in the same directory as the scripts
- Or use `--config` to specify path

### Authentication errors
- Vertex AI: Run `gcloud auth application-default login`
- OpenAI/Anthropic: Set API key environment variables

### Import errors
- Ensure you've installed required dependencies: `pip install -r requirements.txt`
- Install only the provider packages you need

## License

These scripts are provided as functional starting points for building your own AI executive assistant. Feel free to modify and extend them for your needs.
