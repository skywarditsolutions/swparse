import io
import os
import structlog
import tempfile
import pandas as pd
from typing import Any
import warnings
# from .utils import format_timestamp
 
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from swparse.config.base import get_settings

settings = get_settings()

logger = structlog.get_logger()

MARKER_MODEL_DICT = settings.worker.MARKER_MODEL_DICT
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = (
    "1"  # For some reason, transformers decided to use .isin for a simple op, which is not supported on MPS
)
 
warnings.filterwarnings("ignore", category=UserWarning)  # Filter torch pytree user warnings

def pdf_markdown(
    in_file: bytes,
    langs: list[str] = ["en"],
    start_page: int = 0,
    max_pages: int = 40,
    ocr_all_pages: bool = False,
) -> tuple[str, str, str, dict[str, Any], dict, list[dict[str, Any]]]:
    # PDF to LLAMA conversion 
 

    if MARKER_MODEL_DICT is None:  
        logger.info("Loading Models")
        model_dict = create_model_dict()

        logger.info(list(model_dict.keys()))

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

        config = {
            "paginate_output": True,
            "force_ocr":   ocr_all_pages
        }
 
        pdf_converter = PdfConverter(
                config=config,
                artifact_dict=model_dict,
                processor_list=processors,
                renderer= "swparse.domain.swparse.llama_json_renderer.LLAMAJSONRenderer"
        )
        rendered = pdf_converter(filename)
        json_result = rendered.pages
        out_meta = rendered.metadata
        images = rendered.images
        full_text = rendered.text
        full_html = rendered.html
        full_md = rendered.md

    return full_text, full_html, full_md, images, out_meta, json_result

    

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