from fastapi import APIRouter, Depends, HTTPException, UploadFile
from ..models import FileAttachment

router = APIRouter(
    prefix="/file-upload",
    tags=["file-upload"],
    responses={404: {"description": "Not found"}},
)



@router.post("/")
async def upload_file(file: UploadFile):
    content = await file.read()
    f = FileAttachment()
    f.content = content
    f.name = file.filename
    f.save()
    return f.to_dict()
