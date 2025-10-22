import os
import base64
from mistralai import Mistral
from flask import current_app
import json
import re


def encode_image(image_path):
    """Encode image to base64"""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except FileNotFoundError:
        raise FileNotFoundError(f"Image file not found: {image_path}")
    except Exception as e:
        raise Exception(f"Error encoding image: {e}")


def perform_ocr(image_path):
    """
    Perform OCR on an image using Mistral
    
    Args:
        image_path: Path to the image file
        
    Returns:
        str: Extracted markdown text from the image
        
    Raises:
        Exception: If OCR fails
    """
    api_key = os.environ.get("COOK_AGENT_KEY")
    if not api_key:
        raise ValueError("COOK_AGENT_KEY not found in environment")
    
    client = Mistral(api_key=api_key)
    
    try:
        # Encode image to base64
        base64_image = encode_image(image_path)
        
        current_app.logger.info(f"Performing OCR on {image_path}")
        
        # Call OCR endpoint
        ocr_response = client.ocr.process(
            model="mistral-ocr-latest",
            document={
                "type": "image_url",
                "image_url": f"data:image/jpeg;base64,{base64_image}"
            },
            include_image_base64=True
        )
        
        # Extract markdown text
        if not ocr_response.pages or len(ocr_response.pages) == 0:
            raise Exception("No pages returned from OCR")
        
        markdown_text = ocr_response.pages[0].markdown
        
        current_app.logger.info(f"OCR completed successfully")
        
        # ========== DEBUG PRINT ==========
        print("\n" + "="*80)
        print("🔍 OCR RESPONSE - RAW MARKDOWN:")
        print("="*80)
        print(markdown_text)
        print("="*80 + "\n")
        # =================================
        
        return markdown_text
    
    except Exception as e:
        current_app.logger.error(f"OCR error: {e}")
        raise Exception(f"OCR processing failed: {str(e)}")


def parse_agent_json(text: str):
    """
    Extracts JSON from a string that may be wrapped in Markdown code fences.
    Returns a Python dict, or raises json.JSONDecodeError if invalid.
    """
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```", "", text)
    text = re.sub(r"```$", "", text)
    text = text.strip()
    return json.loads(text)


def parse_ocr_text_to_recipe(ocr_text):
    """
    Parse OCR text to recipe using Mistral Recipe Agent
    
    Args:
        ocr_text: Text extracted from OCR
        
    Returns:
        dict: Recipe data in AI format
        
    Raises:
        Exception: If parsing fails
    """
    api_key = os.environ.get("COOK_AGENT_KEY")
    recipe_agent_id = os.environ.get("RECIPE_AGENT_ID")
    
    if not api_key or not recipe_agent_id:
        raise ValueError("COOK_AGENT_KEY and RECIPE_AGENT_ID must be set in environment")
    
    client = Mistral(api_key=api_key)
    
    try:
        current_app.logger.info("Parsing OCR text to recipe with agent")
        
        # Call recipe agent with OCR text
        response = client.beta.conversations.start(
            agent_id=recipe_agent_id,
            inputs=ocr_text
        )
        
        raw_text = response.outputs[0].content
        
        # ========== DEBUG PRINT ==========
        print("\n" + "="*80)
        print("🔍 RECIPE AGENT RESPONSE - RAW:")
        print("="*80)
        print(raw_text)
        print("="*80 + "\n")
        # =================================
        
        json_recipe = parse_agent_json(raw_text)
        
        # ========== DEBUG PRINT ==========
        print("\n" + "="*80)
        print("🔍 RECIPE AGENT RESPONSE - PARSED JSON:")
        print("="*80)
        print(json.dumps(json_recipe, indent=2, ensure_ascii=False))
        print("="*80 + "\n")
        # =================================
        
        return json_recipe
    
    except Exception as e:
        current_app.logger.error(f"Recipe parsing error: {e}")
        raise Exception(f"Failed to parse recipe from OCR: {str(e)}")