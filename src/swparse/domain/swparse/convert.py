import io
import os
import re
import structlog

from tempfile import NamedTemporaryFile
from contextlib import asynccontextmanager
from marker.config.parser import ConfigParser
from marker.converters.pdf import PdfConverter
from lark import Lark, Token, Transformer
from swparse.config.base import get_settings

from marker.models import create_model_dict

from .utils import get_memory_usage, get_vram_usage
 
from typing import Any, TYPE_CHECKING, List

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

__all__ = ["pdf_markdown", "MdAnalyser"]
 
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
        models_dict = create_model_dict(device="cpu")

    
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




class MdAnalyser:
    def __init__(self, markdown_content: str):
        self.markdown_content = markdown_content
        self.components = []
        self.links = []
        self.lines = markdown_content.splitlines()

        # Compile patterns once for efficiency
        self.patterns = {
            "heading": re.compile(r"^(#{1,6})\s*(.+)$"),
            "table_row": re.compile(r"^\|.*\|$"),
            "paragraph": re.compile(r"^(?!\!\[.*\]\(.*\))(?!.*https?://)[^\|#\s].+$"),
            "table_separator": re.compile(r"^\|[-|]*\|$"),
            "links": re.compile(r"http?s?://[^\s]+")
        }

    def extract_components(self) -> tuple[List[dict[str,Any]], list[dict[str, str]]]:
        """Extracts components from the markdown content."""
        current_table = []

        for line in self.lines:
            if not line.strip():
                continue
            # Process different patterns
            self.extract_link(line)
            line = self.remove_links(line)
            if self.patterns["heading"].match(line):
                self._flush_table(current_table)
                self.add_heading(line)
            elif self.patterns["table_row"].match(line):
                if not self.patterns["table_separator"].match(line):
                    current_table.append(line)
            elif self.patterns["paragraph"].match(line):
                self._flush_table(current_table)
                self.add_paragraph(line)


        self._flush_table(current_table)

        return self.components, self.links


    def add_table(self, current_table: List[str]):
        """Processes and adds a table component."""
        rows = [
            [cell.strip() for cell in re.findall(r"\|([^|]+)", row)]
            for row in current_table
        ]
        self.components.append({
            "type": "table",
            "md": "\n".join(current_table),
            "rows": rows,
            "bBox": self._get_bbox(),
        })

    def _flush_table(self, current_table: List[str]):
        """Adds the current table to components if not empty."""
        if current_table:
            self.add_table(current_table)
            current_table.clear()


    def extract_link(self, line: str):
        """Extract links from the given line and adds them to self.links."""
        matches = self.patterns["links"].findall(line)
        for match in matches:
            self.links.append({
                "text": match,
                "url": match
            })

    def remove_links(self, line: str) -> str:
        """Remove links from a line while keeping the remaining text."""
        return self.patterns["links"].sub("", line).strip()

    def add_heading(self, line: str):
        """Processes and adds a heading component."""
        match = self.patterns["heading"].match(line)
        level = len(match.group(1))
        text = match.group(2).strip()
        self.components.append({
            "type": "heading",
            "level": level,
            "md": line,
            "value": text,
            "bBox": self._get_bbox()
        })

    def add_paragraph(self, line: str):
        """Processes and adds a text component."""
        self.components.append({
            "type": "text",
            "md": line,
            "value": self.md_to_text(line),
            "bBox": self._get_bbox()
        })

    @staticmethod
    def md_to_text(md: str) -> str:
        """Converts Markdown to plain text (basic implementation)."""
        return re.sub(r"(\*\*|__|`|~~)", "", md).strip()

    @staticmethod
    def _get_bbox() -> dict:
        """Returns a default bounding box structure."""
        return {"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0}



class TreeToJson(Transformer):
    def __init__(self, visit_tokens: bool = True):
        super().__init__(visit_tokens)
        self.tables = set()

    def start(self, items: list[Token]):
        return {"tables": items[0:-1], "output": items[-1].lower()}

    def instruction(self, items: list[Token]):
        headers = [label["name"] for label in items[1:-1]]
        if len(headers) != len(dict.fromkeys(headers)):
            raise ValueError("Duplicate labels")
        return {"mode": items[-1], "table_name": items[0], "labels": items[1:-1]}

    def mode(self, items: list[Token]):
        mode_map = {
            "by_sentence": "sent",
            "sent": "sent",
            "bysentence": "sent",
            "by_line": "ln",
            "ln": "ln",
            "byline": "ln",
        }
        if not len(items):
            return "sent"
        return mode_map[items[0].value.replace(" ", "_").lower()]

    def output(self, items: list[Token]):
        if not len(items):
            return "json"
        return items[0].value.lower()

    def table_ident(self, items: list[Token]):
        table_name = items[0].value.replace(" ", "_").lower()
        if table_name in self.tables:
            raise Exception(f"Duplicate table name: {table_name}")
        self.tables.add(table_name)
        return table_name

    def value(self, items: list[Token]):
        name = items[0].replace(" ", "_").lower()
        if len(items) == 1:
            return {"name": name, "type": "string"}
        return {"name": name, "type": items[1]}

    def field(self, items: list[Token]):
        return items[0].value

    def type(self, items: list[Token]):
        return items[0].value
