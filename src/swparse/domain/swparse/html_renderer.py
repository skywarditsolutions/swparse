from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from marker.renderers import BaseRenderer
from marker.schema import BlockTypes
from marker.schema.blocks import BlockId
from marker.schema.document import Document, DocumentOutput
from marker.renderers.html import HTMLRenderer


from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
 
# Ignore beautifulsoup warnings
import warnings
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)


class HTMLOutput(BaseModel):
    full_html:str
    metadata: dict[str, Any]
    paginated_html:dict[str, str]
    paginated_images: dict[str , Any]


class LLAMAHTMLRenderer(BaseRenderer):
    image_blocks: list = [BlockTypes.Picture, BlockTypes.Figure]
    page_blocks: list = [BlockTypes.Page]
    paginate_output: bool = True
    image_extraction_mode: Literal["lowres", "highres"] = "highres"


    def extract_image(self, document:Document, image_id:BlockId):
        image_block = document.get_block(image_id)
        page = document.get_page(image_block.page_id)
        page_img = page.lowres_image if self.image_extraction_mode == "lowres" else page.highres_image
        image_box = image_block.polygon.rescale(page.polygon.size, page_img.size)
        cropped = page_img.crop(image_box.bbox)
        return cropped


    def extract_html(self, document:Document, document_output:DocumentOutput, paginated_html: dict[str, str], paginated_images: dict[str, Any], level:int=0 )->tuple[str, dict[str, Any], dict[str, str], dict[str, Any]]:
        soup = BeautifulSoup(document_output.html, 'html.parser')

        content_refs = soup.find_all('content-ref')
        ref_block_id = None
        images = {}
        for ref in content_refs:
            src = ref.get('src')
            sub_images = {}
            for item in document_output.children:
                if item.id == src:
                    content, sub_images_, paginated_html, paginated_images = self.extract_html(document, item, paginated_html, paginated_images, level + 1)
                    sub_images.update(sub_images_)
                    ref_block_id: BlockId = item.id
                    break

            if ref_block_id.block_type in self.remove_blocks:
                ref.replace_with('')
            elif ref_block_id.block_type in self.image_blocks:
                if self.extract_images:
                    image = self.extract_image(document, ref_block_id)
                    image_name = f"{ref_block_id.to_path()}.png"
                    image_name = image_name.lower()
                    images[image_name] = image
                    
                    # paginated images collection
                    if self.paginate_output and f"{ref_block_id.page_id}" in paginated_images:
                        paginated_images[f"{ref_block_id.page_id}"][image_name] = image
                    else:
                        paginated_images[f"{ref_block_id.page_id}"] = {image_name: image}

                    ref.replace_with(BeautifulSoup(f"<p><img alt='{image_name}' src='{image_name}'></p>", 'html.parser'))
                else:
                    ref.replace_with('')
            elif ref_block_id.block_type in self.page_blocks:
                images.update(sub_images)

                # paginated HTML collection
                if self.paginate_output:
                    paginated_html[f"{ref_block_id.page_id}"] = content
                    content = f"<div class='page' data-page-id='{ref_block_id.page_id}'>{content}</div>"


                ref.replace_with(BeautifulSoup(f"{content}", 'html.parser'))
            else:
                images.update(sub_images)
                ref.replace_with(BeautifulSoup(f"{content}", 'html.parser'))

        output = str(soup)
        if level == 0:
            output = self.merge_consecutive_tags(output, 'b')
            output = self.merge_consecutive_tags(output, 'i')

        return output, images, paginated_html, paginated_images


    def __call__(self, document:Document) -> HTMLOutput:
        document_output = document.render()
        paginated_html:dict[str, str] = {}
        paginated_images:dict[str, Any] = {}
        full_html, images, paginated_html, paginated_images = self.extract_html(document, document_output, paginated_html, paginated_images)
        return HTMLOutput(
            full_html=full_html,
            paginated_html= paginated_html,
            paginated_images = paginated_images,
            metadata=self.generate_document_metadata(document, document_output)
        )

 