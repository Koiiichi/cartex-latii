from google import genai
from google.genai import errors
from config import config
from pydantic import BaseModel
from typing import Type
from enum import Enum
import httpx
import stamina

class ModelType(Enum):
    FAST = "fast"
    ADVANCED = "advanced"

client = genai.Client(api_key=config.gemini_api_key)

class Gemini:
    @stamina.retry(on=(errors.ServerError, httpx.TimeoutException), attempts=3, wait_initial=1.0, wait_max=30.0)
    def request(self, prompt: str, schema: Type[BaseModel], model: ModelType = ModelType.FAST) -> BaseModel:
        try:
            response = client.models.generate_content(
            model=config.gemini_fast_model if model == ModelType.FAST else config.gemini_advanced_model,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": schema.model_json_schema(),
            },
            )
            if not response.text:
                raise ValueError("Gemini API returned an empty response.")
            output = schema.model_validate_json(response.text)
            return output
        except errors.ClientError as e:
            print(f"Client error during Gemini API call: {e}")
            raise
        except Exception as e:
            print(f"Error during Gemini API call: {e}")
            raise
        
        