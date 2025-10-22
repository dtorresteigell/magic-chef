from flask import Blueprint, render_template, send_file, request, flash, redirect, url_for, current_app, session
from app import db
from app.models import Recipe
from app.utils.auth_helpers import login_required
from app.utils.pdf_generator import generate_recipe_pdf, generate_cookbook_pdf
import os
from datetime import datetime

bp = Blueprint('pdf', __name__, url_prefix='/pdf')


@bp.route('/recipe/<recipe_id>')
def recipe_pdf(recipe_id):
    """Generate PDF for a single recipe"""
    recipe = Recipe.query.get_or_404(recipe_id)
    
    # Create filename
    safe_title = "".join(c for c in recipe.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
    filename = f"{safe_title}_{datetime.now().strftime('%Y%m%d')}.pdf"
    output_path = os.path.join(current_app.config['PDF_FOLDER'], filename)
    
    try:
        # Generate PDF
        pdf_path = generate_recipe_pdf(
            recipe, 
            output_path, 
            current_app.config['UPLOAD_FOLDER']
        )
        
        # Send file
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('main.recipe_detail', recipe_id=recipe_id))


@bp.route('/cookbook', methods=['GET', 'POST'])
def cookbook():
    """Generate PDF cookbook from selected recipes"""
    if request.method == 'POST':
        # Get selected recipe IDs
        recipe_ids = request.form.getlist('recipe_ids')
        cookbook_title = request.form.get('title', 'My Recipe Collection')
        
        if not recipe_ids:
            flash('Please select at least one recipe', 'error')
            return redirect(url_for('pdf.select_recipes'))
        
        # Get recipes
        recipes = Recipe.query.filter(Recipe.id.in_(recipe_ids)).all()
        
        if not recipes:
            flash('No recipes found', 'error')
            return redirect(url_for('pdf.select_recipes'))
        
        # Create filename
        safe_title = "".join(c for c in cookbook_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{safe_title}_{datetime.now().strftime('%Y%m%d')}.pdf"
        output_path = os.path.join(current_app.config['PDF_FOLDER'], filename)
        
        try:
            # Generate PDF
            pdf_path = generate_cookbook_pdf(
                recipes,
                cookbook_title,
                output_path,
                current_app.config['UPLOAD_FOLDER']
            )
            
            flash(f'Cookbook PDF generated successfully! ({len(recipes)} recipes)', 'success')
            
            # Send file
            return send_file(
                pdf_path,
                as_attachment=True,
                download_name=filename,
                mimetype='application/pdf'
            )
        except Exception as e:
            flash(f'Error generating PDF: {str(e)}', 'error')
            return redirect(url_for('pdf.select_recipes'))
    
    # GET request - show selection page
    return redirect(url_for('pdf.select_recipes'))


@bp.route('/select')
@login_required
def select_recipes():
    """Page to select recipes for cookbook generation"""
    if "user_id" not in session:
        flash("Please log in to see your recipes.", "info")
        return redirect(url_for("auth.login"))
    user_id = session.get('user_id', None)

    recipes = Recipe.query.filter_by(user_id=user_id).order_by(Recipe.created_at.desc()).all()
    return render_template('pdf_select.html', recipes=recipes)