from __future__ import annotations

from typing import Any

import re
import regex
import boto3
from botocore.config import Config
import html_text
from markdownify import MarkdownConverter
from bs4 import MarkupResemblesLocatorWarning

from marker.schema import BlockTypes
from marker.schema.document import Document

from .html_renderer import LLAMAHTMLRenderer
from .utils import save_image_sync
from .schemas import LLAMAJSONOutput
from swparse.config.app import settings
import structlog
from swparse.domain.swparse.utils import extract_md_components

# Ignore beautifulsoup warnings
import warnings

logger = structlog.getLogger()
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

BUCKET = settings.storage.BUCKET
MINIO_ROOT_USER = settings.storage.ROOT_USER
MINIO_ROOT_PASSWORD = settings.storage.ROOT_PASSWORD


def cleanup_text(full_text:str):
    full_text = re.sub(r'\n{3,}', '\n\n', full_text)
    full_text = re.sub(r'(\n\s){3,}', '\n\n', full_text)
    return full_text

 

class Markdownify(MarkdownConverter):
    paginated_md:dict[str, str]= {}

    def __init__(self, paginate_output:bool, page_separator:str, **kwargs:Any):
        super().__init__(**kwargs)
        self.paginate_output = paginate_output
        self.page_separator = page_separator

    def convert_div(self, el:Any, text:str, convert_as_inline:Any) -> str:
        is_page = el.has_attr('class') and el['class'][0] == 'page'
        if self.paginate_output and is_page:
            page_id = el['data-page-id']
            # pagination_item = "\n\n" + "{" + str(page_id) + "}" + self.page_separator + "\n\n"
            self.paginated_md[f"{str(page_id)}"] = text
            # return pagination_item + text
         
        return text

    def convert_p(self, el:Any, text:str, *args:Any):
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
        full_html, images , paginated_html, paginated_images = self.extract_html(document, document_output, paginated_html, paginated_images)

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
