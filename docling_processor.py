# -*- coding: utf-8 -*-
"""
Docling layout detection pre-processor for CV PDF parsing.

Functions:
    initialize_docling_converter() - Initialize Docling DocumentConverter (CPU-only)
    extract_layout_regions() - Extract layout bounding boxes from PDF
    crop_region_from_image() - Crop detected region from page image
    extract_region_text_with_qwen() - Send cropped region to Qwen for text extraction
    process_pdf_with_docling() - Full orchestrator: PDF -> regions -> text extraction
"""

import logging
import tempfile
from pathlib import Path
from typing import Optional, List

import fitz
from docling.document_converter import DocumentConverter, PdfFormatOption

logger = logging.getLogger(__name__)

_converter: Optional[DocumentConverter] = None


def initialize_docling_converter() -> DocumentConverter:
    """
    Initialize Docling DocumentConverter for CPU-only layout detection.
    Runs once at FastAPI startup.
    """
    global _converter
    if _converter is not None:
        return _converter

    logger.info("Initializing Docling DocumentConverter (CPU mode)")
    _converter = DocumentConverter(
        format_options={
            PdfFormatOption: PdfFormatOption(
                do_ocr=False,
                generate_page_images=True,
            )
        }
    )
    logger.info("Docling converter initialized")
    return _converter


def get_docling_converter() -> DocumentConverter:
    """Get initialized Docling converter. Raises if not initialized."""
    global _converter
    if _converter is None:
        raise RuntimeError("Docling converter not initialized. Call initialize_docling_converter() at startup.")
    return _converter


def extract_layout_regions(pdf_path: str) -> dict:
    """
    Extract layout regions from PDF using Docling.
    
    Args:
        pdf_path: path to PDF file
    
    Returns:
        dict with structure {page_num: [regions_with_bboxes]}
        Each region has: label, bbox (x0,y0,x1,y1), reading_order
    """
    converter = get_docling_converter()
    
    try:
        doc = converter.convert(pdf_path)
        logger.info(f"Docling extracted layout from {pdf_path}")
    except Exception as e:
        logger.error(f"Docling conversion failed: {e}")
        return {}
    
    regions_by_page = {}
    
    # Collect all items from texts, tables, pictures with their page references
    items_to_process = []
    
    # Texts (includes TextItem, SectionHeaderItem, etc.)
    for item in doc.document.texts:
        if hasattr(item, 'prov') and item.prov:
            page_no = item.prov[0].page_no if item.prov else None
            if page_no is not None and hasattr(item, 'bbox') and item.bbox:
                items_to_process.append((page_no, item))
    
    # Tables
    for item in doc.document.tables:
        if hasattr(item, 'prov') and item.prov:
            page_no = item.prov[0].page_no if item.prov else None
            if page_no is not None and hasattr(item, 'bbox') and item.bbox:
                items_to_process.append((page_no, item))
    
    # Pictures
    for item in doc.document.pictures:
        if hasattr(item, 'prov') and item.prov:
            page_no = item.prov[0].page_no if item.prov else None
            if page_no is not None and hasattr(item, 'bbox') and item.bbox:
                items_to_process.append((page_no, item))
    
    # Group by page and extract regions
    for page_no, item in items_to_process:
        bbox = item.bbox
        label = item.__class__.__name__
        reading_order = getattr(item, 'reading_order', 0)
        
        if page_no not in regions_by_page:
            regions_by_page[page_no] = []
        
        regions_by_page[page_no].append({
            'label': label,
            'bbox': (bbox.x0, bbox.y0, bbox.x1, bbox.y1),
            'reading_order': reading_order,
        })
    
    # Sort regions within each page by reading order
    for page_no in regions_by_page:
        regions_by_page[page_no] = sorted(
            regions_by_page[page_no], 
            key=lambda r: r['reading_order']
        )
        logger.info(f"Page {page_no}: {len(regions_by_page[page_no])} regions detected")
    
    return regions_by_page


def convert_docling_to_fitz_coords(
    page_height: float,
    docling_bbox: tuple,
) -> tuple:
    """
    Convert Docling bbox (bottom-left origin) to fitz coords (top-left origin).
    
    Docling: (x0, y0_from_bottom, x1, y1_from_bottom)
    Fitz:    (x0, y0_from_top, x1, y1_from_top)
    
    Args:
        page_height: height of the page in points
        docling_bbox: (x0, y0, x1, y1) in Docling coords
    
    Returns:
        (x0, y0, x1, y1) in fitz coords
    """
    x0, y0_docling, x1, y1_docling = docling_bbox
    
    y0_fitz = page_height - y1_docling
    y1_fitz = page_height - y0_docling
    
    return (x0, y0_fitz, x1, y1_fitz)


