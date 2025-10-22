from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session, jsonify, make_response
from flask_login import current_user
from app import db
from app.models import Recipe
from app.utils.image_handler import process_recipe_image, delete_recipe_images, allowed_file
from app.utils.auth_helpers import login_required
from app.utils.translate_helpers import translate_recipe_sync
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
import os
import json

bp = Blueprint('main', __name__)


@bp.route('/')
@login_required
def index():
    """Home page with user-specific recipe list"""
    if "user_id" not in session:
        flash("Please log in to see your recipes.", "info")
        return redirect(url_for("auth.login"))

    recipes = (
        Recipe.query.filter_by(user_id=session["user_id"])
        .order_by(Recipe.created_at.desc())
        .all()
    )

    return render_template("index.html", recipes=recipes)

@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        current_user.first_name = request.form.get("first_name")
        current_user.last_name = request.form.get("last_name")
        current_user.email = request.form.get("email")

        # Handle optional profile picture
        picture = request.files.get("profile_picture")
        if picture and picture.filename:
            filename = secure_filename(picture.filename)
            path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
            picture.save(path)
            current_user.profile_pic = filename

        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for("main.settings"))

    return render_template("user_settings.html")

@bp.route("/settings/password", methods=["POST"])
@login_required
def change_password():
    old_password = request.form.get("old_password")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")

    # 1️⃣ Validate old password
    if not check_password_hash(current_user.password_hash, old_password):
        flash("Incorrect old password.", "error")
        return redirect(url_for("main.settings"))

    # 2️⃣ Validate new password confirmation
    if new_password != confirm_password:
        flash("New passwords do not match.", "error")
        return redirect(url_for("main.settings"))

    # 3️⃣ Optionally enforce minimum password strength
    if len(new_password) < 8:
        flash("Password must be at least 8 characters long.", "error")
        return redirect(url_for("main.settings"))

    # 4️⃣ Update securely
    current_user.password_hash = generate_password_hash(new_password)
    db.session.commit()

    flash("Password updated successfully!", "success")
    return redirect(url_for("main.settings"))


@bp.route('/recipes/<recipe_id>')
def recipe_detail(recipe_id):
    """Recipe detail page"""
    recipe = Recipe.query.get_or_404(recipe_id)

    # Check if current user already copied this recipe
    recipe_already_copied = Recipe.query.filter_by(
        user_id=session['user_id'],
        original_id=recipe.original_id
    ).first() is not None

    if "user_id" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("auth.login"))
    else:
        user_id = session["user_id"]
    
    # If recipe belongs to someone else and is not public
    if (recipe.user_id and recipe.user_id != session.get('user_id') and not recipe.is_public): # Later if recipe.user_id != user_id and not recipe.is_public:
        flash("You are not allowed to view this recipe.", "warning")
        return redirect(url_for("main.index"))

    return render_template('recipe_detail.html', recipe=recipe, recipe_already_copied=recipe_already_copied)


@bp.route('/recipes/new', methods=['GET', 'POST'])
@login_required
def recipe_new():
    """Create new recipe"""
    if request.method == 'POST':
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("auth.login"))
        else:
            user_id = session["user_id"]
            try:
                # Get form data
                title = request.form.get('title')
                description = request.form.get('description')
                servings = int(request.form.get('servings', 4))
                
                # Parse ingredients (format: "ingredient|description" one per line)
                ingredients_text = request.form.get('ingredients', '')
                ingredients_dict = {}
                for line in ingredients_text.strip().split('\n'):
                    if '|' in line:
                        key, value = line.split('|', 1)
                        ingredients_dict[key.strip()] = value.strip()
                
                # Parse instructions (one per line)
                instructions_text = request.form.get('instructions', '')
                instructions_list = [line.strip() for line in instructions_text.strip().split('\n') if line.strip()]
                
                # Parse notes (one per line)
                notes_text = request.form.get('notes', '')
                notes_list = [line.strip() for line in notes_text.strip().split('\n') if line.strip()]
                
                # Parse tags (comma-separated)
                tags_text = request.form.get('tags', '')
                tags_list = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
                
                # Create recipe
                recipe = Recipe(
                    user_id=user_id,
                    title=title,
                    description=description,
                    servings=servings
                )
                recipe.ingredients_dict = ingredients_dict
                recipe.instructions_list = instructions_list
                recipe.notes_list = notes_list
                recipe.tags_list = tags_list
                
                # Handle image upload with optimization
                if 'image' in request.files:
                    file = request.files['image']
                    if file and file.filename and allowed_file(file.filename):
                        filename, thumb_filename = process_recipe_image(
                            file, 
                            current_app.config['UPLOAD_FOLDER']
                        )
                        if filename:
                            recipe.image_filename = filename
                            flash('Image uploaded and optimized successfully!', 'success')
                        else:
                            flash('Error processing image. Recipe saved without image.', 'warning')
                
                db.session.add(recipe)
                db.session.flush()
                recipe.original_id = recipe.id
                db.session.commit()
                
                flash('Recipe created successfully!', 'success')
                return redirect(url_for('main.recipe_detail', recipe_id=recipe.id))
            
            except Exception as e:
                db.session.rollback()
                flash(f'Error creating recipe: {str(e)}', 'error')
                return redirect(url_for('main.recipe_new'))
    
    return render_template('recipe_form.html', recipe=None)


