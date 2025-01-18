import io
import os
 
import structlog

from tempfile import NamedTemporaryFile
from contextlib import asynccontextmanager
from marker.config.parser import ConfigParser
from marker.converters.pdf import PdfConverter
 
from swparse.config.base import get_settings

from marker.models import create_model_dict

from swparse.domain.swparse.utils import get_vram_usage
 
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .schemas import LLAMAJSONOutput
 
import warnings
warnings.filterwarnings("ignore", category=UserWarning)  # Filter torch pytree user warnings

settings = get_settings()
logger = structlog.get_logger()
MEMORY_USAGE_LOG = settings.app.MEMORY_USAGE_LOG
 
 
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = (
    "1"  # For some reason, transformers decided to use .isin for a simple op, which is not supported on MPS
)

 
models_dict:dict[str, Any] = {}    


@asynccontextmanager
async def create_temp_file_async(file: bytes, suffix: str):
    file_like = io.BytesIO(file)
    with NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
  
        temp_file.write(file_like.read())
        temp_file.seek(0)   
  
        yield temp_file.name

# PDF conversion 
async def pdf_markdown(
    in_file: bytes,
    langs: list[str] = ["en"], 
    start_page: int = 0,
    max_pages: int = 40,
    ocr_all_pages: bool = False,
) -> "LLAMAJSONOutput":
    global models_dict
    if not models_dict:
        models_dict = create_model_dict()

    
    if MEMORY_USAGE_LOG:
        allocated, cached  = get_vram_usage()

        logger.info(f"(Before model loading) VRAM ")
        logger.info(f"GPU Memory - Allocated: {allocated:.2f} MB, Cached: {cached:.2f} MB")  

    logger.info("Model loaded")
    logger.info(list(models_dict.keys()))
    
    if MEMORY_USAGE_LOG:
        logger.info(f"(After model loaded) VRAM ")
        allocated, cached = get_vram_usage()
        logger.info(f"GPU Memory - Allocated: {allocated:.2f} MB, Cached: {cached:.2f} MB")
    pass
    processors = [
        "marker.processors.blockquote.BlockquoteProcessor",
        # "marker.processors.code.CodeProcessor",
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
 
    async with create_temp_file_async(in_file, ".pdf") as filename:
 

        config = {
            "paginate_output": True,
            "strip_existing_ocr": ocr_all_pages,
        }
        logger.info("config")
        logger.info(config)
        config_parser = ConfigParser(config)
        pdf_converter = PdfConverter(
            config=config_parser.generate_config_dict(),
            artifact_dict=models_dict,
            processor_list=processors,
            renderer="swparse.domain.swparse.llama_json_renderer.LLAMAJSONRenderer"
        )

        return pdf_converter(filename)



