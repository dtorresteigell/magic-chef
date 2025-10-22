from flask import Blueprint, render_template, request, session
from app.models import Recipe

bp = Blueprint('search', __name__, url_prefix='/search')


@bp.route('/')
def search():
    """Main search page"""
    return render_template('search.html')


@bp.route('/results')
def search_results():
    """
    HTMX endpoint for live search results
    Returns only the results HTML fragment
    """
    # # Temporary delay to see loading indicator
    # import time
    # time.sleep(0.5)  # Remove this line after testing!
    query = request.args.get('q', '').strip()
    tag = request.args.get('tag', '').strip()
    user_id = session.get('user_id', None)
    
    results = []
    search_type = None
    
    if query:
        results = Recipe.search_all_attributes(search_string=query, user_id=user_id)
        search_type = 'general'
    elif tag:
        results = Recipe.search_by_tag(tag=tag, user_id=user_id)
        search_type = 'tag'
    
    # Return only the results fragment for htmx
    return render_template('components/search_results_fragment.html',
                         results=results,
                         query=query,
                         tag=tag,
                         search_type=search_type)


@bp.route('/tags')
def all_tags():
    """Get all unique tags from all recipes"""
    all_recipes = Recipe.query.all()
    tags_set = set()
    
    for recipe in all_recipes:
        tags_set.update(recipe.tags_list)
    
    tags = sorted(list(tags_set))
    return render_template('components/tag_list.html', tags=tags)