import os
import json
import re
from mistralai import Mistral
from flask import current_app
from flask_babel import gettext as _


DISH_IDEAS_PROMPT = """You are an expert chef specializing in creative cuisine. Your task is to suggest dish ideas based on available ingredients.

Always respond in this exact JSON format:
{
  "dish_ideas": ["Dish title 1", "Dish title 2", ...]
}

Key guidelines:
- When told to use only specific ingredients, restrict to those plus common staples (oil, salt, pasta, rice, onions, garlic, etc.)
- When allowed to add ingredients, focus on complementing the provided ones while keeping the original ingredients central
- Ensure all dishes are practical and realistically cookable
- Provide diverse suggestions across different cuisines and cooking methods
- Keep titles clear and appetizing
- Use standard recipe naming conventions

The titles should be specific enough to understand the main components but concise enough to be readable."""

CREATE_RECIPE_PROMPT = """You are an experienced chef and recipe writer. Your task is to create detailed, practical recipes that are easy to follow.

Always respond in this exact JSON format:
{
  "title": "Recipe title",
  "description": "Brief description of the dish and its key features",
  "notes": ["Helpful tips", "Serving suggestions", "Storage advice"],
  "ingredients": {
    "servings": 4,
    "items": {
      "ingredient name": "precise quantity and any preparation notes"
    }
  },
  "instructions": [
    "Clear step-by-step instructions",
    "Each step as a complete sentence"
  ]
}

Key guidelines:
- Write clear, precise instructions in a step-by-step format
- Include exact measurements and quantities
- Add helpful notes about preparation, storage, or variations
- Ensure ingredients list matches the instructions exactly
- Keep the recipe practical and achievable for home cooks
- Include tips for best results and common pitfalls to avoid

Each instruction should be a complete, actionable sentence."""


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
    """Interface to Mistral AI for recipe generation"""

    def __init__(self):
        self.api_key = os.environ.get("COOK_AGENT_KEY")
        if not self.api_key:
            raise ValueError(_("COOK_AGENT_KEY must be set in environment"))
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

        user_input = f"Create {num_ideas} recipe ideas using these ingredients: {', '.join(ingredients_list)}. "
        if use_only:
            user_input += "Use ONLY these ingredients plus basic kitchen staples (salt, oil, etc)."
        else:
            user_input += "You can suggest additional complementary ingredients."

        try:
            response = self.client.chat.complete(
                messages=[
                    {"role": "system", "content": DISH_IDEAS_PROMPT},
                    {"role": "user", "content": user_input},
                ],
                model="mistral-large-latest",
                temperature=0.7,
                response_format={"type": "json_object"},
                safe_prompt=True,
            )

            raw_text = response.choices[0].message.content
            data = parse_agent_json(raw_text)
            return data.get("dish_ideas", [])

        except Exception as e:
            current_app.logger.error(f"Error generating dish ideas: {e}")
            raise Exception(
                _("Failed to generate dish ideas: %(error)s") % {"error": str(e)}
            )

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
        user_input = f"Create a detailed recipe for '{title}' using these ingredients: {', '.join(ingredients_list)}. "
        if use_only:
            user_input += "Use ONLY these ingredients plus basic kitchen staples (salt, oil, etc)."
        else:
            user_input += "You can suggest additional complementary ingredients."

        try:
            response = self.client.chat.complete(
                messages=[
                    {"role": "system", "content": CREATE_RECIPE_PROMPT},
                    {"role": "user", "content": user_input},
                ],
                model="mistral-large-latest",
                temperature=0.7,
                response_format={"type": "json_object"},
                safe_prompt=True,
            )

            raw_text = response.choices[0].message.content

            # ========== DEBUG PRINT ==========
            print("\n" + "=" * 80)
            print("🔍 RAW API RESPONSE:")
            print("=" * 80)
            print(raw_text)
            print("=" * 80)
            # =================================

            data = parse_agent_json(raw_text)

            # ========== DEBUG PRINT ==========
            print("\n" + "=" * 80)
            print("🔍 PARSED JSON:")
            print("=" * 80)
            import json

            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("=" * 80 + "\n")
            # =================================

            # Validate required fields
            required_fields = ["title", "description", "ingredients", "instructions"]
            for field in required_fields:
                if field not in data:
                    raise ValueError(
                        _("Missing required field: %(field)s") % {"field": field}
                    )

            return data

        except Exception as e:
            current_app.logger.error(f"Error generating recipe: {e}")
            raise Exception(
                _("Failed to generate recipe: %(error)s") % {"error": str(e)}
            )


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
    print("\n" + "=" * 80)
    print("🔍 CONVERTING AI RECIPE:")
    print("=" * 80)
    print(f"ingredients field type: {type(ai_recipe.get('ingredients'))}")
    print(f"ingredients field value: {ai_recipe.get('ingredients')}")
    print("=" * 80 + "\n")
    # =================================

    # Parse ingredients
    ingredients_data = ai_recipe.get("ingredients")

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
        servings = ingredients_data.get("servings", 6)
        ingredients_dict = ingredients_data.get("items", {})
        if ingredients_dict == {} and len(ingredients_data.keys() - {"servings"}) == 1:
            # Fallback: AI returned just the ingredients dict without 'items' key
            ingredients_dict = ingredients_data.get(
                list(ingredients_data.keys() - {"servings"})[0], {}
            )
        print(f"✅ Extracted servings: {servings}")
        print(f"✅ Extracted ingredients: {list(ingredients_dict.keys())[:3]}...")

    else:
        print(f"❌ Unexpected ingredients format: {type(ingredients_data)}")

    result = {
        "title": ai_recipe.get("title", _("Untitled Recipe")),
        "description": ai_recipe.get("description", ""),
        "servings": servings,
        "ingredients": ingredients_dict,
        "instructions": ai_recipe.get("instructions", []),
        "notes": ai_recipe.get("notes", []),
        "tags": [_("AI-generated")],
    }

    # ========== DEBUG PRINT ==========
    print("\n" + "=" * 80)
    print("🔍 CONVERTED RESULT:")
    print("=" * 80)
    import json

    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("=" * 80 + "\n")
    # =================================

    return result
