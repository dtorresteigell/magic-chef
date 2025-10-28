"""
Model-agnostic LLM client wrapper
Supports multiple providers: Mistral, OpenAI, Anthropic, etc.
"""
import os
from typing import List, Dict, Optional
import requests
from flask import current_app


class LLMClient:
    """Abstraction layer for different LLM providers"""
    
    def __init__(self, provider: str = "mistral"):
        self.provider = provider.lower()
        self.api_key = None
        self.model_id = None
        self.base_url = None
        
        if self.provider == "mistral":
            self.api_key = os.environ.get('COOK_AGENT_KEY')
            self.model_id = os.environ.get('MODEL_ID', 'mistral-large-latest')
            try:
                from mistralai import Mistral
                self.client = Mistral(api_key=self.api_key)
            except ImportError:
                raise ImportError("mistralai package not installed. Run: pip install mistralai")
                
        elif self.provider == "openai":
            self.api_key = os.environ.get('OPENAI_API_KEY')
            self.model_id = os.environ.get('MODEL_ID', 'gpt-4')
            self.base_url = "https://api.openai.com/v1/chat/completions"
        elif self.provider == "anthropic":
            self.api_key = os.environ.get('ANTHROPIC_API_KEY')
            self.model_id = os.environ.get('MODEL_ID', 'claude-3-5-sonnet-20241022')
            self.base_url = "https://api.anthropic.com/v1/messages"
        
        if not self.api_key:
            raise ValueError(f"API key not found for provider: {self.provider}")
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict:
        """
        Send chat completion request
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response
            
        Returns:
            Dict with 'content' and optional 'metadata'
        """
        if self.provider == "mistral":
            return self._mistral_completion(messages, temperature, max_tokens)
        elif self.provider == "openai":
            return self._openai_completion(messages, temperature, max_tokens)
        elif self.provider == "anthropic":
            return self._anthropic_completion(messages, temperature, max_tokens)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    def _mistral_completion(self, messages: List[Dict], temperature: float, max_tokens: int) -> Dict:
        """Mistral API implementation using official SDK"""
        try:
            response = self.client.chat.complete(
                model=self.model_id,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return {
                'content': response.choices[0].message.content,
                'metadata': {
                    'model': response.model,
                    'usage': {
                        'prompt_tokens': response.usage.prompt_tokens,
                        'completion_tokens': response.usage.completion_tokens,
                        'total_tokens': response.usage.total_tokens
                    }
                }
            }
        except Exception as e:
            current_app.logger.error(f"Mistral API error: {str(e)}")
            raise Exception(f"LLM API error: {str(e)}")
    
    def _openai_completion(self, messages: List[Dict], temperature: float, max_tokens: int) -> Dict:
        """OpenAI API implementation"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                'content': data['choices'][0]['message']['content'],
                'metadata': {
                    'model': data.get('model'),
                    'usage': data.get('usage')
                }
            }
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"OpenAI API error: {str(e)}")
            raise Exception(f"LLM API error: {str(e)}")
    
    def _anthropic_completion(self, messages: List[Dict], temperature: float, max_tokens: int) -> Dict:
        """Anthropic API implementation"""
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        # Anthropic uses slightly different format
        # Extract system message if present
        system_message = None
        user_messages = []
        for msg in messages:
            if msg['role'] == 'system':
                system_message = msg['content']
            else:
                user_messages.append(msg)
        
        payload = {
            "model": self.model_id,
            "messages": user_messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        if system_message:
            payload['system'] = system_message
        
        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                'content': data['content'][0]['text'],
                'metadata': {
                    'model': data.get('model'),
                    'usage': data.get('usage')
                }
            }
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Anthropic API error: {str(e)}")
            raise Exception(f"LLM API error: {str(e)}")