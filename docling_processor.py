import logging
import os
import tempfile
from typing import Optional
 
import fitz
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
 
logger = logging.getLogger(__name__)
 
_converter: Optional[DocumentConverter] = None
 
 
def initialize_docling_converter() -> DocumentConverter:
    global _converter
    if _converter is not None:
        return _converter
 
    logger.info("Initializing Docling DocumentConverter (CPU mode)")
 
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    pipeline_options.generate_page_images = True
 
    _converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )
    logger.info("Docling converter initialized")
    return _converter
 
 
def get_docling_converter() -> DocumentConverter:
    global _converter
    if _converter is None:
        raise RuntimeError(
            "Docling converter not initialized. "
            "Call initialize_docling_converter() at startup."
        )
    return _converter
 
 
def extract_layout_regions(pdf_path: str) -> dict:
    """
    Extract layout regions from PDF using Docling.
 
    Returns:
        dict {page_num (0-indexed): [regions]}
        Each region: {label, bbox (x0,y0,x1,y1) in fitz top-left coords, reading_order}
    """
    converter = get_docling_converter()
 
    try:
        result = converter.convert(pdf_path)
        logger.info(f"Docling extracted layout from {pdf_path}")
    except Exception as e:
        logger.error(f"Docling conversion failed: {e}")
        return {}
 
    doc = result.document
 
    # Zbierz rozmiary stron (page_no jest 1-indexed w Docling)
    page_sizes = {}
    for page_no, page in doc.pages.items():
        page_sizes[page_no] = page.size.height  # wysokość w punktach PDF
 
    regions_by_page = {}
    reading_order = 0
 
    for item, level in doc.iterate_items():
        prov = getattr(item, 'prov', None)
        if not prov:
            reading_order += 1
            continue
 
        p = prov[0]
        bbox = getattr(p, 'bbox', None)
        page_no = getattr(p, 'page_no', None)
 
        if bbox is None or page_no is None:
            reading_order += 1
            continue
 
        page_h = page_sizes.get(page_no)
        if page_h is None:
            reading_order += 1
            continue
 
        # BoundingBox ma l, t, r, b w coord_origin=BOTTOMLEFT
        # t = top od dołu, b = bottom od dołu
        # konwersja na fitz (top-left origin):
        #   y0_fitz = page_h - t   (t jest wyżej od b)
        #   y1_fitz = page_h - b
        x0 = bbox.l
        x1 = bbox.r
        y0 = page_h - bbox.t
        y1 = page_h - bbox.b
 
        # upewnij się że x0<x1, y0<y1
        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
 
        label = type(item).__name__
 
        # page_no jest 1-indexed w Docling, fitz jest 0-indexed
        page_idx = page_no - 1
 
        if page_idx not in regions_by_page:
            regions_by_page[page_idx] = []
 
        regions_by_page[page_idx].append({
            'label': label,
            'bbox': (x0, y0, x1, y1),
            'reading_order': reading_order,
        })
 
        reading_order += 1
 
    for page_idx in regions_by_page:
        regions_by_page[page_idx].sort(key=lambda r: r['reading_order'])
        logger.info(f"Page {page_idx}: {len(regions_by_page[page_idx])} regions detected")
 
    return regions_by_page
 
 
