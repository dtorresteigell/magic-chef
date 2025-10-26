from flask import (
    Blueprint,
    render_template,
    request,
    session,
    jsonify,
    url_for,
    current_app,
)
from flask_login import login_required, current_user
from flask_babel import gettext as _, get_locale
import mistralai  # or your LLM library
import json
import os
from datetime import datetime

from app.utils.llm_client import LLMClient
from app.utils.ai_recipe_generator import parse_agent_json

bp = Blueprint("chat", __name__, url_prefix="/chat")


# Initialize LLM client (defaults to Mistral)
def get_llm_client():
    """Get LLM client instance"""
    provider = os.environ.get("LLM_PROVIDER", "mistral")
    return LLMClient(provider=provider)


def get_chat_history():
    """Get chat history from session"""
    from flask import current_app

    current_app.logger.info("Retrieving chat history from session")
    if "chat_history" not in session:
        session["chat_history"] = []
    current_app.logger.info(f"Current chat history: {session['chat_history']}")
    return session["chat_history"]


def save_message(role, content, metadata=None):
    """Save message to session"""
    chat_history = get_chat_history()
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "metadata": metadata or {},
    }
    chat_history.append(message)
    session["chat_history"] = chat_history
    session.modified = True


@bp.route("/toggle")
@login_required
def toggle():
    """Toggle chat window open/closed"""
    is_open = request.args.get("open", "true") == "true"
    if is_open:
        return render_template("components/chat_window.html")
    else:
        return '<div id="chat-window" class="hidden"></div>'


@bp.route("/minimize")
@login_required
def minimize():
    """Minimize chat window"""
    return '<div id="chat-window" class="hidden"></div>'


@bp.route("/messages")
@login_required
def get_messages():
    """Load chat history"""
    chat_history = get_chat_history()
    return render_template("components/chat_messages.html", messages=chat_history)


@bp.route("/send", methods=["POST"])
@login_required
def send_message():
    """Send message to LLM and get response"""
    user_message = request.form.get("message", "").strip()

    if not user_message:
        return "", 400

    # Save user message (frontend already displayed it)
    save_message("user", user_message)

    # Get LLM response
    try:
        from flask import current_app

        current_app.logger.info(f"User message: {user_message}")
        print(f"User message!!!!: {user_message}")

        chat_history = get_chat_history()
        current_app.logger.info(f"Chat history before LLM call: {chat_history}")
        print(f"Chat history before LLM call: {chat_history}")

        response = get_llm_response(user_message, get_chat_history())
        current_app.logger.info(f"LLM response: {response}")
        save_message("assistant", response["content"], response.get("metadata"))

        # Check if there's an action to perform
        action_html = ""
        if response.get("metadata", {}).get("action") == "save_recipe":
            recipe_data = response["metadata"].get("recipe_data", {})
            current_app.logger.info(f"Recipe data to prefill: {recipe_data}")
            # URL-encode the JSON data
            import urllib.parse

            prefill_json = urllib.parse.quote(json.dumps(recipe_data))
            current_app.logger.info(f"Prefill JSON (URL-encoded): {prefill_json}")
            action_html = f"""
            <div class="mt-2 pt-2 border-t border-white/20">
                <a href="{url_for('main.recipe_new', prefill=prefill_json)}"
                   class="text-sm text-orange-600 hover:text-orange-700 underline flex items-center gap-1">
                    📝 {_('Create this recipe')} →
                </a>
            </div>
            """
            current_app.logger.info(f"Action HTML: {action_html}")

        # Return ONLY assistant message (user message already shown by frontend)
        assistant_html = render_template(
            "components/chat_message.html",
            message={"role": "assistant", "content": response["content"]},
        )

        # Add action button if needed
        if action_html:
            assistant_html = assistant_html.replace("</div>", action_html + "</div>")

        return assistant_html

    except Exception as e:
        from flask import current_app

        current_app.logger.error(f"Chat error: {str(e)}")
        error_msg = _("Sorry, I encountered an error. Please try again.")
        return render_template(
            "components/chat_message.html",
            message={"role": "assistant", "content": error_msg},
        )


@bp.route("/clear", methods=["POST"])
@login_required
def clear_chat():
    """Clear chat history and return empty messages"""
    session["chat_history"] = []
    session.modified = True
    return ""


