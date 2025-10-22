from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, current_app, session
from app import db
from app.utils.auth_helpers import login_required
from app.models import Recipe
import os

bp = Blueprint('table_view', __name__, url_prefix='/table')


@bp.route('/')
@login_required
def index():
    """Recipe table view"""
    if "user_id" not in session:
        flash("Please log in to see your recipes.", "info")
        return redirect(url_for("auth.login"))
    user_id = session.get('user_id', None)

    # Get all recipes with sorting
    sort_by = request.args.get('sort', 'created_at')
    order = request.args.get('order', 'desc')
    
    # Build query
    query = Recipe.query.filter_by(user_id=user_id)
    
    # Apply sorting
    if sort_by == 'title':
        query = query.order_by(Recipe.title.asc() if order == 'asc' else Recipe.title.desc())
    elif sort_by == 'servings':
        query = query.order_by(Recipe.servings.asc() if order == 'asc' else Recipe.servings.desc())
    elif sort_by == 'created_at':
        query = query.order_by(Recipe.created_at.asc() if order == 'asc' else Recipe.created_at.desc())
    elif sort_by == 'updated_at':
        query = query.order_by(Recipe.updated_at.asc() if order == 'asc' else Recipe.updated_at.desc())
    
    recipes = query.all()
    
    return render_template('table_view.html', recipes=recipes, sort_by=sort_by, order=order)


@bp.route('/bulk-delete', methods=['POST'])
def bulk_delete():
    """Delete multiple recipes"""
    try:
        recipe_ids = request.json.get('recipe_ids', [])
        
        if not recipe_ids:
            return jsonify({'success': False, 'error': 'No recipes selected'}), 400
        
        # Get recipes
        recipes = Recipe.query.filter(Recipe.id.in_(recipe_ids)).all()
        
        # Delete images
        for recipe in recipes:
            if recipe.image_filename:
                from app.utils.image_handler import delete_recipe_images
                delete_recipe_images(recipe.image_filename, current_app.config['UPLOAD_FOLDER'])
        
        # Delete from database
        Recipe.query.filter(Recipe.id.in_(recipe_ids)).delete(synchronize_session=False)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{len(recipes)} recipe(s) deleted successfully'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/bulk-tag', methods=['POST'])
def bulk_tag():
    """Add tag to multiple recipes"""
    try:
        recipe_ids = request.json.get('recipe_ids', [])
        tag = request.json.get('tag', '').strip()
        
        if not recipe_ids:
            return jsonify({'success': False, 'error': 'No recipes selected'}), 400
        
        if not tag:
            return jsonify({'success': False, 'error': 'Tag is required'}), 400
        
        # Get recipes
        recipes = Recipe.query.filter(Recipe.id.in_(recipe_ids)).all()
        
        # Add tag to each recipe
        for recipe in recipes:
            tags = recipe.tags_list
            if tag not in tags:
                tags.append(tag)
                recipe.tags_list = tags
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Tag "{tag}" added to {len(recipes)} recipe(s)'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/export-csv')
def export_csv():
    """Export recipes to CSV"""
    import csv
    from io import StringIO
    from flask import Response
    
    recipe_ids = request.args.getlist('ids')
    
    if recipe_ids:
        recipes = Recipe.query.filter(Recipe.id.in_(recipe_ids)).all()
    else:
        recipes = Recipe.query.all()
    
    # Create CSV
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Title', 'Description', 'Servings', 'Ingredients', 'Instructions', 'Notes', 'Tags', 'Created', 'Updated'])
    
    # Write data
    for recipe in recipes:
        writer.writerow([
            recipe.title,
            recipe.description,
            recipe.servings,
            len(recipe.ingredients_dict),
            len(recipe.instructions_list),
            '; '.join(recipe.notes_list),
            ', '.join(recipe.tags_list),
            recipe.created_at.strftime('%Y-%m-%d') if recipe.created_at else '',
            recipe.updated_at.strftime('%Y-%m-%d') if recipe.updated_at else ''
        ])
    
    # Create response
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': 'attachment; filename=recipes_export.csv'
        }
    )