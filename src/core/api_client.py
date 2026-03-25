#!/usr/bin/env python3
"""
API Client - Interface to MiniMax text and vision models.

Provides:
- generate_text(): Text generation for skill selection and parameter inference
- analyze_image(): Vision validation for plot quality checking
- chat(): Multi-turn conversation for deep research
"""

from __future__ import annotations

import base64
import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


class APIClient:
    """Client for MiniMax API."""

    def __init__(
        self,
        api_key: str | None = None,
        text_model: str | None = None,
        text_api_url: str | None = None,
        vision_model: str | None = None,
        vision_api_url: str | None = None,
    ) -> None:
        """
        Initialize API client.

        Args:
            api_key: MiniMax API key. If None, reads from MINIMAX_API_KEY env.
            text_model: Text model name. If None, reads from env.
            text_api_url: Text API URL. If None, reads from env.
            vision_model: Vision model name. If None, reads from env.
            vision_api_url: Vision API URL. If None, reads from env.
        """
        import os

        self.api_key = api_key or os.getenv("MINIMAX_API_KEY", "")
        self.text_model = text_model or os.getenv(
            "MINIMAX_TEXT_MODEL", "MiniMax-M2.7-highspeed"
        )
        self.text_api_url = text_api_url or os.getenv(
            "MINIMAX_TEXT_API_URL", "https://api.minimaxi.com/v1"
        )
        self.vision_model = vision_model or os.getenv(
            "MINIMAX_VISION_MODEL", "MiniMax-M2.7-highspeed"
        )
        self.vision_api_url = vision_api_url or os.getenv(
            "MINIMAX_VISION_API_URL", "https://api.minimaxi.com/v1"
        )

    def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """
        Generate text using MiniMax text model.

        Args:
            prompt: User prompt.
            system_prompt: System prompt (optional).
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.

        Returns:
            Generated text.
        """
        if not self.api_key:
            logger.warning("API key not configured, returning placeholder")
            return "API key not configured"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        data = {
            "model": self.text_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            response = requests.post(
                f"{self.text_api_url}/text/chatcompletion_v2",
                headers=headers,
                json=data,
                timeout=120,
            )
            response.raise_for_status()

            result = response.json()
            return result.get("choices", [{}])[0].get("message", {}).get(
                "content", ""
            )

        except requests.exceptions.Timeout:
            logger.error("Text generation request timed out")
            return "Request timed out. Please try again."
        except requests.exceptions.RequestException as e:
            logger.error("Text generation request failed: %s", e)
            return f"API request failed: {e}"
        except Exception as e:
            logger.error("Text generation error: %s", e)
            return f"Error: {e}"

    def analyze_image(self, image_data: bytes, prompt: str) -> str:
        """
        Analyze image using MiniMax vision model.

        Args:
            image_data: Image bytes.
            prompt: Question/prompt about the image.

        Returns:
            Analysis result.
        """
        if not self.api_key:
            logger.warning("API key not configured, skipping visual validation")
            return "API key not configured"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        files = {
            "file": ("image.png", image_data, "image/png"),
        }

        data = {
            "model": self.vision_model,
            "prompt": prompt,
            "type": "image_url",
        }

        try:
            response = requests.post(
                f"{self.vision_api_url}/vision/chatcompletion_v2",
                headers=headers,
                data=data,
                files=files,
                timeout=120,
            )
            response.raise_for_status()

            result = response.json()
            return result.get("choices", [{}])[0].get("message", {}).get(
                "content", ""
            )

        except requests.exceptions.Timeout:
            logger.error("Vision analysis request timed out")
            return "Request timed out. Please try again."
        except requests.exceptions.RequestException as e:
            logger.error("Vision analysis request failed: %s", e)
            return f"API request failed: {e}"
        except Exception as e:
            logger.error("Vision analysis error: %s", e)
            return f"Error: {e}"

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.7) -> str:
        """
        Multi-turn chat conversation.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            temperature: Sampling temperature.

        Returns:
            Assistant's response.
        """
        if not self.api_key:
            logger.warning("API key not configured")
            return "API key not configured"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        data = {
            "model": self.text_model,
            "messages": messages,
            "temperature": temperature,
        }

        try:
            response = requests.post(
                f"{self.text_api_url}/text/chatcompletion_v2",
                headers=headers,
                json=data,
                timeout=120,
            )
            response.raise_for_status()

            result = response.json()
            return result.get("choices", [{}])[0].get("message", {}).get(
                "content", ""
            )

        except Exception as e:
            logger.error("Chat request failed: %s", e)
            return f"Error: {e}"
