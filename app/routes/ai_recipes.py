from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from app import db
from app.models import Recipe
from flask_babel import gettext as _
from app.utils.ai_recipe_generator import MistralRecipeGenerator, convert_ai_recipe_to_model_format

bp = Blueprint('ai_recipes', __name__, url_prefix='/ai')


@bp.route('/')
def index():
    """AI recipe generation page"""
    # Get history from session
    history = session.get('dish_ideas_history', [])
    return render_template('ai_recipes.html', history=history)


@bp.route('/generate-ideas', methods=['POST'])
def generate_ideas():
    """AJAX endpoint to generate dish ideas"""
    try:
        # Get form data
        ingredients_text = request.json.get('ingredients', '')
        num_ideas = int(request.json.get('num_ideas', 10))
        use_only = request.json.get('use_only', False)
        
        # Parse ingredients
        ingredients_list = [ing.strip() for ing in ingredients_text.split(',') if ing.strip()]
        
        if not ingredients_list:
            return jsonify({'success': False, 'error': _('Please enter at least one ingredient')}), 400
        
        # Generate ideas
        generator = MistralRecipeGenerator()
        dish_ideas = generator.generate_dish_ideas(ingredients_list, num_ideas, use_only)
        
        # Store in session for history
        history_entry = {
            'ingredients': ingredients_list,
            'use_only': use_only,
            'num_ideas': num_ideas,
            'dishes': dish_ideas
        }
        
        # Update history (keep last 5)
        history = session.get('dish_ideas_history', [])
        history.insert(0, history_entry)
        history = history[:5]  # Keep only last 5
        session['dish_ideas_history'] = history
        
        return jsonify({
            'success': True,
            'dish_ideas': dish_ideas,
            'ingredients': ingredients_list,
            'use_only': use_only
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/generate-recipe', methods=['POST'])
def generate_recipe():
    """AJAX endpoint to generate a full recipe"""
    try:
        # Get form data
        title = request.json.get('title', '')
        ingredients_list = request.json.get('ingredients', [])
        use_only = request.json.get('use_only', False)
        
        if not title:
            return jsonify({'success': False, 'error': _('Dish title is required')}), 400
        
        if not ingredients_list:
            return jsonify({'success': False, 'error': _('Ingredients list is required')}), 400
        
        # Generate recipe
        generator = MistralRecipeGenerator()
        ai_recipe = generator.generate_recipe(title, ingredients_list, use_only)
        
        # Convert to our format
        recipe_data = convert_ai_recipe_to_model_format(ai_recipe)
        
        return jsonify({
            'success': True,
            'recipe': recipe_data
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/save-recipe', methods=['POST'])
def save_recipe():
    """Save AI-generated recipe to database"""
    try:
        recipe_data = request.json.get('recipe')
        
        if not recipe_data:
            return jsonify({'success': False, 'error': _('Recipe data is required')}), 400
        
        if "user_id" not in session:
            flash(_("Please log in first."), "warning")
            return redirect(url_for("auth.login"))
        
        user_id = session['user_id']
        # Create recipe from data
        recipe = Recipe.from_dict(recipe_data, user_id=user_id)
        
        db.session.add(recipe)
        db.session.flush()
        recipe.original_id = recipe.id
        db.session.commit()
        
        return jsonify({
            'success': True,
            'recipe_id': recipe.id,
            'message': _('Recipe saved successfully!')
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/clear-history', methods=['POST'])
def clear_history():
    """Clear dish ideas history"""
    session['dish_ideas_history'] = []
    return jsonify({'success': True})