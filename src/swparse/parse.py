"""
Utility to OCR a list of images and output them as one PDF

License: GNU AGPL 3.0
Author: (c) Harald Lieder, harald.lieder@outlook.com
Date: 2021-10-26
"""
import os
import sys

import pymupdf
from pymupdf import Document
if tuple(map(int, pymupdf.VersionBind.split("."))) < (1, 19, 0):
    raise ValueError("Need at least PyMuPDF v1.19.0")

imgfile = sys.argv[1]
pix = pymupdf.Pixmap(imgfile)  # make a pixmap form the image file
pdfbytes = pix.pdfocr_tobytes(language="eng")  # 1-page PDF with the OCRed image
pdf = pymupdf.open("pdf", pdfbytes)

out = open("output.txt", "wb") # create a text output
for page in pdf: # iterate the document pages
    text = page.get_text().encode("utf8") # get plain text (is in UTF-8)
    out.write(text) # write text of page
    out.write(bytes((12,))) # write page delimiter (form feed 0x0C)
out.close()


import pymupdf4llm
md_text = pymupdf4llm.to_markdown("./ocr-pdf.pdf",table_strategy="text")
print (md_text)
with open("output.md", "w") as out_md: # create a text output
    out_md.write(md_text)
