from __future__ import annotations

from typing import Any, Annotated, Tuple

import re
import regex
from collections import defaultdict

from bs4 import NavigableString
from markdownify import MarkdownConverter

 
import boto3
import structlog
import html_text
from botocore.config import Config
from bs4 import MarkupResemblesLocatorWarning

from marker.schema import BlockTypes
from marker.schema.document import Document

from swparse.domain.swparse.html_renderer import LLAMAHTMLRenderer
 
from swparse.domain.swparse.schemas import LLAMAJSONOutput
from swparse.config.app import settings
from swparse.domain.swparse.utils import extract_md_components, save_image_sync

# Ignore beautifulsoup warnings
import warnings

logger = structlog.getLogger()
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

BUCKET = settings.storage.BUCKET
MINIO_ROOT_USER = settings.storage.ROOT_USER
MINIO_ROOT_PASSWORD = settings.storage.ROOT_PASSWORD


def escape_dollars(text:str):
    return text.replace("$", r"\$")

def cleanup_text(full_text:str):
    full_text = re.sub(r'\n{3,}', '\n\n', full_text)
    full_text = re.sub(r'(\n\s){3,}', '\n\n', full_text)
    return full_text.strip()

def get_formatted_table_text(element):

    text = []
    for content in element.contents:
        if content is None:
            continue

        if isinstance(content, NavigableString):
            stripped = content.strip()
            if stripped:
                text.append(escape_dollars(stripped))
        elif content.name == 'br':
            text.append('<br>')
        elif content.name == "math":
            text.append("$" + content.text + "$")
        else:
            content_str = escape_dollars(str(content))
            text.append(content_str)

    full_text = ""
    for i, t in enumerate(text):
        if t == '<br>':
            full_text += t
        elif i > 0 and text[i - 1] != '<br>':
            full_text += " " + t
        else:
            full_text += t
    return full_text


class Markdownify(MarkdownConverter):
    paginated_md:dict[str, str]= {}
    
    def __init__(self, paginate_output, page_separator, inline_math_delimiters, block_math_delimiters, **kwargs):
        super().__init__(**kwargs)
        self.paginate_output = paginate_output
        self.page_separator = page_separator
        self.inline_math_delimiters = inline_math_delimiters
        self.block_math_delimiters = block_math_delimiters


    def convert_div(self, el, text, convert_as_inline):
        is_page = el.has_attr('class') and el['class'][0] == 'page'
        if self.paginate_output and is_page:
            page_id = el['data-page-id']
            # pagination_item = "\n\n" + "{" + str(page_id) + "}" + self.page_separator + "\n\n"
            pagination_item = "\n\n" +  self.page_separator + "\n\n"
            
            self.paginated_md[str(page_id)] = text
            return pagination_item + text
        else:
            return text

    def convert_p(self, el, text, convert_as_inline):
        hyphens = r'-—¬'
        has_continuation = el.has_attr('class') and 'has-continuation' in el['class']
        if has_continuation:
            block_type = BlockTypes[el['block-type']]
            if block_type in [BlockTypes.TextInlineMath, BlockTypes.Text]:
                if regex.compile(rf'.*[\p{{Ll}}|\d][{hyphens}]\s?$', regex.DOTALL).match(text):  # handle hypenation across pages
                    return regex.split(rf"[{hyphens}]\s?$", text)[0]
                return f"{text} "
            if block_type == BlockTypes.ListGroup:
                return f"{text}"
        return f"{text}\n\n" if text else ""  # default convert_p behavior

    def convert_math(self, el, text, convert_as_inline):
        inline = el.has_attr('display') and el['display'] == 'inline'
        if inline:
            return self.inline_math_delimiters[0] + text + self.inline_math_delimiters[1]
        else:
            return "\n" + self.block_math_delimiters[0] + text + self.block_math_delimiters[1] + "\n"

    def convert_table(self, el, text, convert_as_inline):
        total_rows = len(el.find_all('tr'))
        colspans = []
        rowspan_cols = defaultdict(int)
        for i, row in enumerate(el.find_all('tr')):
            row_cols = rowspan_cols[i]
            for cell in row.find_all(['td', 'th']):
                colspan = int(cell.get('colspan', 1))
                row_cols += colspan
                for r in range(int(cell.get('rowspan', 1)) - 1):
                    rowspan_cols[i + r] += colspan # Add the colspan to the next rows, so they get the correct number of columns
            colspans.append(row_cols)
        total_cols = max(colspans)

        grid = [[None for _ in range(total_cols)] for _ in range(total_rows)]

        for row_idx, tr in enumerate(el.find_all('tr')):
            col_idx = 0
            for cell in tr.find_all(['td', 'th']):
                # Skip filled positions
                while col_idx < total_cols and grid[row_idx][col_idx] is not None:
                    col_idx += 1

                # Fill in grid
                value = get_formatted_table_text(cell).replace("\n", " ").replace("|", " ").strip()
                rowspan = int(cell.get('rowspan', 1))
                colspan = int(cell.get('colspan', 1))

                if col_idx >= total_cols:
                    # Skip this cell if we're out of bounds
                    continue

                for r in range(rowspan):
                    for c in range(colspan):
                        try:
                            if r == 0 and c == 0:
                                grid[row_idx][col_idx] = value
                            else:
                                grid[row_idx + r][col_idx + c] = '' # Empty cell due to rowspan/colspan
                        except IndexError:
                            # Sometimes the colspan/rowspan predictions can overflow
                            print(f"Overflow in columns: {col_idx + c} >= {total_cols}")
                            continue

                col_idx += colspan

        markdown_lines = []
        col_widths = [0] * total_cols
        for row in grid:
            for col_idx, cell in enumerate(row):
                if cell is not None:
                    col_widths[col_idx] = max(col_widths[col_idx], len(str(cell)))

        add_header_line = lambda: markdown_lines.append('|' + '|'.join('-' * (width + 2) for width in col_widths) + '|')

        # Generate markdown rows
        added_header = False
        for i, row in enumerate(grid):
            is_empty_line = all(not cell for cell in row)
            if is_empty_line and not added_header:
                # Skip leading blank lines
                continue

            line = []
            for col_idx, cell in enumerate(row):
                if cell is None:
                    cell = ''
                padding = col_widths[col_idx] - len(str(cell))
                line.append(f" {cell}{' ' * padding} ")
            markdown_lines.append('|' + '|'.join(line) + '|')

            if not added_header:
                # Skip empty lines when adding the header row
                add_header_line()
                added_header = True

        # Handle one row tables
        if total_rows == 1:
            add_header_line()

        table_md = '\n'.join(markdown_lines)
        return "\n\n" + table_md + "\n\n"

    def convert_a(self, el, text, convert_as_inline):
        text = self.escape(text)
        text = re.sub(r"([\[\]])", r"\\\1", text)
        return super().convert_a(el, text, convert_as_inline)

    def convert_span(self, el, text, convert_as_inline):
        if el.get("id"):
            return f'<span id="{el["id"]}">{text}</span>'
        else:
            return text

    def escape(self, text:str):
        text = super().escape(text)
        if self.options['escape_dollars']:
            text = text.replace('$', r'\$')
        return text
    
    def get_paginated_md(self) -> dict[str, str]:
        return self.paginated_md
    