@bp.route('/recipes/<recipe_id>/edit', methods=['GET', 'POST'])
@login_required
def recipe_edit(recipe_id):
    """Edit existing recipe"""
    recipe = Recipe.query.get_or_404(recipe_id)

    if "user_id" not in session or recipe.user_id != session["user_id"]:
        flash("You don’t have permission to modify this recipe.", "error")
        return redirect(url_for("main.index"))
    
    if request.method == 'POST':
        try:
            # Update basic fields
            recipe.title = request.form.get('title')
            recipe.description = request.form.get('description')
            recipe.servings = int(request.form.get('servings', 4))
            
            # Parse ingredients
            ingredients_text = request.form.get('ingredients', '')
            ingredients_dict = {}
            for line in ingredients_text.strip().split('\n'):
                if '|' in line:
                    key, value = line.split('|', 1)
                    ingredients_dict[key.strip()] = value.strip()
            recipe.ingredients_dict = ingredients_dict
            
            # Parse instructions
            instructions_text = request.form.get('instructions', '')
            recipe.instructions_list = [line.strip() for line in instructions_text.strip().split('\n') if line.strip()]
            
            # Parse notes
            notes_text = request.form.get('notes', '')
            recipe.notes_list = [line.strip() for line in notes_text.strip().split('\n') if line.strip()]
            
            # Parse tags
            tags_text = request.form.get('tags', '')
            recipe.tags_list = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
            
            # Handle image upload with optimization
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename and allowed_file(file.filename):
                    # Delete old images
                    if recipe.image_filename:
                        delete_recipe_images(recipe.image_filename, current_app.config['UPLOAD_FOLDER'])
                    
                    # Process new image
                    filename, thumb_filename = process_recipe_image(
                        file,
                        current_app.config['UPLOAD_FOLDER']
                    )
                    if filename:
                        recipe.image_filename = filename
                        flash('Image updated and optimized successfully!', 'success')
                    else:
                        flash('Error processing image. Recipe updated without new image.', 'warning')
            
            db.session.commit()
            flash('Recipe updated successfully!', 'success')
            return redirect(url_for('main.recipe_detail', recipe_id=recipe.id))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating recipe: {str(e)}', 'error')
    
    return render_template('recipe_form.html', recipe=recipe)

