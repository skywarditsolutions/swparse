import io
import os
import structlog
import tempfile
import pandas as pd
from typing import Any, TYPE_CHECKING
from marker.config.parser import ConfigParser

# from .utils import format_timestamp
from marker.converters.pdf import PdfConverter
from swparse.config.base import get_settings
from marker.models import create_model_dict
 
if TYPE_CHECKING:
    from .schemas import LLAMAJSONOutput

import warnings
warnings.filterwarnings("ignore", category=UserWarning)  # Filter torch pytree user warnings

settings = get_settings()

logger = structlog.get_logger()
 
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = (
    "1"  # For some reason, transformers decided to use .isin for a simple op, which is not supported on MPS
)
 
models_dict = {}
# PDF conversion 
def pdf_markdown(
    in_file: bytes,
    langs: list[str] = ["en"],
    start_page: int = 0,
    max_pages: int = 40,
    ocr_all_pages: bool = False,
) -> "LLAMAJSONOutput":
    global models_dict
    if not models_dict:
        models_dict = create_model_dict()
  
    logger.info("Model loaded: ")
    logger.info( list( models_dict.keys()))

 
    processors = [
        "marker.processors.blockquote.BlockquoteProcessor",
        "marker.processors.code.CodeProcessor",
        "marker.processors.debug.DebugProcessor",
        "marker.processors.document_toc.DocumentTOCProcessor",
        "marker.processors.equation.EquationProcessor",
        "marker.processors.footnote.FootnoteProcessor",
        "marker.processors.ignoretext.IgnoreTextProcessor",
        "marker.processors.line_numbers.LineNumbersProcessor",
        "marker.processors.list.ListProcessor",
        "marker.processors.page_header.PageHeaderProcessor",
        "marker.processors.sectionheader.SectionHeaderProcessor",
        "marker.processors.table.TableProcessor",
        "marker.processors.text.TextProcessor",
    ]


    with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_pdf:
        temp_pdf.write(in_file)
        temp_pdf.seek(0)
        filename = temp_pdf.name

<<<<<<< HEAD
        config = {
            "paginate_output": True,
            "force_ocr":   ocr_all_pages
=======
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
    texify_model, layout_model, order_model, detection_model, ocr_model, table_rec_model = model_lst

    # Identify text lines on pages
    surya_detection(doc, pages, detection_model, batch_multiplier=batch_multiplier)
    flush_cuda_memory()

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

    out_meta["ocr_stats"] = ocr_stats
    if len([b for p in pages for b in p.blocks]) == 0:
        print(f"Could not extract any text blocks for {fname}")
        return "", {}, out_meta

    surya_layout(doc, pages, layout_model, batch_multiplier=batch_multiplier)
    flush_cuda_memory()

    # Find headers and footers
    bad_span_ids = filter_header_footer(pages)
    out_meta["block_stats"] = {"header_footer": len(bad_span_ids)}

    # Add block types in
    annotate_block_types(pages)

    # Find reading order for blocks
    # Sort blocks by reading order
    surya_order(doc, pages, order_model, batch_multiplier=batch_multiplier)
    sort_blocks_in_reading_order(pages)
    flush_cuda_memory()

    # Dump debug data if flags are set
    draw_page_debug_images(fname, pages)
    dump_bbox_debug_data(fname, pages)

    # Fix code blocks
    code_block_count = identify_code_blocks(pages)
    out_meta["block_stats"]["code"] = code_block_count
    indent_blocks(pages)

    # Fix table blocks
    table_count = format_tables(pages, doc, fname, detection_model, table_rec_model, ocr_model)
    out_meta["block_stats"]["table"] = table_count

    for page in pages:
        for block in page.blocks:
            logger.info("block")
            logger.info(block)
            block.filter_spans(bad_span_ids)
            block.filter_bad_span_types()

    filtered, eq_stats = replace_equations(
        doc,
        pages,
        texify_model,
        batch_multiplier=batch_multiplier,
    )
    flush_cuda_memory()
    out_meta["block_stats"]["equations"] = eq_stats

    # Extract images and figures
    if settings.EXTRACT_IMAGES:
        extract_images(doc, pages)

    # Split out headers
    split_heading_blocks(pages)
    infer_heading_levels(pages)
    find_bold_italic(pages)

    # Use headers to compute a table of contents
    out_meta["computed_toc"] = compute_toc(pages)

    # Copy to avoid changing original data
    merged_lines = merge_spans(filtered)
    text_blocks = merge_lines(merged_lines)
    text_blocks = filter_common_titles(text_blocks)
    full_text = get_full_text(text_blocks)

    # Handle empty blocks being joined
    full_text = cleanup_text(full_text)

    # Replace bullet characters with a -
    full_text = replace_bullets(full_text)

    doc_images = images_to_dict(pages)

    json_result = []
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
                'charts':[],
                "width": page.width,
                "height": page.height,
                "triggeredAutoMode": False,
                'structuredData':None,
                'noStructuredContent':False,
                'noTextContent':False
>>>>>>> dev
        }
        config_parser = ConfigParser(config)
        pdf_converter = PdfConverter(
                config=config_parser.generate_config_dict(),
                artifact_dict=models_dict,
                processor_list=processors,
                renderer= "swparse.domain.swparse.llama_json_renderer.LLAMAJSONRenderer"
        )
 
        return pdf_converter(filename)

    

async def convert_xlsx_csv(
    input: bytes
) -> str:
    try:
        xlsx_data = io.BytesIO(input)
        df = pd.read_excel(xlsx_data, header=None)
        return df.to_csv(index=False)
    except Exception as e:
        logger.error(f"info converting XLSX to CSV: {e}")
        return ""