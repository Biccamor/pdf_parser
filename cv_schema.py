"""
Schemat Pydantic reprezentujący ustrukturyzowane dane CV.
Nie zawiera żadnych danych osobowych — tylko edukacja, doświadczenie, umiejętności i dodatki.
"""

from pydantic import BaseModel, Field
from typing import List


class CVData(BaseModel):
    education: List[str] = Field(
        default_factory=list,
        description=(
            "List of educational institutions, degrees, and years of study. "
            "Keep original language. ALWAYS include dates if present. "
            "Example: ['Warsaw University - Computer Science (2015-2020)']. "
            "DO NOT include any personal names."
        ),
    )
    experience: List[str] = Field(
        default_factory=list,
        description=(
            "Employment history. Keep original language. ALWAYS include dates, "
            "job title, and company name. "
            "Example: ['Senior Developer at Google (2020-2023)']. "
            "DO NOT include any personal names or contact details."
        ),
    )
    skills: List[str] = Field(
        default_factory=list,
        description=(
            "List of hard and soft skills. If they are in categories keep category names too "
            "and order them as they are in the CV. Keep concise. "
            "Example: ['Python', 'SQL', 'Time management']."
        ),
    )
    extra: List[str] = Field(
        default_factory=list,
        description=(
            "Additional information: foreign languages, driver's license, certificates, hobbies. "
            "If none found in CV, return an empty list []. "
            "DO NOT include any personal names or contact details."
        ),
    )
