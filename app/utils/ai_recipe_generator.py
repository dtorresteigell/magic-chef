import os
import json
import re
from mistralai import Mistral
from flask import current_app
from flask_babel import gettext as _
from datetime import datetime
from app.utils.geo import get_season_tag_from_latitude


DISH_IDEAS_PROMPT_INGREDIENTS = """You are an expert chef specializing in creative cuisine. Your task is to suggest dish ideas based on available ingredients.

Always respond in this exact JSON format:
{
  "dish_ideas": ["Dish title 1", "Dish title 2", ...]
}

Key guidelines:
- When told to use only specific ingredients, restrict to those plus common staples (oil, salt, pasta, rice, onions, garlic, etc.)
- When allowed to add ingredients, focus on complementing the provided ones while keeping the original ingredients central
- Ensure all dishes are practical and realistically cookable
- Provide diverse suggestions across different cuisines and cooking methods
- Use standard recipe naming conventions
- Respect all restrictions (dietary, seasonal, allergy, difficulty)
- Keep titles clear, appetizing, and specific enough to understand the main components
"""

DISH_IDEAS_PROMPT_DESCRIPTION = """You are an expert chef specializing in creative cuisine. Your task is to suggest dish ideas based on a free-form description provided by the user.

Always respond in this exact JSON format:
{
  "dish_ideas": ["Dish title 1", "Dish title 2", ...]
}

Key guidelines:
- Focus on interpreting the description and creating diverse, realistic dishes that fit it
- Respect all restrictions (dietary, seasonal, allergy, difficulty)
- Keep titles clear, appetizing, and specific enough to understand the main components
"""


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
- Each instruction should be a complete, actionable sentence
- Ensure ingredients list matches the instructions exactly
- Include exact measurements and quantities
- Add helpful notes about preparation, storage, or variations
- Keep the recipe practical and achievable for home cooks
- Include tips for best results and common pitfalls to avoid"""


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

    def generate_dish_ideas(
        self,
        mode="ingredients",
        ingredients_list=None,
        description="",
        num_ideas=10,
        use_only=False,
        vegetarian=False,
        vegan=False,
        seasonal=False,
        allergies="",
        difficulty="indifferent",
        user_location="Germany",
    ):
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
        num_ideas = min(num_ideas, 20)

        system_prompt = (
            DISH_IDEAS_PROMPT_INGREDIENTS
            if mode == "ingredients"
            else DISH_IDEAS_PROMPT_DESCRIPTION
        )

        if mode == "ingredients":
            user_input = f"Create {num_ideas} recipe ideas using these ingredients: {', '.join(ingredients_list)}. "
            if use_only:
                user_input += (
                    "Use ONLY these ingredients plus basic staples (salt, oil, etc). "
                )
            else:
                user_input += "You can suggest additional complementary ingredients. "
        else:
            user_input = f"Create {num_ideas} dish ideas based on this description: '{description}'. "

        # Options and restrictions
        extra_lines = []
        if vegan:
            extra_lines.append(
                "All dishes must be strictly vegan (no animal products at all)."
            )
        elif vegetarian:  # only if not vegan
            extra_lines.append(
                "All dishes must be strictly vegetarian (no meat or fish)."
            )
        if seasonal:
            extra_lines.append(
                f"Use only seasonal ingredients available around {user_location} in {datetime.now().strftime('%B')}."
            )
        if allergies:
            extra_lines.append(
                f"DO NOT USE THE FOLLOWING INGREDIENTS UNDER ANY CIRCUMSTANCES: {allergies.upper()}."
            )
        if difficulty != "indifferent":
            extra_lines.append(
                f"All recipes should have a {difficulty} difficulty level."
            )

        user_input += " ".join(extra_lines)

        current_app.logger.debug(f"Generating dish ideas with input: {user_input}")

        try:
            response = self.client.chat.complete(
                messages=[
                    {"role": "system", "content": system_prompt},
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

    def generate_recipe(
        self,
        title,
        ingredients_list=None,
        use_only=False,
        mode="ingredients",
        description="",
        vegetarian=False,
        vegan=False,
        seasonal=False,
        allergies="",
        difficulty="indifferent",
        user_location="Germany",
        debug=False,
    ):
        """
        Generate a full recipe considering all user parameters.
        """
        ingredients_list = ingredients_list or []

        # ---------- 1. Construct context dynamically ----------
        context_lines = []

        if mode == "ingredients":
            line = f"- The recipe should be based on these ingredients: {', '.join(ingredients_list)}"
            if use_only:
                line += "- Use ONLY these ingredients plus basic kitchen staples (salt, pepper, oil, water, etc.)"
            else:
                line += "- You can include a few additional complementary ingredients"
            context_lines.append(line)
        elif mode == "description":
            context_lines.append(
                f"- The recipe should be inspired by this description: {description}"
            )

        if vegan:
            context_lines.append("- The recipe must be fully vegan")
        elif vegetarian:  # only if not vegan
            context_lines.append("- The recipe must be fully vegetarian")
        if seasonal:
            context_lines.append(
                f"- Use only seasonal ingredients available around {user_location} in {datetime.now().strftime('%B')}"
            )
        if allergies:
            context_lines.append(
                f"- DO NOT USE THE FOLLOWING INGREDIENTS UNDER ANY CIRCUMSTANCES: {allergies}."
            )
        if difficulty and difficulty != "indifferent":
            context_lines.append(f"- The recipe difficulty should be {difficulty}")

        # Join all context lines neatly
        dynamic_context = "\n".join(context_lines)

        # ---------- 2. Build the final system prompt ----------
        final_prompt = f"{CREATE_RECIPE_PROMPT}\n{dynamic_context}"

        # ---------- 3. Send to model ----------
        try:
            response = self.client.chat.complete(
                messages=[
                    {"role": "system", "content": final_prompt},
                    {
                        "role": "user",
                        "content": f"Create a detailed recipe for '{title}'.",
                    },
                ],
                model="mistral-large-latest",
                temperature=0.7,
                response_format={"type": "json_object"},
                safe_prompt=True,
            )

            raw_text = response.choices[0].message.content
            data = parse_agent_json(raw_text)

            # Validate required fields
            required_fields = ["title", "description", "ingredients", "instructions"]
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")

            return data

        except Exception as e:
            current_app.logger.error(f"Error generating recipe: {e}")
            raise Exception(f"Failed to generate recipe: {str(e)}")


def convert_ai_recipe_to_model_format(
    ai_recipe,
    title,
    ingredients_list,
    use_only,
    mode,
    description,
    vegetarian,
    vegan,
    seasonal,
    allergies,
    difficulty,
    user_latitude,
    debug=False,
):
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

    Adds tags depending on parameters.

    Returns:
        dict: Format compatible with Recipe.from_dict()
    """
    servings = 6  # Default
    ingredients_dict = {}

    # ========== DEBUG PRINT ==========
    if debug:
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

    # Tags
    tags = [_("AI-generated")]

    if vegan:
        tags.append(_("vegan"))
    elif vegetarian:  # only if not vegan
        tags.append(_("vegetarian"))
    if seasonal:
        if user_latitude is not None:
            tags.append(_(get_season_tag_from_latitude(user_latitude)))
        else:
            tags.append(_("seasonal"))
    if difficulty in ["easy", "medium", "hard"]:
        tags.append(_(difficulty))
    if allergies != "":
        tags.append(_("allergy-aware"))

    result = {
        "title": ai_recipe.get("title", _("Untitled Recipe")),
        "description": ai_recipe.get("description", ""),
        "servings": servings,
        "ingredients": ingredients_dict,
        "instructions": ai_recipe.get("instructions", []),
        "notes": ai_recipe.get("notes", []),
        "tags": tags,
    }

    # ========== DEBUG PRINT ==========
    if debug:
        print("\n" + "=" * 80)
        print("🔍 CONVERTED RESULT:")
        print("=" * 80)
        import json

        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("=" * 80 + "\n")
    # =================================

    return result
