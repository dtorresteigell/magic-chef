from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from datetime import datetime
import os


class RecipePDFGenerator:
    """Generate beautiful PDFs for recipes"""
    
    def __init__(self, output_path):
        self.output_path = output_path
        self.story = []
        self._setup_styles()
    
    def _setup_styles(self):
        """Setup PDF styles"""
        styles = getSampleStyleSheet()
        
        # Front page title
        self.front_title_style = ParagraphStyle(
            'FrontTitle',
            parent=styles['Heading1'],
            fontSize=36,
            textColor='#2C3E50',
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            leading=42
        )
        
        # Subtitle
        self.subtitle_style = ParagraphStyle(
            'Subtitle',
            parent=styles['Normal'],
            fontSize=14,
            textColor='#7F8C8D',
            alignment=TA_CENTER,
            fontName='Helvetica',
            spaceAfter=10
        )
        
        # Recipe title
        self.title_style = ParagraphStyle(
            'RecipeTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor='#2C3E50',
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        # Section headings
        self.heading_style = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor='#34495E',
            spaceAfter=8,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        )
        
        # Body text
        self.body_style = ParagraphStyle(
            'Body',
            parent=styles['BodyText'],
            fontSize=11,
            spaceAfter=6,
            leading=14
        )
    
    def add_front_page(self, title, recipe_count):
        """Add a front page to the PDF"""
        self.story.append(Spacer(1, 8*cm))
        self.story.append(Paragraph(title, self.front_title_style))
        self.story.append(Spacer(1, 1*cm))
        self.story.append(Paragraph(f"{recipe_count} Recipes", self.subtitle_style))
        
        # Add date
        date_str = datetime.now().strftime("%B %Y")
        self.story.append(Paragraph(date_str, self.subtitle_style))
        
        self.story.append(PageBreak())
    
    def add_recipe(self, recipe, image_path=None, is_last=False):
        """
        Add a recipe to the PDF
        
        Args:
            recipe: Recipe model instance
            image_path: Optional path to recipe image
            is_last: Whether this is the last recipe (no page break after)
        """
        # Recipe Title
        self.story.append(Paragraph(recipe.title, self.title_style))
        self.story.append(Spacer(1, 0.3*cm))
        
        # Recipe Image (if provided)
        if image_path and os.path.exists(image_path):
            try:
                img = Image(image_path, width=12*cm, height=8*cm, kind='proportional')
                self.story.append(img)
                self.story.append(Spacer(1, 0.5*cm))
            except Exception as e:
                print(f"Warning: Could not add image to PDF: {e}")
        
        # Description
        self.story.append(Paragraph("<b>Description</b>", self.heading_style))
        self.story.append(Paragraph(recipe.description, self.body_style))
        self.story.append(Spacer(1, 0.2*cm))
        
        # Ingredients
        servings = recipe.servings
        ingredients_dict = recipe.ingredients_dict
        self.story.append(Paragraph(f"<b>Ingredients ({servings} servings)</b>", self.heading_style))
        
        for ingredient, description in ingredients_dict.items():
            ingredient_text = f"• <b>{ingredient.title()}:</b> {description}"
            self.story.append(Paragraph(ingredient_text, self.body_style))
        self.story.append(Spacer(1, 0.2*cm))
        
        # Instructions
        self.story.append(Paragraph("<b>Instructions</b>", self.heading_style))
        for idx, instruction in enumerate(recipe.instructions_list, 1):
            instr_text = f"{idx}. {instruction}"
            self.story.append(Paragraph(instr_text, self.body_style))
        self.story.append(Spacer(1, 0.2*cm))
        
        # Notes
        if recipe.notes_list:
            self.story.append(Paragraph("<b>Notes</b>", self.heading_style))
            for note in recipe.notes_list:
                note_text = f"• {note}"
                self.story.append(Paragraph(note_text, self.body_style))
        
        # Add page break between recipes (except after last recipe)
        if not is_last:
            self.story.append(PageBreak())
    
    def build(self):
        """Build the PDF document"""
        doc = SimpleDocTemplate(
            self.output_path,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        doc.build(self.story)
        return self.output_path


def generate_recipe_pdf(recipe, output_path, upload_folder):
    """
    Generate a PDF for a single recipe
    
    Args:
        recipe: Recipe model instance
        output_path: Where to save the PDF
        upload_folder: Path to recipe images folder
        
    Returns:
        str: Path to generated PDF
    """
    generator = RecipePDFGenerator(output_path)
    
    # Add front page with recipe name
    generator.add_front_page(recipe.title, 1)
    
    # Get image path if exists
    image_path = None
    if recipe.image_filename:
        image_path = os.path.join(upload_folder, recipe.image_filename)
    
    # Add the recipe
    generator.add_recipe(recipe, image_path, is_last=True)
    
    # Build and return path
    return generator.build()


def generate_cookbook_pdf(recipes, title, output_path, upload_folder):
    """
    Generate a PDF cookbook with multiple recipes
    
    Args:
        recipes: List of Recipe model instances
        title: Cookbook title
        output_path: Where to save the PDF
        upload_folder: Path to recipe images folder
        
    Returns:
        str: Path to generated PDF
    """
    generator = RecipePDFGenerator(output_path)
    
    # Add front page
    generator.add_front_page(title, len(recipes))
    
    # Add each recipe
    for i, recipe in enumerate(recipes):
        is_last = (i == len(recipes) - 1)
        
        # Get image path if exists
        image_path = None
        if recipe.image_filename:
            image_path = os.path.join(upload_folder, recipe.image_filename)
        
        generator.add_recipe(recipe, image_path, is_last)
    
    # Build and return path
    return generator.build()