@bp.route('/recipes/<recipe_id>/translate', methods=['GET', 'POST'])
@login_required
def recipe_translate(recipe_id):
    """Translate recipe and open edit form with translated content"""
    recipe = Recipe.query.get_or_404(recipe_id)
    
    # Check permissions
    if "user_id" not in session or recipe.user_id != session["user_id"]:
        flash("You don't have permission to translate this recipe.", "error")
        return redirect(url_for("main.index"))
    
    # Handle POST (same as recipe_edit to save changes)
    if request.method == 'POST':
        try:
            # Update basic fields
            recipe.title = request.form.get('title')
            recipe.description = request.form.get('description')
            recipe.servings = int(request.form.get('servings', 4))
           
            # Parse ingredients
            ingredients_text = request.form.get('ingredients', '')
            ingredients_dict = {}
            for line in ingredients_text.strip().split('\n'):
                if '|' in line:
                    key, value = line.split('|', 1)
                    ingredients_dict[key.strip()] = value.strip()
            recipe.ingredients_dict = ingredients_dict
           
            # Parse instructions
            instructions_text = request.form.get('instructions', '')
            recipe.instructions_list = [line.strip() for line in instructions_text.strip().split('\n') if line.strip()]
           
            # Parse notes
            notes_text = request.form.get('notes', '')
            recipe.notes_list = [line.strip() for line in notes_text.strip().split('\n') if line.strip()]
           
            # Parse tags
            tags_text = request.form.get('tags', '')
            recipe.tags_list = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
           
            # Handle image upload with optimization
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename and allowed_file(file.filename):
                    # Delete old images
                    if recipe.image_filename:
                        delete_recipe_images(recipe.image_filename, current_app.config['UPLOAD_FOLDER'])
                   
                    # Process new image
                    filename, thumb_filename = process_recipe_image(
                        file,
                        current_app.config['UPLOAD_FOLDER']
                    )
                    if filename:
                        recipe.image_filename = filename
                        flash('Image updated and optimized successfully!', 'success')
                    else:
                        flash('Error processing image. Recipe updated without new image.', 'warning')
           
            db.session.commit()
            
            # Clear the original recipe from session
            session.pop('original_recipe', None)
            
            flash('Recipe updated successfully!', 'success')
            return redirect(url_for('main.recipe_detail', recipe_id=recipe.id))
       
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating recipe: {str(e)}', 'error')
    
    # Handle GET (translate the recipe)
    # Get target language from query parameter
    target_lang = request.args.get('lang', 'es')
    
    # Validate language
    valid_langs = ['en', 'es', 'de', 'tr']
    if target_lang not in valid_langs:
        flash("Invalid language selected.", "error")
        return redirect(url_for('main.recipe_detail', recipe_id=recipe.id))
    
    try:
        # Store original recipe data in session BEFORE translation
        session['original_recipe'] = {
            'title': recipe.title,
            'description': recipe.description,
            'ingredients_dict': recipe.ingredients_dict,
            'instructions_list': recipe.instructions_list,
            'notes_list': recipe.notes_list,
        }
        
        # Prepare recipe data for translation
        recipe_data = {
            'title': recipe.title,
            'description': recipe.description,
            'notes_list': recipe.notes_list or [],
            'ingredients_dict': recipe.ingredients_dict or {},
            'instructions_list': recipe.instructions_list or [],
            'servings': recipe.servings,
            'tags_list': recipe.tags_list or [],
        }
        
        # Translate the recipe
        translated_data = translate_recipe_sync(recipe_data, target_lang)
        
        # Create a temporary recipe object with translated data
        # We don't save it yet - user will save via the form submission
        translated_recipe = type('obj', (object,), {
            'id': recipe.id,
            'title': translated_data['title'],
            'description': translated_data['description'],
            'servings': translated_data['servings'],
            'ingredients_dict': translated_data['ingredients_dict'],
            'instructions_list': translated_data['instructions_list'],
            'notes_list': translated_data['notes_list'],
            'tags_list': translated_data['tags_list'],
            'image_filename': recipe.image_filename,
            'user_id': recipe.user_id,
            'created_at': recipe.created_at,
            'updated_at': recipe.updated_at,
            'is_public': recipe.is_public,
        })()
        
        flash(f'Recipe translated successfully! Review and save changes.', 'success')
        return render_template('recipe_form.html', 
                             recipe=translated_recipe, 
                             is_translation=True,
                             target_lang=target_lang)
        
    except Exception as e:
        flash(f'Error translating recipe: {str(e)}', 'error')
        return redirect(url_for('main.recipe_detail', recipe_id=recipe.id))


@bp.route('/recipes/<recipe_id>/delete', methods=['POST'])
@login_required
def recipe_delete(recipe_id):
    """Delete recipe"""
    recipe = Recipe.query.get_or_404(recipe_id)

    if "user_id" not in session or recipe.user_id != session["user_id"]:
        flash("You don’t have permission to modify this recipe.", "error")
        return redirect(url_for("main.index"))
    
    try:
        # Delete images
        if recipe.image_filename:
            delete_recipe_images(recipe.image_filename, current_app.config['UPLOAD_FOLDER'])
        
        db.session.delete(recipe)
        db.session.commit()
        flash('Recipe deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting recipe: {str(e)}', 'error')
    
    return redirect(url_for('main.index'))


