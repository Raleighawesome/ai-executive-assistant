"""AI provider abstraction layer.

Supports multiple AI providers: vertex (Google), openai, anthropic, and ollama.
Provides unified interface for text generation and embeddings.
"""

import os
from typing import Optional, List

from config import get_config


class AIProvider:
    """Unified AI provider interface."""

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        """Initialize AI provider.

        Args:
            provider: Provider name (vertex, openai, anthropic, ollama).
                     If None, uses config.
            model: Model name. If None, uses config.
        """
        config = get_config()
        self.provider = provider or config.ai_provider
        self.model = model or config.ai_model
        self.embedding_provider = config.embedding_provider
        self.embedding_model = config.embedding_model

        self._client = None
        self._embedding_client = None

    def _get_vertex_client(self):
        """Initialize Vertex AI client."""
        if self._client is None:
            import vertexai
            from vertexai.generative_models import GenerativeModel

            config = get_config()
            project = config.get('ai.vertex.project_id')
            location = config.get('ai.vertex.location', 'us-central1')

            # Handle service account impersonation if configured
            impersonate_sa = config.get('ai.vertex.impersonate_service_account')
            if impersonate_sa:
                os.environ['GOOGLE_IMPERSONATE_SERVICE_ACCOUNT'] = impersonate_sa

            vertexai.init(project=project, location=location)
            self._client = GenerativeModel(self.model)

        return self._client

    def _get_openai_client(self):
        """Initialize OpenAI client."""
        if self._client is None:
            from openai import OpenAI

            config = get_config()
            api_key = config.get('ai.openai.api_key') or os.getenv('OPENAI_API_KEY')
            self._client = OpenAI(api_key=api_key)

        return self._client

    def _get_anthropic_client(self):
        """Initialize Anthropic client."""
        if self._client is None:
            from anthropic import Anthropic

            config = get_config()
            api_key = config.get('ai.anthropic.api_key') or os.getenv('ANTHROPIC_API_KEY')
            self._client = Anthropic(api_key=api_key)

        return self._client

    def _get_ollama_client(self):
        """Get Ollama base URL."""
        config = get_config()
        return config.get('ai.ollama.base_url', 'http://localhost:11434')

    def generate_text(self, prompt: str, model: Optional[str] = None) -> str:
        """Generate text using configured AI provider.

        Args:
            prompt: Input prompt
            model: Override default model

        Returns:
            Generated text
        """
        model = model or self.model

        if self.provider == 'vertex':
            client = self._get_vertex_client()
            response = client.generate_content(prompt)
            return response.text

        elif self.provider == 'openai':
            client = self._get_openai_client()
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content

        elif self.provider == 'anthropic':
            client = self._get_anthropic_client()
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text

        elif self.provider == 'ollama':
            import requests
            base_url = self._get_ollama_client()
            response = requests.post(
                f"{base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False}
            )
            response.raise_for_status()
            return response.json()['response']

        else:
            raise ValueError(f"Unsupported AI provider: {self.provider}")

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text.

        Args:
            text: Input text

        Returns:
            Embedding vector as list of floats
        """
        if self.embedding_provider == 'vertex':
            from vertexai.language_models import TextEmbeddingModel

            config = get_config()
            project = config.get('ai.vertex.project_id')
            location = config.get('ai.vertex.location', 'us-central1')

            # Handle service account impersonation if configured
            impersonate_sa = config.get('ai.vertex.impersonate_service_account')
            if impersonate_sa:
                os.environ['GOOGLE_IMPERSONATE_SERVICE_ACCOUNT'] = impersonate_sa

            import vertexai
            vertexai.init(project=project, location=location)

            model_name = self.embedding_model or 'text-embedding-005'
            model = TextEmbeddingModel.from_pretrained(model_name)
            embeddings = model.get_embeddings([text])
            return embeddings[0].values

        elif self.embedding_provider == 'openai':
            client = self._get_openai_client()
            model_name = self.embedding_model or 'text-embedding-3-small'
            response = client.embeddings.create(
                model=model_name,
                input=text
            )
            return response.data[0].embedding

        elif self.embedding_provider == 'ollama':
            import requests
            base_url = self._get_ollama_client()
            model_name = self.embedding_model or 'nomic-embed-text'
            response = requests.post(
                f"{base_url}/api/embeddings",
                json={"model": model_name, "prompt": text}
            )
            response.raise_for_status()
            return response.json()['embedding']

        else:
            raise ValueError(f"Unsupported embedding provider: {self.embedding_provider}")


# Convenience functions
def generate_text(prompt: str, model: Optional[str] = None) -> str:
    """Generate text using configured AI provider.

    Args:
        prompt: Input prompt
        model: Override default model

    Returns:
        Generated text
    """
    provider = AIProvider()
    return provider.generate_text(prompt, model)


def generate_embedding(text: str) -> List[float]:
    """Generate embedding for text.

    Args:
        text: Input text

    Returns:
        Embedding vector as list of floats
    """
    provider = AIProvider()
    return provider.generate_embedding(text)
