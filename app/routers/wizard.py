

import re
from fastapi import APIRouter, HTTPException


router = APIRouter(
    prefix="/wizard",
    tags=["wizard"],
    responses={404: {"description": "Not found"}},
)


wizards = [
    [
        {
            "id": 0,
            "question": "What is your name?",
            "validation": "^[a-zA-Z ]+$",
            "type": "text"
        },
        {
            "id": 1,
            "question": "What is your enrollment number?",
            "validation": "^[0-9]+$",
            "type": "text"
        },
        {
            "id": 2,
            "question": "What is the reason of your application for leave of absence?",
            "type": "checkbox",
            "options": [
                "illness",
                "foreign study",
                "maternity/parental leave",
                "internship",
                "care of a close relative",
                "Formation of a company",
                "Other"
            ],
            "validation": "^[0-6]$"
        }
    ]
]


@router.get("/{wizard_id}")
def start_wizard(wizard_id: int):
    return wizards[wizard_id]


@router.post("/{wizard_id}/{question_id}")
def validate_answer(wizard_id: int, question_id: int, answer: str):
    wizard = wizards[wizard_id]
    question = wizard[question_id]
    if not re.match(question["validation"], answer): 
        raise HTTPException(status_code=404, detail="Regex failed: " + question["validation"])
    