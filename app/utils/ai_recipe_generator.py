import os
import json
import re
from mistralai import Mistral
from flask import current_app
from flask_babel import gettext as _


def parse_agent_json(text: str):
    """
    Extracts JSON from a string that may be wrapped in Markdown code fences.
    Returns a Python dict, or raises json.JSONDecodeError if invalid.
    """
    # Remove ```json or ``` at the start and ``` at the end
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```", "", text)
    text = re.sub(r"```$", "", text)
    # Strip leading/trailing whitespace
    text = text.strip()
    # Parse JSON
    return json.loads(text)


class MistralRecipeGenerator:
    """Interface to Mistral AI agent for recipe generation"""
    
    def __init__(self):
        self.api_key = os.environ.get("COOK_AGENT_KEY")
        self.agent_id = os.environ.get("AGENT_ID")
        
        if not self.api_key or not self.agent_id:
            raise ValueError(_("COOK_AGENT_KEY and AGENT_ID must be set in environment"))
        
        self.client = Mistral(api_key=self.api_key)
    
    def generate_dish_ideas(self, ingredients_list, num_ideas=10, use_only=False):
        """
        Generate dish title ideas from ingredients
        
        Args:
            ingredients_list: List of ingredient strings
            num_ideas: Number of dish ideas to generate (max 20)
            use_only: Whether to use only these ingredients + staples
            
        Returns:
            list: List of dish title strings
            
        Raises:
            Exception: If API call fails
        """
        num_ideas = min(num_ideas, 20)  # Cap at 20
        
        user_input = f'dish_ideas(len={num_ideas}, list={ingredients_list}, use_only={use_only})'
        
        try:
            response = self.client.beta.conversations.start(
                agent_id=self.agent_id,
                inputs=user_input
            )
            
            raw_text = response.outputs[0].content
            data = parse_agent_json(raw_text)
            
            return data.get('dish_ideas', [])
        
        except Exception as e:
            current_app.logger.error(f"Error generating dish ideas: {e}")
            raise Exception(_("Failed to generate dish ideas: %(error)s") % {"error": str(e)})
    
    def generate_recipe(self, title, ingredients_list, use_only=False):
        """
        Generate a full recipe from title and ingredients
        
        Args:
            title: Dish title
            ingredients_list: List of ingredient strings
            use_only: Whether to use only these ingredients + staples
            
        Returns:
            dict: Recipe data with keys: title, description, notes, ingredients, instructions
            
        Raises:
            Exception: If API call fails
        """
        user_input = f'recipe(title="{title}", list={ingredients_list}, use_only={use_only})'
        
        try:
            response = self.client.beta.conversations.start(
                agent_id=self.agent_id,
                inputs=user_input
            )
            
            raw_text = response.outputs[0].content
            
            # ========== DEBUG PRINT ==========
            print("\n" + "="*80)
            print("🔍 RAW API RESPONSE:")
            print("="*80)
            print(raw_text)
            print("="*80)
            # =================================
            
            data = parse_agent_json(raw_text)
            
            # ========== DEBUG PRINT ==========
            print("\n" + "="*80)
            print("🔍 PARSED JSON:")
            print("="*80)
            import json
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("="*80 + "\n")
            # =================================
            
            # Validate required fields
            required_fields = ['title', 'description', 'ingredients', 'instructions']
            for field in required_fields:
                if field not in data:
                    raise ValueError(_("Missing required field: %(field)s") % {"field": field})
            
            return data
        
        except Exception as e:
            current_app.logger.error(f"Error generating recipe: {e}")
            raise Exception(_("Failed to generate recipe: %(error)s") % {"error": str(e)})


def convert_ai_recipe_to_model_format(ai_recipe):
    """
    Convert AI recipe format to our Recipe model format
    
    AI format:
    {
        "title": "...",
        "description": "...",
        "notes": ["note1", "note2"],
        "ingredients": { servings: 6, items: { "ingredient": "quantity and form, description", ... } },
        "instructions": ["step1", "step2"]
    }
    
    Returns:
        dict: Format compatible with Recipe.from_dict()
    """
    servings = 6  # Default
    ingredients_dict = {}
    
    # ========== DEBUG PRINT ==========
    print("\n" + "="*80)
    print("🔍 CONVERTING AI RECIPE:")
    print("="*80)
    print(f"ingredients field type: {type(ai_recipe.get('ingredients'))}")
    print(f"ingredients field value: {ai_recipe.get('ingredients')}")
    print("="*80 + "\n")
    # =================================
    
    # Parse ingredients
    ingredients_data = ai_recipe.get('ingredients')
    
    if isinstance(ingredients_data, list):
        if len(ingredients_data) >= 2:
            # Expected format: [servings, {ingredient: description}]
            servings = ingredients_data[0]
            ingredients_dict = ingredients_data[1]
            
            print(f"✅ Extracted servings: {servings}")
            print(f"✅ Extracted ingredients: {list(ingredients_dict.keys())[:3]}...")
        elif len(ingredients_data) == 1:
            # Fallback: only dict provided
            if isinstance(ingredients_data[0], dict):
                ingredients_dict = ingredients_data[0]
                print("⚠️ Only ingredients dict found, using default servings=6")
            elif isinstance(ingredients_data[0], int):
                servings = ingredients_data[0]
                print(f"⚠️ Only servings found: {servings}, no ingredients!")
        else:
            print("❌ Empty ingredients list!")
    
    elif isinstance(ingredients_data, dict):
        # Expected output: AI returned dict { "servings": 6, "items": { "ingredient": "quantity and form, description", ... } }
        servings = ingredients_data.get('servings', 6)
        ingredients_dict = ingredients_data.get('items', {})
        if ingredients_dict == {} and len(ingredients_data.keys() - {'servings'}) == 1:
            # Fallback: AI returned just the ingredients dict without 'items' key
            ingredients_dict = ingredients_data.get(list(ingredients_data.keys() - {'servings'})[0], {})
        print(f"✅ Extracted servings: {servings}")
        print(f"✅ Extracted ingredients: {list(ingredients_dict.keys())[:3]}...")
    
    else:
        print(f"❌ Unexpected ingredients format: {type(ingredients_data)}")
    
    result = {
        'title': ai_recipe.get('title', _('Untitled Recipe')),
        'description': ai_recipe.get('description', ''),
        'servings': servings,
        'ingredients': ingredients_dict,
        'instructions': ai_recipe.get('instructions', []),
        'notes': ai_recipe.get('notes', []),
        'tags': [_('AI-generated')]
    }
    
    # ========== DEBUG PRINT ==========
    print("\n" + "="*80)
    print("🔍 CONVERTED RESULT:")
    print("="*80)
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("="*80 + "\n")
    # =================================
    
    return result