from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    flash,
    session,
    current_app,
)
from app import db
from app.models import Recipe
from flask_babel import gettext as _
from app.utils.ai_recipe_generator import (
    MistralRecipeGenerator,
    convert_ai_recipe_to_model_format,
)
from app.utils.geo import get_user_country

bp = Blueprint("ai_recipes", __name__, url_prefix="/ai")


@bp.route("/")
def index():
    """AI recipe generation page"""
    # Get history from session
    history = session.get("dish_ideas_history", [])
    return render_template("ai_recipes.html", history=history)


@bp.route("/generate-ideas", methods=["POST"])
def generate_ideas():
    """AJAX endpoint to generate dish ideas"""
    try:
        # Get form data
        mode = request.json.get("mode", "ingredients")
        ingredients_text = request.json.get("ingredients", "")
        use_only = request.json.get("use_only", False)
        description = request.json.get("description", "")
        vegetarian = request.json.get("vegetarian", False)
        vegan = request.json.get("vegan", False)
        seasonal = request.json.get("seasonal", False)
        allergies = request.json.get("allergies", "")
        difficulty = request.json.get("difficulty", "indifferent")
        user_location, user_latitude = get_user_country()
        num_ideas = int(request.json.get("num_ideas", 10))

        if mode == "ingredients":
            ingredients_list = [
                ing.strip() for ing in ingredients_text.split(",") if ing.strip()
            ]
            if not ingredients_list:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": _("Please enter at least one ingredient"),
                        }
                    ),
                    400,
                )
        else:
            ingredients_list = []  # empty for description mode
            if not description.strip():
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": _("Please enter a description"),
                        }
                    ),
                    400,
                )

        # Generate ideas
        generator = MistralRecipeGenerator()
        dish_ideas = generator.generate_dish_ideas(
            mode=mode,
            ingredients_list=ingredients_list if mode == "ingredients" else [],
            description=description if mode == "description" else "",
            num_ideas=num_ideas,
            use_only=use_only,
            vegetarian=vegetarian,
            vegan=vegan,
            seasonal=seasonal,
            allergies=allergies,
            difficulty=difficulty,
            user_location=user_location,
        )

        # Store in session for history
        history_entry = {
            "mode": mode,
            "ingredients": ingredients_list,
            "description": description,
            "use_only": use_only,
            "num_ideas": num_ideas,
            "vegetarian": vegetarian,
            "vegan": vegan,
            "seasonal": seasonal,
            "allergies": allergies,
            "difficulty": difficulty,
            "dishes": dish_ideas,
        }

        # Update history (keep last 5)
        history = session.get("dish_ideas_history", [])
        history.insert(0, history_entry)
        history = history[:5]  # Keep only last 5
        session["dish_ideas_history"] = history

        return jsonify(
            {
                "success": True,
                "dish_ideas": dish_ideas,
                "mode": mode,
                "ingredients": ingredients_list,
                "description": description,
                "use_only": use_only,
                "vegetarian": vegetarian,
                "vegan": vegan,
                "seasonal": seasonal,
                "allergies": allergies,
                "difficulty": difficulty,
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/generate-recipe", methods=["POST"])
def generate_recipe():
    """AJAX endpoint to generate a full recipe"""
    try:
        data = request.json

        title = data.get("title", "")
        mode = data.get("mode", "ingredients")
        ingredients_list = data.get("ingredients", [])
        description = data.get("description", "")
        use_only = data.get("use_only", False)
        vegetarian = data.get("vegetarian", False)
        vegan = data.get("vegan", False)
        seasonal = data.get("seasonal", False)
        allergies = data.get("allergies", "")
        difficulty = data.get("difficulty", "indifferent")

        # Validate required inputs
        if not title:
            return (
                jsonify({"success": False, "error": _("Dish title is required")}),
                400,
            )

        if mode == "ingredients" and not ingredients_list:
            return (
                jsonify({"success": False, "error": _("Ingredients list is required")}),
                400,
            )

        if mode == "description" and not description:
            return (
                jsonify({"success": False, "error": _("Description is required")}),
                400,
            )

        user_location, user_latitude = get_user_country()

        generator = MistralRecipeGenerator()
        ai_recipe = generator.generate_recipe(
            title=title,
            ingredients_list=ingredients_list,
            use_only=use_only,
            mode=mode,
            description=description,
            vegetarian=vegetarian,
            vegan=vegan,
            seasonal=seasonal,
            allergies=allergies,
            difficulty=difficulty,
            user_location=user_location,
        )

        recipe_data = convert_ai_recipe_to_model_format(
            ai_recipe,
            title=title,
            ingredients_list=ingredients_list,
            use_only=use_only,
            mode=mode,
            description=description,
            vegetarian=vegetarian,
            vegan=vegan,
            seasonal=seasonal,
            allergies=allergies,
            difficulty=difficulty,
            user_latitude=user_latitude,
        )

        return jsonify({"success": True, "recipe": recipe_data})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/save-recipe", methods=["POST"])
def save_recipe():
    """Save AI-generated recipe to database"""
    try:
        recipe_data = request.json.get("recipe")

        if not recipe_data:
            return (
                jsonify({"success": False, "error": _("Recipe data is required")}),
                400,
            )

        if "user_id" not in session:
            flash(_("Please log in first."), "warning")
            return redirect(url_for("auth.login"))

        user_id = session["user_id"]
        # Create recipe from data
        recipe = Recipe.from_dict(recipe_data, user_id=user_id)

        db.session.add(recipe)
        db.session.flush()
        recipe.original_id = recipe.id
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "recipe_id": recipe.id,
                "message": _("Recipe saved successfully!"),
            }
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/clear-history", methods=["POST"])
def clear_history():
    """Clear dish ideas history"""
    session["dish_ideas_history"] = []
    return jsonify({"success": True})
