from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.core.db import get_db
from app.models.recipe import User

router = APIRouter(prefix="/api/v1/users", tags=["users"])

class UserProfileUpdate(BaseModel):
    birth_date: Optional[str] = None # ISO format (YYYY-MM-DD)
    weight_kg: Optional[float] = None
    allergies: Optional[str] = None

class UserProfileResponse(BaseModel):
    id: int
    username: str
    birth_date: Optional[datetime] = None
    weight_kg: Optional[float] = None
    allergies: Optional[str] = None

    class Config:
        from_attributes = True

@router.get("/{user_id}", response_model=UserProfileResponse)
def get_user_profile(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/{user_id}", response_model=UserProfileResponse)
def update_user_profile(user_id: int, profile: UserProfileUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if profile.birth_date:
        try:
            user.birth_date = datetime.strptime(profile.birth_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid birth_date format. Use YYYY-MM-DD")
            
    if profile.weight_kg is not None:
        user.weight_kg = profile.weight_kg
    if profile.allergies is not None:
        user.allergies = profile.allergies
        
    db.commit()
    db.refresh(user)
    return user
