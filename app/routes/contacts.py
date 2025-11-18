# app/routes/contacts.py
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    session,
)
from flask_login import current_user, login_required
from flask_babel import gettext as _
from app import db
from app.models import User, Contact, Recipe, RecipeShare, Notification
from sqlalchemy import or_, and_

bp = Blueprint("contacts", __name__, url_prefix="/contacts")


@bp.route("/")
@login_required
def index():
    """Contacts management page"""
    user_id = current_user.id

    # Get all contacts (accepted)
    contacts = Contact.get_user_contacts(user_id)

    # Get pending requests (received)
    pending_received = Contact.query.filter_by(
        receiver_id=user_id, status="pending"
    ).all()

    # Get pending requests (sent)
    pending_sent = Contact.query.filter_by(requester_id=user_id, status="pending").all()

    return render_template(
        "contacts.html",
        contacts=contacts,
        pending_received=pending_received,
        pending_sent=pending_sent,
    )


@bp.route("/search")
@login_required
def search():
    """Search for users to add as contacts"""
    query = request.args.get("q", "").strip()

    if len(query) < 2:
        return jsonify({"users": []})

    user_id = current_user.id

    # Search by username or email
    users = (
        User.query.filter(
            or_(User.username.ilike(f"%{query}%"), User.email.ilike(f"%{query}%")),
            User.id != user_id,  # Exclude current user
        )
        .limit(10)
        .all()
    )

    # Get existing contact relationships
    existing_contacts = Contact.query.filter(
        or_(
            and_(
                Contact.requester_id == user_id,
                Contact.receiver_id.in_([u.id for u in users]),
            ),
            and_(
                Contact.receiver_id == user_id,
                Contact.requester_id.in_([u.id for u in users]),
            ),
        )
    ).all()

    # Create lookup for contact status
    contact_status = {}
    for contact in existing_contacts:
        other_id = (
            contact.receiver_id
            if contact.requester_id == user_id
            else contact.requester_id
        )
        contact_status[other_id] = contact.status

    # Build results
    results = []
    for user in users:
        results.append(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "display_name": user.get_display_name(),
                "status": contact_status.get(user.id, None),
            }
        )

    return jsonify({"users": results})


@bp.route("/request/<user_id>", methods=["POST"])
@login_required
def send_request(user_id):
    """Send a contact request to another user"""
    requester_id = current_user.id

    # Check if user exists
    receiver = User.query.get(user_id)
    if not receiver:
        return jsonify({"success": False, "error": _("User not found")}), 404

    # Can't add yourself
    if requester_id == user_id:
        return jsonify({"success": False, "error": _("Cannot add yourself")}), 400

    # Check if contact already exists
    existing = Contact.query.filter(
        or_(
            and_(Contact.requester_id == requester_id, Contact.receiver_id == user_id),
            and_(Contact.requester_id == user_id, Contact.receiver_id == requester_id),
        )
    ).first()

    if existing:
        return (
            jsonify({"success": False, "error": _("Contact request already exists")}),
            400,
        )

    # Create new contact request
    contact = Contact(requester_id=requester_id, receiver_id=user_id, status="pending")
    db.session.add(contact)

    # Create notification
    notification = Notification(user_id=user_id, type="contact_request")
    notification.data_dict = {
        "requester_id": requester_id,
        "requester_username": current_user.username,
        "requester_display_name": current_user.get_display_name(),
    }
    db.session.add(notification)

    db.session.commit()

    return jsonify({"success": True, "message": _("Contact request sent!")})


@bp.route("/accept/<contact_id>", methods=["POST"])
@login_required
def accept_request(contact_id):
    """Accept a contact request"""
    contact = Contact.query.get_or_404(contact_id)

    # Verify this user is the receiver
    if contact.receiver_id != current_user.id:
        return jsonify({"success": False, "error": _("Unauthorized")}), 403

    # Accept the request
    contact.status = "accepted"

    # Create notification for requester
    notification = Notification(user_id=contact.requester_id, type="contact_accepted")
    notification.data_dict = {
        "accepter_id": current_user.id,
        "accepter_username": current_user.username,
        "accepter_display_name": current_user.get_display_name(),
    }
    db.session.add(notification)

    db.session.commit()

    flash(_("Contact request accepted!"), "success")
    return redirect(url_for("contacts.index"))


