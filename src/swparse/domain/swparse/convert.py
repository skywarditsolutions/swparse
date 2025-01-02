import os
import structlog
import tempfile
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
    if not models_dict:
        models_dict = create_model_dict()
  
    logger.info("Model loaded: ")
    logger.info(list(models_dict.keys()))

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
            "force_ocr":   ocr_all_pages,
            "skip_layout_detection": True
        }
        config_parser = ConfigParser(config)
        pdf_converter = PdfConverter(
                config=config_parser.generate_config_dict(),
                artifact_dict=models_dict,
                processor_list=processors,
                renderer= "swparse.domain.swparse.llama_json_renderer.LLAMAJSONRenderer"
        )
 
        return pdf_converter(filename)

 