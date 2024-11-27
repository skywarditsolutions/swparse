import io
import os
import tempfile
import time
import typing
import warnings

import structlog
import pandas
import pypdfium2 as pdfium  # Needs to be at the top to avoid warnings
from marker.cleaners.bullets import replace_bullets
from marker.cleaners.code import identify_code_blocks, indent_blocks
from marker.cleaners.fontstyle import find_bold_italic
from marker.cleaners.headers import filter_common_titles, filter_header_footer
from marker.cleaners.headings import infer_heading_levels, split_heading_blocks
from marker.cleaners.text import cleanup_text
from marker.cleaners.toc import compute_toc
from marker.debug.data import draw_page_debug_images, dump_bbox_debug_data
from marker.equations.equations import replace_equations
from marker.images.extract import extract_images
from marker.images.save import images_to_dict
from marker.layout.layout import annotate_block_types, surya_layout
from marker.layout.order import sort_blocks_in_reading_order, surya_order
from marker.models import load_all_models
from marker.ocr.detection import surya_detection
from marker.ocr.lang import replace_langs_with_codes, validate_langs
from marker.ocr.recognition import run_ocr
from marker.pdf.extract_text import get_text_blocks
from marker.pdf.utils import find_filetype
from marker.postprocessors.markdown import get_full_text, merge_lines, merge_spans
from marker.schema.page import Page
from marker.settings import settings
from marker.tables.table import format_tables
from marker.utils import flush_cuda_memory
from PIL import Image
from .utils import format_timestamp

logger = structlog.get_logger()
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = (
    "1"  # For some reason, transformers decided to use .isin for a simple op, which is not supported on MPS
)
model_lst: list[typing.Any] = []


warnings.filterwarnings("ignore", category=UserWarning)  # Filter torch pytree user warnings


def pdf_markdown(
    in_file: bytes,
    langs: list[str] = ["en"],
    start_page: int = 0,
    max_pages: int = 40,
    ocr_all_pages: bool = False,
) -> tuple[str, dict[str, Image.Image], dict, list]:
    if len(model_lst) == 0:
        logger.error("Loading Models")
        model_lst.extend(load_all_models())
        logger.error(len(model_lst))
    with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_pdf:
        temp_pdf.write(in_file)
        temp_pdf.seek(0)
        filename = temp_pdf.name
        full_text, images, out_meta, json_result = convert_single_pdf(
            filename,
            model_lst=model_lst,
            langs=langs,
            start_page=start_page,
            max_pages=max_pages,
            ocr_all_pages=ocr_all_pages,
        )

    return full_text, images, out_meta, json_result