@bp.route("/reject/<contact_id>", methods=["POST"])
@login_required
def reject_request(contact_id):
    """Reject a contact request"""
    contact = Contact.query.get_or_404(contact_id)

    # Verify this user is the receiver
    if contact.receiver_id != current_user.id:
        return jsonify({"success": False, "error": _("Unauthorized")}), 403

    # Delete the request
    db.session.delete(contact)
    db.session.commit()

    flash(_("Contact request rejected"), "info")
    return redirect(url_for("contacts.index"))


@bp.route("/remove/<contact_id>", methods=["POST"])
@login_required
def remove_contact(contact_id):
    """Remove a contact"""
    contact = Contact.query.get_or_404(contact_id)

    # Verify this user is part of the contact
    if (
        contact.requester_id != current_user.id
        and contact.receiver_id != current_user.id
    ):
        return jsonify({"success": False, "error": _("Unauthorized")}), 403

    # Delete the contact
    db.session.delete(contact)
    db.session.commit()

    flash(_("Contact removed"), "info")
    return redirect(url_for("contacts.index"))


@bp.route("/cancel/<contact_id>", methods=["POST"])
@login_required
def cancel_request(contact_id):
    """Cancel a pending contact request you sent"""
    contact = Contact.query.get_or_404(contact_id)

    # Verify this user is the requester
    if contact.requester_id != current_user.id:
        return jsonify({"success": False, "error": _("Unauthorized")}), 403

    # Delete the request
    db.session.delete(contact)
    db.session.commit()

    flash(_("Contact request cancelled"), "info")
    return redirect(url_for("contacts.index"))


@bp.route("/share-modal/<recipe_id>")
@login_required
def share_modal(recipe_id):
    """Get the share modal content for a recipe"""
    recipe = Recipe.query.get_or_404(recipe_id)

    # Verify ownership
    if recipe.user_id != current_user.id:
        return jsonify({"success": False, "error": _("Unauthorized")}), 403

    # Get user's contacts
    contacts = Contact.get_user_contacts(current_user.id)

    # Get already shared users
    shared_with = RecipeShare.query.filter_by(recipe_id=recipe_id).all()
    shared_user_ids = {share.shared_with_user_id for share in shared_with}

    return render_template(
        "components/share_modal.html",
        recipe=recipe,
        contacts=contacts,
        shared_user_ids=shared_user_ids,
    )


@bp.route("/share/<recipe_id>", methods=["POST"])
@login_required
def share_recipe(recipe_id):
    """Share a recipe with specific users"""
    recipe = Recipe.query.get_or_404(recipe_id)

    # Verify ownership
    if recipe.user_id != current_user.id:
        return jsonify({"success": False, "error": _("Unauthorized")}), 403

    user_ids = request.json.get("user_ids", [])

    if not user_ids:
        return jsonify({"success": False, "error": _("No users selected")}), 400

    # Verify all users are contacts
    contacts = Contact.get_user_contacts(current_user.id)
    contact_ids = {contact.id for contact in contacts}

    shared_count = 0
    for user_id in user_ids:
        # Check if user is a contact
        if user_id not in contact_ids:
            continue

        # Check if already shared
        existing = RecipeShare.query.filter_by(
            recipe_id=recipe_id, shared_with_user_id=user_id
        ).first()

        if existing:
            continue

        # Create share
        share = RecipeShare(recipe_id=recipe_id, shared_with_user_id=user_id)
        db.session.add(share)

        # Create notification
        notification = Notification(user_id=user_id, type="recipe_shared")
        notification.data_dict = {
            "recipe_id": recipe_id,
            "recipe_title": recipe.title,
            "sharer_id": current_user.id,
            "sharer_username": current_user.username,
            "sharer_display_name": current_user.get_display_name(),
        }
        db.session.add(notification)

        shared_count += 1

    db.session.commit()

    return jsonify(
        {
            "success": True,
            "message": _("Recipe shared with %(count)d user(s)")
            % {"count": shared_count},
        }
    )


@bp.route("/unshare/<recipe_id>/<user_id>", methods=["POST"])
@login_required
def unshare_recipe(recipe_id, user_id):
    """Remove recipe share with specific user"""
    recipe = Recipe.query.get_or_404(recipe_id)

    # Verify ownership
    if recipe.user_id != current_user.id:
        return jsonify({"success": False, "error": _("Unauthorized")}), 403

    share = RecipeShare.query.filter_by(
        recipe_id=recipe_id, shared_with_user_id=user_id
    ).first()

    if share:
        db.session.delete(share)
        db.session.commit()
        return jsonify({"success": True, "message": _("Share removed")})

    return jsonify({"success": False, "error": _("Share not found")}), 404
