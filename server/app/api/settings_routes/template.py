"""Letter template endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.settings import LetterTemplateResponse, LetterTemplateTextUpdate
from app.services.cover_letter_service import extract_text
from app.services.settings_store import SettingsStore, get_settings_store

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get(
    "/letter-template",
    response_model=LetterTemplateResponse,
    summary="Get the personal letter template",
)
async def get_letter_template(
    store: SettingsStore = Depends(get_settings_store),
) -> LetterTemplateResponse:
    """Return the stored letter template text and original filename."""
    result = await store.get_letter_template()
    return LetterTemplateResponse(**result)


@router.put(
    "/letter-template",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Upload and save a letter template file",
)
async def save_letter_template(
    file: UploadFile,
    store: SettingsStore = Depends(get_settings_store),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Extract text from a TXT or DOCX upload and persist it as the letter template.
    
    Raises:
        HTTPException: 415 if the file extension is not .txt or .docx.
        HTTPException: 422 if the file cannot be parsed.
    """
    filename = file.filename or "template"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in {"txt", "docx"}:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only TXT and DOCX files are accepted for letter templates.",
        )

    raw_bytes = await file.read()
    try:
        text = extract_text(raw_bytes, filename)
    except Exception as exc:
        logger.error("Letter template text extraction failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract text from the uploaded file. Ensure it is a valid TXT or DOCX.",
        ) from exc
    # PostgreSQL JSONB rejects null bytes
    text = text.replace("\x00", "")
    await store.set_letter_template(text=text, filename=filename)
    await db.commit()
    logger.info("Letter template saved: %s", filename)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/letter-template",
    response_model=LetterTemplateResponse,
    summary="Update letter template text from the inline editor",
)
async def update_letter_template_text(
    payload: LetterTemplateTextUpdate,
    store: SettingsStore = Depends(get_settings_store),
    db: AsyncSession = Depends(get_db),
) -> LetterTemplateResponse:
    """Persist edited template text without re-uploading a file."""
    result = await store.update_letter_template_text(payload.text)
    await db.commit()
    return LetterTemplateResponse(**result)


@router.delete(
    "/letter-template",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete the letter template",
)
async def delete_letter_template(
    store: SettingsStore = Depends(get_settings_store),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove the letter template from the settings blob."""
    await store.delete_letter_template()
    await db.commit()
    logger.info("Letter template deleted.")
