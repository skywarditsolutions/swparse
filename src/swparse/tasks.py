from __future__ import annotations
from logging import getLogger
from typing import TYPE_CHECKING
import pymupdf4llm
import pymupdf
from PIL import Image
from s3fs import S3FileSystem
from swparse.settings import storage
if TYPE_CHECKING:
    from saq.types import Context
import pypdfium2 as pdfium
logger = getLogger(__name__)
BUCKET = storage.BUCKET
MINIO_ROOT_USER = storage.ROOT_USER
MINIO_ROOT_PASSWORD = storage.ROOT_PASSWORD
import mimetypes
async def parse_mu_s3(ctx: Context, *, s3_url: str, ext: str) -> str:
    s3 = S3FileSystem(
        # asynchronous=True,
        endpoint_url=storage.ENPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False
    )

        
    with s3.open(s3_url) as doc:
        try:
            markdown = pymupdf4llm.to_markdown(
                pymupdf.open(mimetypes.guess_extension(ext), doc.read())
            )
        except:
            markdown = ""
    logger.error("parse_mu_s3")
    logger.error(s3_url)
    logger.error(markdown)
    return markdown
async def parse_pdf_markdown_s3(ctx: Context, *, s3_url: str) -> str:
    from swparse.convert import pdf_markdown
    s3 = S3FileSystem(
        # asynchronous=True,
        endpoint_url=storage.ENPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False
    )

    with s3.open(s3_url,mode="rb") as doc:
        markdown, doc_images, out_meta = pdf_markdown(doc.read(), max_pages=20)
    logger.error("parse_pdf_markdown_s3")
    logger.error(s3_url)
    logger.error(markdown)
    return markdown
async def parse_pdf_page_markdown_s3(ctx: Context, *, s3_url: str,page:int) -> str:
    from swparse.convert import pdf_markdown
    s3 = S3FileSystem(
        # asynchronous=True,
        endpoint_url=storage.ENPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False
    )

    with s3.open(s3_url,mode="rb") as doc:
        markdown,doc_images,out_meta = pdf_markdown(doc.read(),start_page=page,max_pages=1)
    logger.error("parse_pdf_markdown_s3")
    logger.error(s3_url)
    logger.error(markdown)
    return markdown

async def parse_image_markdown_s3(ctx: Context, *, s3_url: str, ext: str) -> str:
    from swparse.convert import pdf_markdown
    s3 = S3FileSystem(
        # asynchronous=True,
        endpoint_url=storage.ENPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False   
    )

    with s3.open(s3_url,mode="rb") as doc:
        pil_image = Image.open(doc).convert("RGB")
    pdf = pdfium.PdfDocument.new()

    image = pdfium.PdfImage.new(pdf)
    image.set_bitmap(pdfium.PdfBitmap.from_pil(pil_image))
    width, height = image.get_size()

    matrix = pdfium.PdfMatrix().scale(width, height)
    image.set_matrix(matrix)

    page = pdf.new_page(width, height)
    page.insert_obj(image)
    page.gen_content()

    with s3.open(f"{s3_url}.pdf","wb") as output:
        pdf.save(output)
    with s3.open(f"{s3_url}.pdf","rb") as input:
        markdown = pdf_markdown(input)

    logger.error("parse_image_markdown_s3")
    logger.error(s3_url)
    logger.error(markdown)
    return markdown[0]