def convert_single_pdf(
    fname: str,
    model_lst: list,
    max_pages: int | None = None,
    start_page: int | None = None,
    metadata: dict | None = None,
    langs: list[str] | None = None,
    batch_multiplier: int = 1,
    ocr_all_pages: bool = False,
) -> tuple[str, dict[str, Image.Image], dict, list]:
    ocr_all_pages = ocr_all_pages or settings.OCR_ALL_PAGES

    if metadata:
        langs = metadata.get("languages", langs)

    langs = replace_langs_with_codes(langs)
    validate_langs(langs)

    # Find the filetype
    filetype = find_filetype(fname)

    # Setup output metadata
    out_meta = {
        "languages": langs,
        "filetype": filetype,
        "pages_metadata": [],
    }

    if filetype == "other":  # We can't process this file
        return "", {}, out_meta

    # Get initial text blocks from the pdf
    doc = pdfium.PdfDocument(fname)
    pages, toc = get_text_blocks(
        doc,
        fname,
        max_pages=max_pages,
        start_page=start_page,
    )
    out_meta.update(
        {
            "pdf_toc": toc,
            "pages": len(pages),
        },
    )

    # Trim pages from doc to align with start page
    if start_page:
        for page_idx in range(start_page):
            doc.del_page(0)

    # Unpack models from list
    model_loading_start = time.time()
    texify_model, layout_model, order_model, detection_model, ocr_model, table_rec_model = model_lst
    model_loading_end = time.time()
    # Identify text lines on pages
    surya_detection_start = time.time()
    surya_detection(doc, pages, detection_model, batch_multiplier=batch_multiplier)
    flush_cuda_memory()
    surya_detection_end = time.time()

    OCR_start = time.time()
    # OCR pages as needed
    pages, ocr_stats = run_ocr(
        doc,
        pages,
        langs,
        ocr_model,
        batch_multiplier=batch_multiplier,
        ocr_all_pages=ocr_all_pages,
    )
    flush_cuda_memory()
    OCR_end = time.time()

    out_meta["ocr_stats"] = ocr_stats
    if len([b for p in pages for b in p.blocks]) == 0:
        print(f"Could not extract any text blocks for {fname}")
        return "", {}, out_meta

    surya_laytout_start = time.time()
    surya_layout(doc, pages, layout_model, batch_multiplier=batch_multiplier)
    flush_cuda_memory()
    surya_laytout_end = time.time()

    # Find headers and footers
    header_footer_start = time.time()
    bad_span_ids = filter_header_footer(pages)
    out_meta["block_stats"] = {"header_footer": len(bad_span_ids)}
    header_footer_end = time.time()

    # Add block types in
    annotate_block_types(pages)

    # Find reading order for blocks
    # Sort blocks by reading order
    surya_reading_order_start = time.time()
    surya_order(doc, pages, order_model, batch_multiplier=batch_multiplier)
    sort_blocks_in_reading_order(pages)
    flush_cuda_memory()
    surya_reading_order_end = time.time()

    # Dump debug data if flags are set
    dump_debug_start = time.time()
    draw_page_debug_images(fname, pages)
    dump_bbox_debug_data(fname, pages)
    dump_debug_end = time.time()

    # Fix code blocks
    identify_code_start = time.time()
    code_block_count = identify_code_blocks(pages)
    out_meta["block_stats"]["code"] = code_block_count
    indent_blocks(pages)
    identify_code_end = time.time()

    # Fix table blocks
    table_block_start = time.time()
    table_count = format_tables(pages, doc, fname, detection_model, table_rec_model, ocr_model)
    table_block_end = time.time()
    out_meta["block_stats"]["table"] = table_count

    for page in pages:
        for block in page.blocks:
            block.filter_spans(bad_span_ids)
            block.filter_bad_span_types()

    equation_start = time.time()
    filtered, eq_stats = replace_equations(
        doc,
        pages,
        texify_model,
        batch_multiplier=batch_multiplier,
    )
    flush_cuda_memory()
    equation_end = time.time()
    out_meta["block_stats"]["equations"] = eq_stats

    # Extract images and figures
    extract_images_start = time.time()
    if settings.EXTRACT_IMAGES:
        extract_images(doc, pages)

    extract_images_end = time.time()
    # Split out headers
    split_heading_blocks(pages)
    infer_heading_levels(pages)
    find_bold_italic(pages)

    # Use headers to compute a table of contents
    out_meta["computed_toc"] = compute_toc(pages)

    # Copy to avoid changing original data
    merging_sections_start = time.time()
    merged_lines = merge_spans(filtered)
    text_blocks = merge_lines(merged_lines)
    text_blocks = filter_common_titles(text_blocks)
    full_text = get_full_text(text_blocks)
    merging_sections_end = time.time()

    # Handle empty blocks being joined
    full_text = cleanup_text(full_text)

    # Replace bullet characters with a -
    full_text = replace_bullets(full_text)

    doc_images = images_to_dict(pages)

    json_result = []
    per_page_start = time.time()
    for page_idx, page in enumerate(filtered):

        page_text = get_page_text(page)
        page_merged_lines = merge_spans([page])
        page_text_blocks = merge_lines(page_merged_lines)
        page_text_blocks = filter_common_titles(page_text_blocks)
        page_md = get_full_text(page_text_blocks)

        page_md = cleanup_text(page_md)

        page_md = replace_bullets(page_md)

        doc_images = images_to_dict([page])

        page_metadata = {
                "page": page_idx + 1,
                "text": page_text,
                "md":page_md,
                "doc_images":doc_images,
                "status": "OK",
                "links": [],
                "width": page.width,
                "height": page.height,
                "triggeredAutoMode": False,
        }
        json_result.append(page_metadata)
    per_page_end = time.time()

    logger.info(f"Model loading start: {format_timestamp(model_loading_start)}")
    logger.info(f"Model loading end: {format_timestamp(model_loading_end)}")
    logger.info(f"Model loading time taken {format_timestamp(model_loading_end - model_loading_start)}\n\n")

    logger.info(f"surya_detection_start: {format_timestamp(surya_detection_start)}")
    logger.info(f"surya_detection_start: {format_timestamp(surya_detection_end)}")
    logger.info(f"surya_detection_start time taken {format_timestamp(surya_detection_end - surya_detection_start)}\n\n")

    logger.info(f"OCR start: {format_timestamp(OCR_start)}")
    logger.info(f"OCR end: {format_timestamp(OCR_end)}")
    logger.info(f"OCR taken {format_timestamp(OCR_end - OCR_start)}\n\n")

    logger.info(f"surya_laytout start: {format_timestamp(surya_laytout_start)}")
    logger.info(f"surya_laytout end: {format_timestamp(surya_laytout_end)}")
    logger.info(f"surya_laytout time taken {format_timestamp(surya_laytout_end - surya_laytout_start)}\n\n")

    logger.info(f"header_footer start: {format_timestamp(header_footer_start)}")
    logger.info(f"header_footer end: {format_timestamp(header_footer_end)}")
    logger.info(f"header_footer time taken {format_timestamp(header_footer_end - header_footer_start)}\n\n")

    logger.info(f"surya_reading_order start: {format_timestamp(surya_reading_order_start)}")
    logger.info(f"surya_reading_order end: {format_timestamp(surya_reading_order_end)}")
    logger.info(f"surya_reading_order time taken {format_timestamp(surya_reading_order_end - surya_reading_order_start)}\n\n")

    logger.info(f"dump_debug start: {format_timestamp(dump_debug_start)}")
    logger.info(f"dump_debug end: {format_timestamp(dump_debug_end)}")
    logger.info(f"dump_debug time taken {format_timestamp(dump_debug_end - dump_debug_start)}\n\n")

    logger.info(f"identify_code start: {format_timestamp(identify_code_start)}")
    logger.info(f"identify_code end: {format_timestamp(identify_code_end)}")
    logger.info(f"identify_code time taken {format_timestamp(identify_code_end - identify_code_start)}\n\n")

    logger.info(f"table_block start: {format_timestamp(table_block_start)}")
    logger.info(f"table_block end: {format_timestamp(table_block_end)}")
    logger.info(f"table_block time taken {format_timestamp(table_block_end - table_block_start)}\n\n")

    logger.info(f"equation start: {format_timestamp(equation_start)}")
    logger.info(f"equation end: {format_timestamp(equation_end)}")
    logger.info(f"equation time taken {format_timestamp(equation_end - equation_start)}\n\n")

    logger.info(f"extract_images start: {format_timestamp(extract_images_start)}")
    logger.info(f"extract_images end: {format_timestamp(extract_images_end)}")
    logger.info(f"extract_images time taken {format_timestamp(extract_images_end - extract_images_start)}\n\n")

    logger.info(f"merging_sections start: {format_timestamp(merging_sections_start)}")
    logger.info(f"merging_sections end: {format_timestamp(merging_sections_end)}")
    logger.info(f"merging_sections time taken {format_timestamp(merging_sections_end - merging_sections_start)}\n\n")

    logger.info(f"per_page start: {format_timestamp(per_page_start)}")
    logger.info(f"per_page end: {format_timestamp(per_page_end)}")
    logger.info(f"per_page time taken {format_timestamp(per_page_end - per_page_start)}\n\n")

    return full_text, doc_images, out_meta, json_result



def get_page_text(page: Page) -> str:
    page_text = []

    for block in page.blocks:

        for line in block.lines:

            for span in line.spans:
                if span.text.strip():
                    page_text.append(span.text.strip())  

    return "\n".join(page_text)


async def convert_xlsx_csv(
    input: bytes
) -> str:
    try:
        xlsx_data = io.BytesIO(input)
        df = pandas.read_excel(xlsx_data, header=None)
        return df.to_csv(index=False)
    except Exception as e:
        logger.error(f"info converting XLSX to CSV: {e}")
        return ""