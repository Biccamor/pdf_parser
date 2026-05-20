# Docling Layout Pre-processor Integration - Implementation Summary

## ✅ Complete - All Constraints Met

### New Flow
```
PDF (UploadFile)
  ↓
Docling Layout Detection (CPU-only)
  ├─ Extract bounding boxes per page
  ├─ Sort by (page, reading_order)
  └─ Generate page images (200 DPI, 8px padding)
  ↓
Per-Region Qwen Extraction
  ├─ Crop regions from images
  ├─ Send to Qwen with region-appropriate prompts:
  │  ├─ table → markdown table format
  │  ├─ section_header → strict header extraction
  │  └─ text → plain text preservation
  └─ Collect region texts
  ↓
Assemble Text with Region Labels
  → [LABEL]\ntext\n\n[LABEL]\ntext...
  ↓
Final Structured Parse
  → Send assembled text to Qwen → CVData JSON
```

---

## 📁 Files Modified/Created

### NEW: `docling_processor.py` (276 lines)
**Purpose:** Docling integration and region processing

**Key Functions:**
- `initialize_docling_converter()` - Initialize at startup (FastAPI lifespan)
- `get_docling_converter()` - Retrieve initialized converter
- `extract_layout_regions(pdf_path)` - PDF → layout regions with bboxes
- `convert_docling_to_fitz_coords()` - Y-axis conversion (bottom-left → top-left)
- `crop_region_from_image()` - Crop with 200 DPI, 8px padding, 1000px² threshold
- `get_region_type_label()` - Map Docling class → prompt type
- `extract_region_text_with_qwen()` - Region crop → Qwen → text (region-aware prompts)
- `process_pdf_with_docling()` - Orchestrator: regions → assembled text

**Constraints Met:**
✅ CPU-only (no GPU flags in DocumentConverter)
✅ do_ocr=False (Docling for layout only)
✅ generate_page_images=True
✅ PdfFormatOption usage
✅ 200 DPI rendering
✅ 8px padding
✅ 1000px² minimum area
✅ Y-axis coordinate conversion
✅ Reading order sorting
✅ Temp file cleanup

---

### UPDATED: `main.py` (48 lines → 62 lines)

**Changes:**
- Added FastAPI lifespan context manager:
  ```python
  @asynccontextmanager
  async def lifespan(app: FastAPI):
      initialize_docling_converter()  # startup
      yield
      # cleanup on shutdown
  ```

- Modified `/parser` endpoint:
  1. Validate PDF header (unchanged)
  2. Save to temp file (unchanged)
  3. Call `process_pdf_with_docling()` → assembled text
  4. Call `extract_text_from_assembled()` → CVData
  5. Clean up temp file (unchanged)

**Constraints Met:**
✅ UploadFile interface unchanged
✅ Temp file saved before Docling
✅ Temp file cleaned up after
✅ Lifespan context for startup init

---

### UPDATED: `vision_extractor.py` (+63 lines)

**Added Function:**
- `extract_text_from_assembled(raw_text, model)` - Final parsing
  - Takes assembled text (no images)
  - Uses `_ASSEMBLED_TEXT_PROMPT_TEMPLATE`
  - Returns CVData dict

**Constraints Met:**
✅ Pydantic schemas unchanged (still returns CVData)
✅ Ollama HTTP calls (requests library)
✅ No GPU configuration

---

### UPDATED: `prompt.py` (+94 lines)

**New Prompts:**
1. `_QWEN_TEXT_PROMPT` - Plain text extraction (all non-table/header regions)
2. `_QWEN_TABLE_PROMPT` - Markdown table format (table regions)
3. `_QWEN_SECTION_HEADER_PROMPT` - Strict header-only extraction (header regions)
4. `_ASSEMBLED_TEXT_PROMPT_TEMPLATE` - Final CV parsing from [LABEL]\ntext format

**Usage:**
- Region extraction: prompt selected by `get_region_type_label()`
- Final parse: assembled text + template → CVData

---

### UPDATED: `requirements.txt`

