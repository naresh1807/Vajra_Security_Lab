from pydantic import BaseModel


class LabOut(BaseModel):
    id: str
    title: str
    concept_category: str
    mini_lesson_title: str
    mini_lesson: str
    try_it_steps: list[str]
    base_path: str
    title_te: str
    mini_lesson_title_te: str
    mini_lesson_te: str
    try_it_steps_te: list[str]
