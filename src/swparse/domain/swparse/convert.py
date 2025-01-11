import os
import structlog
import torch
import tempfile
from typing import Any, TYPE_CHECKING
from marker.config.parser import ConfigParser

from .utils import get_memory_usage, get_vram_usage
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
 
models_dict:dict[str, Any] = {}
# PDF conversion 
def pdf_markdown(
    in_file: bytes,
    langs: list[str] = ["en"],
    start_page: int = 0,
    max_pages: int = 40,
    ocr_all_pages: bool = False,
) -> "LLAMAJSONOutput":
    global models_dict
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
 
    allocated, cached  = get_vram_usage()
    
    logger.info(f"(Before model loading) VRAM ")
    logger.info(f"GPU Memory - Allocated: {allocated:.2f} MB, Cached: {cached:.2f} MB")
    
    if not models_dict:
        models_dict = create_model_dict(device=device, dtype=torch.float16)
  

    logger.info("Model loaded")
    logger.info(list(models_dict.keys()))
    
    logger.info(f"(After model loaded) VRAM ")
    allocated, cached = get_vram_usage()
    logger.info(f"GPU Memory - Allocated: {allocated:.2f} MB, Cached: {cached:.2f} MB")

    processors = [
        "marker.processors.blockquote.BlockquoteProcessor",
        "marker.processors.code.CodeProcessor",
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
        "marker.processors.debug.DebugProcessor",
    ]
 
    with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_pdf:
        temp_pdf.write(in_file)
        temp_pdf.seek(0)
        filename = temp_pdf.name

        config = {
            "paginate_output": True,
            "strip_existing_ocr": ocr_all_pages,
        }
        logger.info("conifg")
        logger.info(config)
        config_parser = ConfigParser(config)
        pdf_converter = PdfConverter(
                config=config_parser.generate_config_dict(),
                artifact_dict=models_dict,
                processor_list=processors,
                renderer= "swparse.domain.swparse.llama_json_renderer.LLAMAJSONRenderer"
        )
    
        return pdf_converter(filename)

 