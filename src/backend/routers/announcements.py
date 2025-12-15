"""
Announcements endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)

class AnnouncementCreate(BaseModel):
    title: str
    message: str
    start_date: Optional[str] = None
    expiration_date: str

class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
    start_date: Optional[str] = None
    expiration_date: Optional[str] = None

@router.get("", response_model=List[Dict[str, Any]])
def get_announcements() -> List[Dict[str, Any]]:
    """
    Get all active announcements (not expired)
    """
    now = datetime.now(timezone.utc).date()

    announcements = []
    for announcement in announcements_collection.find():
        # Check expiration date
        try:
            exp_date = datetime.strptime(announcement.get("expiration_date"), '%Y-%m-%d').date()
            if exp_date < now:
                continue  # Expired
        except (ValueError, TypeError):
            continue  # Invalid date, skip

        # Check start_date if it exists
        if announcement.get("start_date"):
            try:
                start_date = datetime.strptime(announcement["start_date"], '%Y-%m-%d').date()
                if start_date > now:
                    continue  # Not started yet
            except (ValueError, TypeError):
                continue  # Invalid date, skip

        announcements.append(announcement)

    # Sort by creation date (newest first)
    announcements.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return announcements

@router.get("/all", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: str) -> List[Dict[str, Any]]:
    """
    Get all announcements (for management) - requires authentication
    """
    # Check teacher authentication
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Authentication required")

    announcements = list(announcements_collection.find())
    # Sort by creation date (newest first)
    announcements.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return announcements

@router.post("", response_model=Dict[str, Any])
def create_announcement(announcement: AnnouncementCreate, teacher_username: str) -> Dict[str, Any]:
    """
    Create a new announcement - requires authentication
    """
    # Check teacher authentication
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Authentication required")

    # Validate dates
    now = datetime.now(timezone.utc)
    try:
        exp_date = datetime.strptime(announcement.expiration_date, '%Y-%m-%d')
        if announcement.start_date:
            start_date = datetime.strptime(announcement.start_date, '%Y-%m-%d')
            if start_date >= exp_date:
                raise HTTPException(
                    status_code=400, detail="Start date must be before expiration date")
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid date format. Use ISO format (YYYY-MM-DD)")

    # Create announcement document
    announcement_doc = {
        "title": announcement.title,
        "message": announcement.message,
        "start_date": announcement.start_date,
        "expiration_date": announcement.expiration_date,
        "created_by": teacher_username,
        "created_at": now.isoformat()
    }

    result = announcements_collection.insert_one(announcement_doc)
    announcement_doc["_id"] = str(result.inserted_id)

    return announcement_doc

@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(announcement_id: str, announcement: AnnouncementUpdate, teacher_username: str) -> Dict[str, Any]:
    """
    Update an announcement - requires authentication
    """
    # Check teacher authentication
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Authentication required")

    # Find the announcement
    announcement_doc = announcements_collection.find_one({"_id": announcement_id})
    if not announcement_doc:
        raise HTTPException(status_code=404, detail="Announcement not found")

    # Validate dates if provided
    if announcement.expiration_date or announcement.start_date:
        exp_date_str = announcement.expiration_date or announcement_doc.get("expiration_date")
        start_date_str = announcement.start_date or announcement_doc.get("start_date")

        if exp_date_str and start_date_str:
            try:
                exp_date = datetime.strptime(exp_date_str, '%Y-%m-%d')
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                if start_date >= exp_date:
                    raise HTTPException(
                        status_code=400, detail="Start date must be before expiration date")
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="Invalid date format. Use ISO format (YYYY-MM-DD)")

    # Prepare update document
    update_doc = {}
    if announcement.title is not None:
        update_doc["title"] = announcement.title
    if announcement.message is not None:
        update_doc["message"] = announcement.message
    if announcement.start_date is not None:
        update_doc["start_date"] = announcement.start_date
    if announcement.expiration_date is not None:
        update_doc["expiration_date"] = announcement.expiration_date

    if update_doc:
        result = announcements_collection.update_one(
            {"_id": announcement_id},
            {"$set": update_doc}
        )
        if result.modified_count == 0:
            raise HTTPException(
                status_code=500, detail="Failed to update announcement")

    # Return updated announcement
    updated_announcement = announcements_collection.find_one({"_id": announcement_id})
    return updated_announcement

@router.delete("/{announcement_id}")
def delete_announcement(announcement_id: str, teacher_username: str):
    """
    Delete an announcement - requires authentication
    """
    # Check teacher authentication
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Authentication required")

    # Find and delete the announcement
    result = announcements_collection.delete_one({"_id": announcement_id})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted successfully"}