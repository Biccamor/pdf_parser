from pydantic import BaseModel, Field
from typing import List, Optional


class EducationEntry(BaseModel):
    degree: Optional[str] = None
    field: Optional[str] = None
    institution: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    notes: Optional[str] = None


class ExperienceEntry(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    location: Optional[str] = None
    description: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)


class Skills(BaseModel):
    programming_languages: List[str] = Field(default_factory=list)
    frameworks_and_libraries: List[str] = Field(default_factory=list)
    tools_and_platforms: List[str] = Field(default_factory=list)
    other: List[str] = Field(default_factory=list)


class Language(BaseModel):
    name: str
    level: Optional[str] = None


class ExtraItem(BaseModel):
    title: str
    date: Optional[str] = None
    description: Optional[str] = None
    details: List[str] = Field(default_factory=list)


class ExtraCategory(BaseModel):
    category: str
    items: List[ExtraItem] = Field(default_factory=list)


class CVData(BaseModel):
    experience: List[ExperienceEntry] = Field(default_factory=list)
    education: List[EducationEntry] = Field(default_factory=list)
    skills: Skills = Field(default_factory=Skills)
    languages: List[Language] = Field(default_factory=list)
    extras: List[ExtraCategory] = Field(default_factory=list)