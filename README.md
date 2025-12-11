# AI Executive Assistant

A privacy-first toolkit for automating meeting workflows with AI. Process meeting notes, search your knowledge base semantically, and generate daily briefings — all running locally on your machine.

## Features

- **Meeting Processing** - Automatically generate executive summaries, extract action items, and organize notes
  - **Personal Notes** - Capture personal details from 1:1s for relationship building (family events, vacations, hobbies)
- **RAG Search** - Semantic search across your entire knowledge base using vector embeddings
  - **MCP Integration** - Query Qdrant directly from Claude Code via the Qdrant MCP Server
- **Calendar Integration** - Daily briefings with context from past meetings and relevant documents
- **Workflow Automation** - End-to-end automation with n8n for hands-free processing

## Quick Start

Visit the documentation site: [ai.dadmode.cc](https://ai.dadmode.cc)

The site includes:
- Step-by-step setup guides for each module
- Interactive setup wizard to generate your configuration
- n8n workflow templates ready to import

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Meeting Notes  │────▶│   AI Provider   │────▶│  Processed MD   │
│   (Obsidian)    │     │ (Ollama/OpenAI) │     │   + Summaries   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Daily Brief    │◀────│   RAG Search    │◀────│  Vector Store   │
│   Dashboard     │     │    (Qdrant)     │     │   (Embeddings)  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Modules

| Module | Description |
|--------|-------------|
| **Foundation** | Core setup: Obsidian vault, Python environment, AI provider |
| **Meeting Processing** | AI-powered summaries, action items, personal notes, and metadata extraction |
| **RAG Search** | Vector database setup, semantic search, and MCP server integration |
| **Calendar Integration** | Google Calendar sync and daily briefing generation |
| **Automation** | n8n workflows for hands-free processing |

## Requirements

- Python 3.11+
- Docker (for Qdrant and n8n)
- Obsidian (or compatible markdown editor)
- AI Provider (Ollama, OpenAI, Anthropic, or Google Vertex AI)

## Privacy

This toolkit is designed to run entirely on your local machine. Your meeting notes, embeddings, and AI processing stay on your hardware. The only external calls are to your chosen AI provider for text generation and embeddings.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

## Support

Need help setting up? [Book a consulting call](https://ai.dadmode.cc/consulting) for personalized guidance.
