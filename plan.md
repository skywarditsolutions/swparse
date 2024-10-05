# Swparse: Phase1 ( Oct - EOY) 

The SWParse  system is a smart document parser that integrates well with LLamaIndex RAG  that extracts text from various file types, including images and documents. It is API Compatible with LlamaPrase and detect structures of documents when extracted as Markdown.



## Main Requirements:

* Support for multiple file formats and Langugage
  * File formats to be supported
    * PDF
      * Plain Text PDF
      * PDF With Images
    * DOC,DOCX
      * DOCX With Images
    * XLS,XLSX
      * Extract Sub tables
    * PPT/PPTX/RTF
    * All Regular Text Files
    * As many Image fiels as possibe



* Accurate text extraction using Several document extractitors and Deep Learning models, LLM , VLMS
  * Deep Learning
    * Surya
    * Marker
* Caching to avoid re-processing the same document multiple times
  * Auto Cached to S3 or S3 compatible object store
  * Detect if document is already extracted and cache.
* Page separation and target page extraction
* Fast Detection of Tables from Documents and Extraction of them. 
* Asynchronous processing for efficient processing of multiple files
* Progress tracking and verbose mode for detailed information
* Several Extraction Options
  * Markdown
  * Text
  * HTML
  * Markdown Tables
  * CSV
  * Image Extraction
* Advanced Extraction
  * Ablility to Query document by giving fields to extract
    * Input : List of fields , like SensibleML
    * Output : JSON
  * LLM and VLLM supported extractions.
    * Lllama3.2 Vision
    * CogVLM or MiniCPM
  * Features from Sensible.so



## Existing Features :

* API Parity with LLamaParse
* API Compatible with LLamaIndex
* Queue based Async Processing of documents.
* Automatically store uploaded docs in S3.
* OCR For Images
* Struture and Table detection for PDF and Images
* Markdown Output with Tables.
* Supported files : PDF , Images.
* Targeted page extraction

## Planned New Features :

* UI for SWParse
* Tabular Output ( CSV or PandasDF in Prequet ? )
* Natural Language based Document Section Search.
* Multi file support:
  * PDF,DOC,DOCX,XLS,XLSX,PPT,PPTX,HTML,CSV
* Custom Field base Query and JSON Extraction.
* VLLM based Extraction
* Plain Text Extraction
* Caching of results (uploads are already cached , Results may or may not need caching - determine base upon option? )
* Targeted Page Range Extraction ( from - to)
* Smart page detection and extraction , based on keyword or phrase?
* Advanced Extraction
  * Ablility to Query document by giving fields to extract
    * Input : List of fields , like SensibleML
    * Output : JSON
  * LLM and VLLM supported extractions.
    * Lllama3.2 Vision
    * CogVLM or MiniCPM
  * Features from Sensible.so

## Planned Non-Functional Reqs:



* Terraform + Github CI/CD
* Observbility
* API Examples
* Notebook Examples



## Tech Stack:



### Current

* PDM
* Litestar
* SAQ
* Redis
* S3fs
* Surya/Marker
* PyMuPDF
* pdfium
* Minio
* Llama-parse
* Pandas

### Planned

* mammoth
  * DocX to HTML conversion planned for easy markdown extraction
* xlsx2html
  * XlsX to HTML conversion , planned to use for esay sub-table extraction
* Unstructured.io
  * Untested, could be useful for more structure extraction.