class LLAMAJSONRenderer(LLAMAHTMLRenderer):
    page_separator: Annotated[str, "The separator to use between pages.", "Default is '-' * 48."] = "-" * 48
    inline_math_delimiters: Annotated[Tuple[str], "The delimiters to use for inline math."] = ("$", "$")
    block_math_delimiters: Annotated[Tuple[str], "The delimiters to use for block math."] = ("$$", "$$")

    def __call__(self, document: Document) -> LLAMAJSONOutput:
        document_output = document.render()
        paginated_html = {}
        paginated_images= {}
        full_html, images , paginated_html, paginated_images = self.extract_html(document, document_output, paginated_html, paginated_images)

        md_cls = Markdownify(
            self.paginate_output,
            self.page_separator,
            heading_style="ATX",
            bullets="-",
            escape_misc=False,
            escape_underscores=False,
            escape_asterisks=False,
            escape_dollars=True,
            sub_symbol="<sub>",
            sup_symbol="<sup>",
            inline_math_delimiters=self.inline_math_delimiters,
            block_math_delimiters=self.block_math_delimiters
        )
        
        markdown = md_cls.convert(full_html)
        full_markdown = cleanup_text(markdown)
        paginated_md = md_cls.get_paginated_md()
        pageKeys = list(paginated_md.keys())

        llama_json_result:list[dict[str,Any]] = []
        full_text = ""
 
        all_images = {}
        s3_client = boto3.client(
            "s3",
            endpoint_url=settings.storage.ENDPOINT_URL,
            aws_access_key_id=MINIO_ROOT_USER,
            aws_secret_access_key=MINIO_ROOT_PASSWORD,
            config=Config(signature_version="s3v4"),
        )
        for pageIdx in pageKeys:
            saved_image_list:list[dict[str, str]] = []

            # saving images onto Minio bucket
            image_dict =  paginated_images.get(pageIdx, {})
            for image_name, image in image_dict.items():
       
                saved_img_file_path = save_image_sync(s3_client, image_name, image)      
       
                # collecting images per page
                saved_image_list.append({image_name:saved_img_file_path})
                # collecting all imges as dict
                all_images[image_name] = saved_img_file_path
                
                
            md = paginated_md[pageIdx]
            html_result = paginated_html.get(pageIdx)
            if html_result is None:
                text_results = ""
            else:
                text_results = html_text.extract_text(html_result, guess_layout=True)
            full_text += text_results
            items, links = extract_md_components(md)
            page = {
                "page":  int(pageIdx) + 1,
                "md": md,
                "text": full_text,
                "status": "OK",
                "links": links,
                "charts": [],
                "width": 0,
                "height": 0,
                "items": items,
                "images": saved_image_list,
                "triggeredAutoMode": False,
                "structuredData": None,
                "noStructuredContent": False,
                "noTextContent": False
            }
 
            llama_json_result.append(page)
        
        return LLAMAJSONOutput(
            markdown= full_markdown,
            html = full_html,
            text= full_text,
            pages = llama_json_result,
            images= all_images,
            metadata=self.generate_document_metadata(document, document_output)
        )