def get_llm_response(user_message, chat_history):
    """
    Get response from LLM with user's language context

    Returns: {'content': str, 'metadata': dict}
    """
    # Get user's language
    from flask import current_app

    current_app.logger.info(f"Getting LLM response for message: {user_message}")
    user_language = get_locale()
    current_app.logger.info(f"User language: {user_language}")
    language_names = {"en": "English", "de": "German", "es": "Spanish", "fr": "French"}
    language_name = language_names.get(user_language, "English")

    # Build system prompt with language instruction
    system_prompt = f"""You are a helpful cooking assistant. You help users with:
- Recipe suggestions and recommendations
- Cooking techniques and tips
- Ingredient substitutions
- Meal planning

IMPORTANT: Always respond in {language_name}. The user prefers to communicate in {language_name}.

When a user wants to save a recipe, extract the recipe details in a structured format with these fields:
- title: Recipe name
- description: Brief description
- servings: Number of servings (integer)
- ingredients: Format as "ingredient | description" one per line
- instructions: One step per line
- notes: Optional notes, one per line
- tags: Comma-separated tags

When you detect the user wants to save a recipe, respond with enthusiasm and let them know you'll help create it."""

    # Build messages list
    messages = [{"role": "system", "content": system_prompt}]
    current_app.logger.info(f"System prompt: {system_prompt}")
    # Add recent chat history (last 10 messages to save tokens)
    for msg in chat_history[-10:]:
        if msg["role"] in ["user", "assistant"]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    # Call LLM
    try:
        llm_client = get_llm_client()
        current_app.logger.info(f"Messages sent to LLM: {messages}")
        response = llm_client.chat_completion(
            messages=messages, temperature=0.7, max_tokens=2000
        )
        current_app.logger.info(f"LLM raw response: {response}")

        # Check if user wants to save recipe
        metadata = response.get("metadata", {})
        if should_extract_recipe(user_message, response["content"]):
            recipe_data = extract_recipe_from_conversation(
                chat_history, response["content"]
            )
            metadata["action"] = "save_recipe"
            metadata["recipe_data"] = recipe_data

        return {"content": response["content"], "metadata": metadata}

    except Exception as e:
        # Log error and return fallback
        from flask import current_app

        current_app.logger.error(f"LLM error: {str(e)}")
        raise


def should_extract_recipe(user_message: str, assistant_response: str) -> bool:
    """Check if we should extract recipe data"""
    save_keywords = [
        "save",
        "create",
        "add",
        "make this recipe",
        "speichern",
        "erstellen",
        "guardar",
        "crear",
    ]
    recipe_keywords = ["recipe", "rezept", "receta", "recette"]

    combined_text = (user_message + " " + assistant_response).lower()

    has_save = any(keyword in combined_text for keyword in save_keywords)
    has_recipe = any(keyword in combined_text for keyword in recipe_keywords)

    return has_save and has_recipe


def extract_recipe_from_conversation(chat_history, latest_response):
    """
    Extract recipe details from conversation using LLM
    """
    try:
        # Get user's language
        user_language = get_locale()
        current_app.logger.debug(f"Extracting recipe for language: {user_language}")
        current_app.logger.debug(f"Chat history: {chat_history}")
        # Build context from recent conversation
        conversation_text = (
            "\n".join(
                [
                    f"{msg['role']}: {msg['content']}"
                    for msg in chat_history[-5:]  # Last 5 messages
                ]
            )
            + f"\nassistant: {latest_response}"
        )
        current_app.logger.debug(
            f"Conversation for recipe extraction: {conversation_text}"
        )

        # Create extraction prompt
        extraction_prompt = f"""Based on the following conversation, extract recipe information and format it EXACTLY as specified:

Conversation:
{conversation_text}

Extract and format the recipe with these fields:
- title: A clear recipe name
- description: Brief description (1-2 sentences)
- servings: Number (integer, default 4 if not mentioned)
- ingredients: Format EXACTLY as "ingredient | amount and description" with one per line
- instructions: One clear step per line
- notes: Optional tips or notes, one per line
- tags: Comma-separated relevant tags

Respond with ONLY a JSON object, no other text:
{{
  "title": "Recipe Name",
  "description": "Description here",
  "servings": 4,
  "ingredients": "flour | 2 cups all-purpose\\nsugar | 1 cup white sugar\\neggs | 3 large",
  "instructions": "Step 1 instruction\\nStep 2 instruction\\nStep 3 instruction",
  "notes": "Optional note 1\\nOptional note 2",
  "tags": "tag1, tag2, tag3"
}}"""

        llm_client = get_llm_client()
        extraction_response = llm_client.chat_completion(
            messages=[{"role": "user", "content": extraction_prompt}],
            temperature=0.3,
            max_tokens=1000,
        )
        print(f"Recipe extraction response: {extraction_response}")
        # Parse JSON response
        content = extraction_response["content"].strip()
        print(f"Raw recipe extraction content: {content}")
        # Remove markdown code blocks if present
        recipe_data = parse_agent_json(content)
        # if content.startswith('```'):
        #     content = content.split('```')[1]
        #     if content.startswith('json'):
        #         content = content[4:]
        print(f"Extracted recipe JSON content: {recipe_data}")
        # recipe_data = json.loads(content)
        # print(f"Extracted recipe data: {recipe_data}")
        return recipe_data

    except Exception as e:
        current_app.logger.error(f"Recipe extraction error: {str(e)}")
        # Return a basic template
        return {
            "title": _("Recipe from conversation"),
            "description": _("Recipe discussed in chat"),
            "servings": 4,
            "ingredients": _("ingredient | amount"),
            "instructions": _("Add instructions here"),
            "notes": "",
            "tags": _("chat, custom"),
        }
