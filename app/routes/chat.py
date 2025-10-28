from flask import Blueprint, render_template, request, session, url_for, current_app
from flask_login import login_required, current_user
from flask_babel import gettext as _, get_locale
from datetime import datetime
import json
import os
import uuid
import urllib.parse

from app import db
from app.models import ChatMessage
from app.utils.llm_client import LLMClient

bp = Blueprint("chat", __name__, url_prefix="/chat")


def get_llm_client():
    """Get LLM client instance"""
    provider = os.environ.get("LLM_PROVIDER", "mistral")
    return LLMClient(provider=provider)


def get_or_create_conversation_id():
    """Get current conversation ID from session or create new one"""
    if "current_conversation_id" not in session:
        session["current_conversation_id"] = str(uuid.uuid4())
        session.modified = True
    return session["current_conversation_id"]


def get_chat_history(conversation_id, limit=20):
    """Get chat history from database"""
    messages = (
        ChatMessage.query.filter_by(
            user_id=current_user.id, conversation_id=conversation_id
        )
        .order_by(ChatMessage.timestamp.desc())
        .limit(limit)
        .all()
    )

    current_app.logger.info(
        f"Fetched {len(messages)} messages for conversation {conversation_id}"
    )

    # Reverse to get chronological order
    return [msg.to_dict() for msg in reversed(messages)]


def save_message(conversation_id, role, content, metadata=None):
    """Save message to database"""
    message = ChatMessage(
        conversation_id=conversation_id,
        user_id=current_user.id,
        role=role,
        content=content,
    )
    db.session.add(message)
    db.session.commit()
    return message


@bp.route("/toggle")
@login_required
def toggle():
    """Toggle chat window open/closed"""
    return render_template("components/chat_window.html")


@bp.route("/minimize")
@login_required
def minimize():
    """Minimize chat window"""
    return '<div id="chat-window" class="hidden"></div>'


@bp.route("/messages")
@login_required
def get_messages():
    """Load chat history"""
    conversation_id = get_or_create_conversation_id()
    current_app.logger.info(f"Loading messages for conversation {conversation_id}")
    chat_history = get_chat_history(conversation_id)
    return render_template("components/chat_messages.html", messages=chat_history)


@bp.route("/send", methods=["POST"])
@login_required
def send_message():
    """Send message to LLM and get response"""
    from flask import current_app

    user_message = request.form.get("message", "").strip()
    current_app.logger.info(f"User message: {user_message}")

    if not user_message:
        current_app.logger.warning("Empty message received")
        return "", 400

    conversation_id = get_or_create_conversation_id()
    current_app.logger.info(f"Conversation ID: {conversation_id}")

    # Save user message
    try:
        save_message(conversation_id, "user", user_message)
        current_app.logger.info("User message saved to DB")
    except Exception as e:
        current_app.logger.error(f"Error saving message: {str(e)}")
        raise

    # Get LLM response
    try:
        chat_history = get_chat_history(conversation_id)
        response = get_llm_response(user_message, chat_history)
        save_message(conversation_id, "assistant", response["content"])

        # Check if there's an action to perform
        action_html = ""
        if response.get("metadata", {}).get("action") == "save_recipe":
            recipe_data = response["metadata"].get("recipe_data", {})
            prefill_json = urllib.parse.quote(json.dumps(recipe_data))
            action_html = f"""
            <div class="mt-2 pt-2 border-t border-white/20">
                <a href="{url_for('main.recipe_new', prefill=prefill_json)}"
                   class="text-sm text-orange-600 hover:text-orange-700 underline flex items-center gap-1">
                    📝 {_('Create this recipe')} →
                </a>
            </div>
            """

        # Return ONLY assistant message
        assistant_html = render_template(
            "components/chat_message.html",
            message={"role": "assistant", "content": response["content"]},
        )

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
    """Start new conversation"""
    # Generate new conversation ID
    session["current_conversation_id"] = str(uuid.uuid4())
    session.modified = True
    return "", 204


@bp.route("/conversations")
@login_required
def list_conversations():
    """Get list of user's conversations (for future feature)"""
    conversations = (
        db.session.query(
            ChatMessage.conversation_id,
            db.func.min(ChatMessage.timestamp).label("started"),
            db.func.max(ChatMessage.timestamp).label("last_message"),
            db.func.count(ChatMessage.id).label("message_count"),
        )
        .filter_by(user_id=current_user.id)
        .group_by(ChatMessage.conversation_id)
        .order_by(db.desc("last_message"))
        .all()
    )

    return render_template(
        "components/chat_conversations.html", conversations=conversations
    )


def get_llm_response(user_message, chat_history):
    """Get response from LLM with user's language context"""
    user_language = get_locale()
    language_names = {"en": "English", "de": "German", "es": "Spanish", "fr": "French"}
    language_name = language_names.get(user_language, "English")

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

    messages = [{"role": "system", "content": system_prompt}]

    # Add recent chat history (last 10 messages)
    for msg in chat_history[-10:]:
        if msg["role"] in ["user", "assistant"]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    try:
        llm_client = get_llm_client()
        response = llm_client.chat_completion(
            messages=messages, temperature=0.7, max_tokens=2000
        )

        metadata = response.get("metadata", {})
        if should_extract_recipe(user_message, response["content"]):
            recipe_data = extract_recipe_from_conversation(
                chat_history, response["content"]
            )
            metadata["action"] = "save_recipe"
            metadata["recipe_data"] = recipe_data

        return {"content": response["content"], "metadata": metadata}

    except Exception as e:
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
    """Extract recipe details from conversation using LLM"""
    try:
        user_language = get_locale()

        conversation_text = (
            "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history[-5:]])
            + f"\nassistant: {latest_response}"
        )

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

        content = extraction_response["content"].strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        recipe_data = json.loads(content)
        return recipe_data

    except Exception as e:
        from flask import current_app

        current_app.logger.error(f"Recipe extraction error: {str(e)}")
        return {
            "title": _("Recipe from conversation"),
            "description": _("Recipe discussed in chat"),
            "servings": 4,
            "ingredients": _("ingredient | amount"),
            "instructions": _("Add instructions here"),
            "notes": "",
            "tags": _("chat, custom"),
        }