@bp.route('/recipes/<recipe_id>/delete-image', methods=['POST'])
@login_required
def recipe_delete_image(recipe_id):
    """Delete recipe image only (AJAX endpoint)"""
    recipe = Recipe.query.get_or_404(recipe_id)

    user_id = session.get("user_id")
    if not user_id or recipe.user_id != user_id:
        return {'success': False, 'message': 'Unauthorized'}, 403
    
    try:
        if recipe.image_filename:
            delete_recipe_images(recipe.image_filename, current_app.config['UPLOAD_FOLDER'])
            recipe.image_filename = None
            db.session.commit()
            return {'success': True, 'message': 'Image deleted successfully'}
        else:
            return {'success': False, 'message': 'No image to delete'}, 400
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'message': str(e)}, 500

@bp.route('/image-stats')
def image_stats():
    """Show image optimization statistics"""
    import os
    from app.models import Recipe
    
    upload_folder = current_app.config['UPLOAD_FOLDER']
    recipes = Recipe.query.all()
    
    stats = {
        'total_recipes': len(recipes),
        'recipes_with_images': sum(1 for r in recipes if r.image_filename),
        'total_images': 0,
        'total_thumbnails': 0,
        'total_size_mb': 0,
        'thumb_size_mb': 0
    }
    
    # Count files and sizes
    if os.path.exists(upload_folder):
        for filename in os.listdir(upload_folder):
            if os.path.isfile(os.path.join(upload_folder, filename)):
                stats['total_images'] += 1
                size = os.path.getsize(os.path.join(upload_folder, filename))
                stats['total_size_mb'] += size / (1024 * 1024)
    
    thumb_folder = os.path.join(upload_folder, 'thumbnails')
    if os.path.exists(thumb_folder):
        for filename in os.listdir(thumb_folder):
            if os.path.isfile(os.path.join(thumb_folder, filename)):
                stats['total_thumbnails'] += 1
                size = os.path.getsize(os.path.join(thumb_folder, filename))
                stats['thumb_size_mb'] += size / (1024 * 1024)
    
    return render_template('image_stats.html', stats=stats)

@bp.route('/recipes/<recipe_id>/save', methods=['POST'])
@login_required
def recipe_save(recipe_id):
    original = Recipe.query.get_or_404(recipe_id)
    user_id = session['user_id']

    # Don’t let users copy their own recipe
    if original.user_id == user_id:
        return render_template(
            "components/flash_messages.html",
            messages=[("warning", "You already own this recipe!")],
        ), 200, {"HX-Retarget": "#flash-messages", "HX-Swap": "outerHTML"}
    # Prevent copying the same original recipe twice
    elif original.recipe_already_copied(user_id):
        flash("You already copied this recipe!", "warning")
        return redirect(url_for("main.recipe_detail", recipe_id=original.id))
    else:
        # Copy recipe to current user
        new_recipe = Recipe(
            user_id=user_id,
            title=original.title,
            description=original.description,
            servings=original.servings,
            ingredients=original.ingredients,
            instructions=original.instructions,
            notes=original.notes,
            tags=original.tags,
            image_filename=original.image_filename,
            original_id=original.original_id
        )
        db.session.add(new_recipe)
        db.session.commit()
        
        # Render flash message with data-new-id
        flash_html = render_template(
            "components/flash_messages.html",
            messages=[("success", "Recipe saved to your profile!")],
            data_new_recipe_id=new_recipe.id
        )

        # Append a script that triggers your event
        flash_html += f'''
        <script>
            document.body.dispatchEvent(new CustomEvent("recipeSaved", {{
                bubbles: true,
                detail: {{ id: "{new_recipe.id}" }}
            }}));
        </script>
        '''

        headers = {
            "HX-Retarget": "#flash-messages",
            "HX-Swap": "outerHTML"
        }

        return flash_html, 200, headers



