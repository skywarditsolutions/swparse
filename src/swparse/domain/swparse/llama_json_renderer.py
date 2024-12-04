from __future__ import annotations

from typing import Any

import re
import os
import regex
import html_text
from markdownify import MarkdownConverter
from pydantic import BaseModel
from bs4 import MarkupResemblesLocatorWarning

from html_renderer import LLAMAHTMLRenderer
from marker.schema import BlockTypes
from marker.schema.document import Document

# Ignore beautifulsoup warnings
import warnings
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)


class JSONItemOutput(BaseModel):
    block_type: str
    md: str
    value: str
    level: str

class LLAMAJSONPAGE(BaseModel):
    page: str
    text: str
    md: str
    images: list[dict[str,str]]
    status: str
    links: list[str]
    width: float
    height: float
    triggeredAutoMode: bool
    items: list[JSONItemOutput]
    block_type: BlockTypes = BlockTypes.Document


class LLAMAJSONOutput(BaseModel):
    md:str
    html:str 
    text:str
    pages: list[dict[str, Any]]
    metadata: dict[str, Any] 
    images:dict[str, Any]
 
 
def cleanup_text(full_text:str):
    full_text = re.sub(r'\n{3,}', '\n\n', full_text)
    full_text = re.sub(r'(\n\s){3,}', '\n\n', full_text)
    return full_text


def save_images(images: dict[str, Any]) -> dict[str, str]:

    output_dir = "./images"
    os.makedirs(output_dir, exist_ok=True)

 
    saved_paths = {}

    for img_name, img in images.items():
        file_path = os.path.join(output_dir, img_name)
        img.save(file_path, "PNG", optimize=False, compress_level=3)
        saved_paths[img_name] = file_path

    return saved_paths

class Markdownify(MarkdownConverter):
    paginated_md:dict[str, str]= {}

    def __init__(self, paginate_output, page_separator, **kwargs):
        super().__init__(**kwargs)
        self.paginate_output = paginate_output
        self.page_separator = page_separator

    def convert_div(self, el, text, convert_as_inline):
        is_page = el.has_attr('class') and el['class'][0] == 'page'
        if self.paginate_output and is_page:
            page_id = el['data-page-id']
            pagination_item = "\n\n" + "{" + str(page_id) + "}" + self.page_separator + "\n\n"
            self.paginated_md[f"{str(page_id)}"] = text
            return pagination_item + text
        else:
            return text

    def convert_p(self, el, text, *args):
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
    
    def get_paginated_md(self) -> dict[str, str]:
        return self.paginated_md


class LLAMAJSONRenderer(LLAMAHTMLRenderer):
    page_separator: str = "-" * 48
    def __call__(self, document: Document) -> LLAMAJSONOutput:
        document_output = document.render()
        paginated_html = {}
        paginated_images= {}
        full_html, images, paginated_html, paginated_images = self.extract_html(document, document_output, paginated_html, paginated_images)
 
        md_cls = Markdownify(
            True,
            self.page_separator,
            heading_style="ATX",
            bullets="-",
            escape_misc=False,
            escape_underscores=False,
            escape_asterisks=False,
            sub_symbol="<sub>",
            sup_symbol="<sup>",
        )
        markdown = md_cls.convert(full_html)
        full_markdown = cleanup_text(markdown)
        paginated_md = md_cls.get_paginated_md()
        pageKeys = list(paginated_md.keys())

        llama_json_result = []
        full_text = ""
        for pageIdx in pageKeys:
            # saved_images = {}
            # un-comment for image saving not with Minio
            # if paginated_images.get(pageIdx):
            #     saved_images = save_images(paginated_images[pageIdx])
            html_result = paginated_html[pageIdx]
            text_results = html_text.extract_text(html_result, guess_layout=True)
            full_text += text_results
            llama_json_result.append(
                {
                "page":pageIdx,
                "md": paginated_md[pageIdx],
                "doc_images":paginated_images[pageIdx],
                "text": text_results,
                "status": "OK",
                "links": [],
                "width": 0,
                "height": 0,
                "triggeredAutoMode": False,
                }
            )
 
        return LLAMAJSONOutput(
            md= full_markdown,
            html = full_html,
            text= full_text,
            pages = llama_json_result,
            images=images,
            metadata=self.generate_document_metadata(document, document_output)
        )
