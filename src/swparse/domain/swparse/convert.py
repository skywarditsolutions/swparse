import io
import os
import structlog
import tempfile
import pandas as pd
from typing import Any, TYPE_CHECKING
import warnings
# from .utils import format_timestamp
import sys
from marker.converters.pdf import PdfConverter
from swparse.config.base import get_settings
from marker.models import create_model_dict
 
if TYPE_CHECKING:
    from .schema import LLAMAJSONOutput

settings = get_settings()

logger = structlog.get_logger()
 
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = (
    "1"  # For some reason, transformers decided to use .isin for a simple op, which is not supported on MPS
)
 
warnings.filterwarnings("ignore", category=UserWarning)  # Filter torch pytree user warnings
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
        size_in_bytes = sys.getsizeof(models_dict)
        logger.info(f"Memory size of the dictionary: {size_in_bytes} bytes")

 
    logger.info("exist")
    state_keys = list( models_dict.keys())
    logger.info(state_keys)

 
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