def crop_region_from_image(
    pdf_path: str,
    page_num: int,
    bbox_docling: tuple,
    dpi: int = 200,
    padding_px: int = 8,
    min_area_px2: int = 1000,
) -> Optional[str]:
    """
    Crop a region from a PDF page and save as temporary image.
    
    Args:
        pdf_path: path to PDF
        page_num: page index (0-based)
        bbox_docling: bbox in Docling coords (x0, y0, x1, y1) where y is from bottom
        dpi: render DPI
        padding_px: padding around crop (pixels)
        min_area_px2: skip regions smaller than this
    
    Returns:
        path to temporary JPEG file, or None if region too small
    """
    try:
        with fitz.open(pdf_path) as doc:
            page = doc[page_num]
            
            page_height = page.rect.height
            bbox_fitz = convert_docling_to_fitz_coords(page_height, bbox_docling)
            
            x0, y0, x1, y1 = bbox_fitz
            width_pt = x1 - x0
            height_pt = y1 - y0
            
            scale = dpi / 72.0
            width_px = int(width_pt * scale)
            height_px = int(height_pt * scale)
            area_px2 = width_px * height_px
            
            if area_px2 < min_area_px2:
                logger.debug(f"Skip region: area {area_px2}px^2 < {min_area_px2}px^2")
                return None
            
            zoom = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(clip=fitz.Rect(x0, y0, x1, y1), matrix=zoom)
            
            if padding_px > 0:
                new_width = pix.width + 2 * padding_px
                new_height = pix.height + 2 * padding_px
                new_pix = fitz.Pixmap(pix.colorspace, (0, 0, new_width, new_height), pix.alpha)
                new_pix.set_rect(pix)
                new_pix.set_origin(padding_px, padding_px)
                pix.set_rect(new_pix)
                pix = new_pix
            
            fd, temp_path = tempfile.mkstemp(suffix=".jpg")
            try:
                pix.save(temp_path)
                logger.debug(f"Cropped region to {temp_path} ({pix.width}x{pix.height}px)")
                return temp_path
            except Exception as e:
                import os
                os.close(fd)
                raise
                
    except Exception as e:
        logger.error(f"Failed to crop region from page {page_num}: {e}")
        return None


def get_region_type_label(docling_label: str) -> str:
    """Map Docling item class name to prompt type."""
    label_lower = docling_label.lower()
    
    if 'table' in label_lower:
        return 'table'
    elif 'header' in label_lower or 'title' in label_lower:
        return 'section_header'
    else:
        return 'text'


async def extract_region_text_with_qwen(
    image_path: str,
    region_type: str,
    model: str = "qwen2.5-vl-7b",
) -> str:
    """
    Send cropped region image to Qwen for text extraction.
    
    Args:
        image_path: path to cropped image
        region_type: 'table', 'section_header', or 'text'
        model: model name in Ollama
    
    Returns:
        extracted text
    """
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
            image_bytes = f.read()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
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
            "http://localhost:11434/api/chat",
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        text = result.get("message", {}).get("content", "").strip()
        logger.info(f"Qwen extracted {len(text)} chars from {region_type} region")
        return text
    except requests.exceptions.RequestException as e:
        logger.error(f"Ollama request failed for region: {e}")
        return ""


async def process_pdf_with_docling(
    pdf_path: str,
    model: str = "qwen2.5-vl-7b",
) -> str:
    """
    Full pipeline: PDF -> Docling layout -> crop regions -> Qwen text -> assembled text.
    
    Args:
        pdf_path: path to PDF
        model: Ollama model name
    
    Returns:
        assembled text with region labels: "[LABEL]\ntext\n\n[LABEL]\ntext..."
    """
    regions_by_page = extract_layout_regions(pdf_path)
    
    if not regions_by_page:
        logger.warning("No layout regions detected by Docling")
        return ""
    
    all_text_parts = []
    
    with fitz.open(pdf_path) as doc:
        for page_num, regions in sorted(regions_by_page.items()):
            page = doc[page_num]
            
            for region in regions:
                label = region['label']
                bbox = region['bbox']
                region_type = get_region_type_label(label)
                
                image_path = crop_region_from_image(
                    pdf_path,
                    page_num,
                    bbox,
                    dpi=200,
                    padding_px=8,
                    min_area_px2=1000,
                )
                
                if image_path is None:
                    continue
                
                try:
                    text = await extract_region_text_with_qwen(
                        image_path,
                        region_type,
                        model=model,
                    )
                    
                    if text:
                        all_text_parts.append(f"[{label.upper()}]\n{text}")
                        logger.info(f"Page {page_num} {label}: {len(text)} chars")
                    
                finally:
                    import os
                    try:
                        os.unlink(image_path)
                    except Exception:
                        pass
    
    assembled_text = "\n\n".join(all_text_parts)
    logger.info(f"Assembled {len(assembled_text)} chars from {len(all_text_parts)} regions")
    return assembled_text
