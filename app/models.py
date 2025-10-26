# app/models.py
from app import db
from flask_login import UserMixin
from datetime import datetime
import uuid
import json
from werkzeug.security import generate_password_hash, check_password_hash


# === USER MODEL ===
class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    profile_pic = db.Column(db.Text)  # e.g., path to uploaded image
    language = db.Column(db.String(5), default="en", nullable=False)

    recipes = db.relationship(
        "Recipe", back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"


# === RECIPE MODEL ===
class Recipe(db.Model):
    """Recipe model - converted from your original Recipe class"""

    __tablename__ = "recipes"

    # Primary key and identification
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Foreign key to User
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", name="fk_recipes_user_id_users"),
        nullable=True,
    )

    # Basic information
    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)

    # Servings and ingredients stored as JSON
    servings = db.Column(db.Integer, nullable=False, default=4)
    ingredients = db.Column(
        db.Text, nullable=False
    )  # JSON string: {"ingredient": "description"}

    # Instructions stored as JSON array
    instructions = db.Column(db.Text, nullable=False)  # JSON string: ["step1", "step2"]

    # Notes stored as JSON array
    notes = db.Column(db.Text, nullable=True)  # JSON string: ["note1", "note2"]

    # Tags stored as JSON array
    tags = db.Column(db.Text, nullable=True)  # JSON string: ["tag1", "tag2"]

    # Image
    image_filename = db.Column(db.Text, nullable=True)

    # Metadata
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Optional field for sharing in the future
    is_public = db.Column(db.Boolean, default=False)

    original_id = db.Column(
        db.String,
        db.ForeignKey("recipes.id", name="fk_recipes_original_id_recipes_id"),
        nullable=True,
    )

    # Relationship
    user = db.relationship("User", back_populates="recipes")
    original = db.relationship("Recipe", remote_side=[id], backref="copies")

    def __repr__(self):
        return f"<Recipe '{self.title}' (id={self.id[:8]}...)>"

    # Property methods to handle JSON serialization
    @property
    def ingredients_dict(self):
        """Get ingredients as a dictionary"""
        return json.loads(self.ingredients) if self.ingredients else {}

    @ingredients_dict.setter
    def ingredients_dict(self, value):
        """Set ingredients from a dictionary"""
        self.ingredients = json.dumps(value, ensure_ascii=False)

    @property
    def instructions_list(self):
        """Get instructions as a list"""
        return json.loads(self.instructions) if self.instructions else []

    @instructions_list.setter
    def instructions_list(self, value):
        """Set instructions from a list"""
        self.instructions = json.dumps(value, ensure_ascii=False)

    @property
    def notes_list(self):
        """Get notes as a list"""
        return json.loads(self.notes) if self.notes else []

    @notes_list.setter
    def notes_list(self, value):
        """Set notes from a list"""
        self.notes = json.dumps(value, ensure_ascii=False) if value else None

    @property
    def tags_list(self):
        """Get tags as a list"""
        return json.loads(self.tags) if self.tags else []

    @tags_list.setter
    def tags_list(self, value):
        """Set tags from a list"""
        self.tags = json.dumps(value, ensure_ascii=False) if value else None

    def to_dict(self):
        """Convert recipe to dictionary for JSON responses (includes all model fields)"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "servings": self.servings,
            "ingredients": self.ingredients_dict,
            "instructions": self.instructions_list,
            "notes": self.notes_list,
            "tags": self.tags_list,
            "image_filename": self.image_filename,
            "is_public": self.is_public,
            "original_id": self.original_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def recipe_already_copied(self, user_id):
        """Return True if the current recipe (or its original) has already been copied by this user"""
        return (
            Recipe.query.filter_by(
                user_id=user_id, original_id=self.original_id
            ).first()
            is not None
        )

    @staticmethod
    def from_dict(data, user_id=None):
        """Create a Recipe instance from a dictionary"""
        recipe = Recipe(
            user_id=user_id,
            title=data.get("title"),
            description=data.get("description"),
            servings=data.get("servings", 6),
            image_filename=data.get("image_filename", ""),
            is_public=data.get("is_public", False),
            original_id=data.get("original_id", None),
        )
        recipe.ingredients_dict = data.get("ingredients", {})
        recipe.instructions_list = data.get("instructions", [])
        recipe.notes_list = data.get("notes", [])
        recipe.tags_list = data.get("tags", [])
        return recipe

    @staticmethod
    def search_by_tag(tag, user_id=None):
        """Search recipes by exact tag match"""
        if user_id is not None:
            recipes = Recipe.query.filter_by(user_id=user_id).all()
        else:
            recipes = Recipe.query.all()
        matching = [r for r in recipes if tag in r.tags_list]
        return matching

    @staticmethod
    def search_all_attributes(search_string, user_id=None):
        """Search for a substring across all recipe attributes (case-insensitive)"""
        search_lower = search_string.lower()
        if user_id is not None:
            recipes = Recipe.query.filter_by(user_id=user_id).all()
        else:
            recipes = Recipe.query.all()
        matching = []

        for recipe in recipes:
            # Search in title
            if search_lower in recipe.title.lower():
                matching.append(recipe)
                continue

            # Search in description
            if search_lower in recipe.description.lower():
                matching.append(recipe)
                continue

            # Search in tags
            if any(search_lower in tag.lower() for tag in recipe.tags_list):
                matching.append(recipe)
                continue

            # Search in notes
            if any(search_lower in note.lower() for note in recipe.notes_list):
                matching.append(recipe)
                continue

            # Search in ingredients
            ingredients = recipe.ingredients_dict
            if any(
                search_lower in key.lower() or search_lower in value.lower()
                for key, value in ingredients.items()
            ):
                matching.append(recipe)
                continue

            # Search in instructions
            if any(
                search_lower in instruction.lower()
                for instruction in recipe.instructions_list
            ):
                matching.append(recipe)
                continue

        return matching
