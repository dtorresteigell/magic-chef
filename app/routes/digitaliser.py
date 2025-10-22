from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session, current_app
from werkzeug.utils import secure_filename
import os
import tempfile
from app.utils.auth_helpers import login_required
from app.utils.ocr_handler import perform_ocr, parse_ocr_text_to_recipe
from app.utils.ai_recipe_generator import convert_ai_recipe_to_model_format

bp = Blueprint('digitaliser', __name__, url_prefix='/digitaliser')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf', 'tiff'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@bp.route('/')
@login_required
def index():
    """Recipe Digitaliser page"""
    if "user_id" not in session:
        flash("Please log in to see your recipes.", "info")
        return redirect(url_for("auth.login"))
    return render_template('digitaliser.html')


@bp.route('/upload-and-ocr', methods=['POST'])
def upload_and_ocr():
    """Upload image and perform OCR"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'Invalid file type. Allowed: PNG, JPG, GIF, WebP, PDF, TIFF'}), 400
        
        # Save to temporary location
        temp_dir = tempfile.gettempdir()
        filename = secure_filename(file.filename)
        temp_path = os.path.join(temp_dir, filename)
        file.save(temp_path)
        
        try:
            # Perform OCR
            ocr_text = perform_ocr(temp_path)
            
            # Parse to recipe
            ai_recipe = parse_ocr_text_to_recipe(ocr_text)
            
            # Convert to model format
            recipe_data = convert_ai_recipe_to_model_format(ai_recipe)
            
            return jsonify({
                'success': True,
                'recipe': recipe_data,
                'ocr_text': ocr_text
            })
        
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
    
    except Exception as e:
        current_app.logger.error(f"OCR/Parse error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/save-recipe', methods=['POST'])
def save_recipe():
    """Save digitised recipe"""
    try:
        from app import db
        from app.models import Recipe

        if "user_id" not in session:
            flash("Please log in to see your recipes.", "info")
            return redirect(url_for("auth.login"))
        user_id = session.get('user_id', None)
        
        recipe_data = request.json.get('recipe')
        
        if not recipe_data:
            return jsonify({'success': False, 'error': 'Recipe data required'}), 400
        
        # Create recipe
        recipe = Recipe.from_dict(recipe_data, user_id=user_id)
        db.session.add(recipe)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'recipe_id': recipe.id,
            'message': 'Recipe saved successfully!'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500