def crop_region_from_image(
    pdf_path: str,
    page_num: int,
    bbox_fitz: tuple,
    dpi: int = 200,
    padding_px: int = 8,
    min_area_px2: int = 1000,
) -> Optional[str]:
    """
    Crop a region from a PDF page and save as temporary JPEG.
 
    Args:
        bbox_fitz: (x0, y0, x1, y1) w fitz coords (top-left origin, punkty PDF)
    """
    try:
        with fitz.open(pdf_path) as doc:
            page = doc[page_num]
            x0, y0, x1, y1 = bbox_fitz
            scale = dpi / 72.0
 
            width_px = int((x1 - x0) * scale)
            height_px = int((y1 - y0) * scale)
            if width_px * height_px < min_area_px2:
                logger.debug(f"Skip region: area {width_px*height_px}px² < {min_area_px2}px²")
                return None
 
            # padding w punktach PDF przed renderowaniem
            pad_pt = padding_px / scale
            pr = page.rect
            x0p = max(0, x0 - pad_pt)
            y0p = max(0, y0 - pad_pt)
            x1p = min(pr.width, x1 + pad_pt)
            y1p = min(pr.height, y1 + pad_pt)
 
            zoom = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(clip=fitz.Rect(x0p, y0p, x1p, y1p), matrix=zoom)
 
            fd, temp_path = tempfile.mkstemp(suffix=".jpg")
            os.close(fd)
            pix.save(temp_path)
            logger.debug(f"Cropped region to {temp_path} ({pix.width}x{pix.height}px)")
            return temp_path
 
    except Exception as e:
        logger.error(f"Failed to crop region from page {page_num}: {e}")
        return None
 
 
def get_region_prompt_type(label: str) -> str:
    label_lower = label.lower()
    if 'table' in label_lower:
        return 'table'
    if 'sectionheader' in label_lower or 'title' in label_lower:
        return 'section_header'
    return 'text'
 
 
async def extract_region_text_with_qwen(
    image_path: str,
    region_type: str,
    model: str = "qwen2.5-vl-7b",
    ollama_url: str = "http://localhost:11434",
) -> str:
    import base64
    import requests
    from prompt import (
        _QWEN_TABLE_PROMPT,
        _QWEN_SECTION_HEADER_PROMPT,
        _QWEN_TEXT_PROMPT,
    )
 
    prompt_map = {
        'table': _QWEN_TABLE_PROMPT,
        'section_header': _QWEN_SECTION_HEADER_PROMPT,
        'text': _QWEN_TEXT_PROMPT,
    }
    prompt = prompt_map.get(region_type, _QWEN_TEXT_PROMPT)
 
    try:
        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode("utf-8")
    except FileNotFoundError:
        logger.error(f"Region image not found: {image_path}")
        return ""
 
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [image_base64],
            }
        ],
        "stream": False,
        "options": {"temperature": 0, "num_ctx": 4096},
    }
 
    try:
        response = requests.post(
            f"{ollama_url}/api/chat",
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        text = response.json().get("message", {}).get("content", "").strip()
        logger.info(f"Qwen extracted {len(text)} chars from {region_type} region")
        return text
    except requests.exceptions.RequestException as e:
        logger.error(f"Ollama request failed: {e}")
        return ""
 
 
async def process_pdf_with_docling(
    pdf_path: str,
    model: str = "qwen2.5vl:7b",
    ollama_url: str = "http://localhost:11434",
) -> str:
    """
    Full pipeline: PDF -> Docling layout -> crop regions -> Qwen OCR -> assembled text.
 
    Returns:
        "[LABEL]\ntext\n\n[LABEL]\ntext..." or "" if no regions detected.
    """
    regions_by_page = extract_layout_regions(pdf_path)
 
    if not regions_by_page:
        logger.warning("No layout regions detected by Docling")
        return ""
 
    all_text_parts = []
 
    for page_num in sorted(regions_by_page.keys()):
        for region in regions_by_page[page_num]:
            label = region['label']
            bbox = region['bbox']
            region_type = get_region_prompt_type(label)
 
            image_path = crop_region_from_image(
                pdf_path, page_num, bbox,
                dpi=200, padding_px=8, min_area_px2=1000,
            )
            if image_path is None:
                continue
 
            try:
                text = await extract_region_text_with_qwen(
                    image_path, region_type,
                    model=model, ollama_url=ollama_url,
                )
                if text:
                    all_text_parts.append(f"[{label.upper()}]\n{text}")
                    logger.info(f"Page {page_num} [{label}]: {len(text)} chars")
            finally:
                try:
                    os.unlink(image_path)
                except Exception:
                    pass
 
    assembled = "\n\n".join(all_text_parts)
    logger.info(f"Assembled {len(assembled)} chars from {len(all_text_parts)} regions")
    return assembled