**Added:**
```
pillow>=10.0.0        # Image operations (PIL)
pymupdf>=1.23.0       # fitz cropping (already present, now versioned)
docling>=1.0.0        # Layout detection
docling-core>=1.0.0   # Docling core
```

---

## 🎯 Key Implementation Details

### Coordinate System Conversion
```python
Docling: (x0, y0_from_bottom, x1, y1_from_bottom)
Fitz:    (x0, y0_from_top, x1, y1_from_top)

Conversion:
  y0_fitz = page_height - y1_docling
  y1_fitz = page_height - y0_docling
```

### Region Processing Pipeline
```python
for page_num, regions in sorted(regions_by_page.items()):
    for region in sorted(regions, key=lambda r: r['reading_order']):
        image_path = crop_region_from_image(
            pdf_path, page_num, bbox,
            dpi=200, padding_px=8, min_area_px2=1000
        )
        text = await extract_region_text_with_qwen(
            image_path,
            region_type=get_region_type_label(region['label']),
            model="qwen2.5-vl-7b"
        )
        all_text_parts.append(f"[{label}]\n{text}")
```

### Assembled Text Format
```
[PAGECONTENT]
Section title extracted here

[TABLE]
| Col1 | Col2 |
|------|------|
| Data | Data |

[TEXT]
Body text extracted here

[SECTION_HEADER]
Next Section

...
```

---

## 🚀 Deployment Steps

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Verify Ollama Running
```bash
ollama serve  # ensure localhost:11434 is accessible
```

### 3. Run FastAPI
```bash
uvicorn main:app --reload
```

### 4. Test
```bash
curl -X POST http://localhost:8000/parser \
  -F "cv=@sample.pdf"
```

---

## ✅ All Constraints Verified

| Constraint | Status | Notes |
|-----------|--------|-------|
| UploadFile interface unchanged | ✅ | Same signature as before |
| Pydantic schemas unchanged | ✅ | CVData used throughout |
| Docling CPU-only | ✅ | No GPU flags in DocumentConverter |
| do_ocr=False | ✅ | Explicitly set in PdfFormatOption |
| generate_page_images=True | ✅ | Enabled for cropping |
| DocumentConverter + PdfFormatOption | ✅ | Used in initialize_docling_converter() |
| Startup lifespan init | ✅ | FastAPI lifespan context manager |
| Temp PDF saved before Docling | ✅ | tempfile.mkstemp() in main.py |
| Temp PDF cleaned up | ✅ | os.unlink() in finally block |
| 200 DPI rendering | ✅ | dpi=200 in crop_region_from_image() |
| 8px padding | ✅ | padding_px=8 parameter |
| 1000px² threshold | ✅ | min_area_px2=1000 |
| Y-axis coordinate conversion | ✅ | convert_docling_to_fitz_coords() |
| Region sorting by (page, reading_order) | ✅ | sorted() in process_pdf_with_docling() |
| Ollama HTTP calls (no AsyncClient) | ✅ | requests.post() in extract_region_text_with_qwen() |

---

## 📊 Git Commit

```
d1b862b feat: Add Docling layout detection pre-processor to CV pipeline
```

**Changes:**
- 5 files changed
- 512 insertions
- 25 deletions
- Created: docling_processor.py
- Modified: main.py, prompt.py, requirements.txt, vision_extractor.py

---

## 🔄 Backward Compatibility

✅ **Full backward compatibility maintained:**
- API endpoint signature unchanged
- Pydantic schemas unchanged
- Can still use old vision_extractor functions if needed
- Old prompts still available in prompt.py

---

## 📝 Notes for Testing

1. **Docling initialization is CPU-intensive** - First startup may take 30-60 seconds
2. **Region cropping is lossless** - 200 DPI + padding ensures quality
3. **Qwen region prompts are strict** - Each prompt optimized for its region type
4. **Assembled text is human-readable** - Can inspect intermediate output in logs
5. **Error handling is graceful** - Skips failed regions and continues processing

---

Done! ✨
