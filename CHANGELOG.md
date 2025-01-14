## v0.7.6 (2025-01-14)

### Feat

- cleanup test code and logging
- JWT omit on testing routes
- benchmark testing atomatic statistics generation in md, GPU VRAM log
- added concurrent stress testing and memory usage statistics
- pdm lock file resolve
- pdm lock for psutil dependency
- added memory usage log using psutil

### Fix

- memory usage log position adjust
- pdm lock to resolve uuid_utils dependency issue

## v0.7.6 (2025-01-09)

### Features

- Added benchmark for Markdown extraction, `force_ocr`, and `plain_text` processing in swparse.
- Refactor the `force_ocr` option handling in the extraction controller to support multiple extractions.

### Fixes

- Updated the file checksum logic to account for the `force_ocr` option.
- Normalized image keys extracted from Excel files.
- Resolved an issue where saved images were overwriting those from previous sheets during `sheet_index` based extraction.

### Improvements

- Upgraded marker-pdf to v1.2.3.
- Improved OCR functionality, now capable of intelligently determining when reapplying OCR is necessary.


## v0.7.5 (2025-01-02)

### Features

- Integrated images into the extracted results of Excel files, such as in HTML and Markdown formats.
- Removed the sheet_index_type parameter to make the sheet indexing more intuitive.
- Introduced a fallback mechanism for reading sheet indexes when specified as a number and improved handling of incorrect sheet names.
- Added a plain_text (boolean) parameter to extract text only from PDF files.

### Fixes

- Resolved an issue where images were missing when extracting from Excel files.

## v0.7.4 (2024-12-24)

### Feat

- Integrated sheet indexing into checksum calculations for Excel files to ensure unique hashes based on sheet selection.

### Fix

- Resolve request hanging issue during authentication errors with multipart form data uploads in middleware


## v0.7.3 (2024-12-23)

### Feat

- added sheet indexing docs to ReadMe file
- checksum checking account for sheet indexing, fix: sheet_index_type key inconsistency and changed to request's body
- increase request body's size
- force_ocr option added for parsing PDF and images

### Fix

- add subtitle to ReadMe
- put back to the previous processing order for pdf parsing
- clean unnecessary files

## v0.7.2 (2024-12-13)

### Feat

- Added sheet indexing support for Excel file extraction, including .xlsx and .xls.
- Enabled extraction from Excel files based on either sheet names or sheet indexes.


### Fix

- clean code and files

## v0.7.1 (2024-12-12)

### Feat

- Added endpoints to generate, list, and delete API keys.
- Added endpoint to rename an API key.


### Fix

- remove sayHello route and model caching to app state
- clean code and fix testing files

## v0.7.0 (2024-12-09)

### Features

- Replaced the old marker version with the newly released version 1.0.2
- Set caching flag from environment variable.
- Added a link section for each page in JSON result.
- Added caching for marker models during server setup.
- Added data type validation for JSON results to ensure compatibility with LlamaParse.

### Improvements

- Significantly reduced marker model loading time.
- Doubled the speed of layout and text detection.
- Improved the output of text items in the JSON result

### Fix

- Fixed the text regular expression to properly capture text, excluding images and links, in the JSON result.
- Fixed JSON result syntax to ensure compatibility with LlamaParse.


## v0.6.3 (2024-11-26)

### Fix

- **wip**: API auth token in middleware

## v0.6.2 (2024-11-25)

### Feat

- add items in json result

### Fix

- images filepath exceeding meta data size, json result JSON dumps

## v0.6.1 (2024-11-23)

## v0.6.0 (2024-11-22)

### Feat

- get json result per page with llamaparse datastructure for pdf
- advanced table extraction from document controller
- llama parse parsing_instruction support
- opensource release preparation
- default/env API key authorization
- save metadata with dedicated jobid file in minio
- advanced table extraction from document controller (wip)
- caching results with jobId in minio bucket
- merge with hm3-file-checksum branch
- return extracted result from existing files if the uploaded file is already exist
- csv, json, md outputs for table extraction
- table extraction
- resolve merge
- sentence split label extractor
- add default data type in syntax parser
- **wip**: add syntax parser
- retry failed extraction API
- integrate extractions with documents
- add extraction module

### Fix

- handle empty metadata
- re-enable api key auth
- store metadata for pdf and iamge
- **wip**: return extracted result if the file is already uploaded
- change swparse api key header, return table extraction json in string
- add condition for table name so that table names are unique
- add condition so that entity labels are unique
- minor fixes
- fix job status handling for retry extraction API
- remove pagination from extraction list, add created_at update_at in schema
- fixed return document serialize with schema
- fix json decoder
- replace mdutils with snakemd

## v0.5.0 (2024-11-02)

### Feat

- extract images from docx, store images for pdf, image, docx
- API-key middleware auth for swparse route
- new model for API key migrated
- merge pptx parser
- table markdown for advanced extraction and fix: extra index col in xlsx
- add tables output to parsing api
- add pptx to markdown parser

### Fix

- header error?
- fix document detail api
- xlsx, csv malformed headers when passing no header documents
- replace html2text with pandas for markdown extraction in xlsx, advanced table extraction
- remove default inserted indexing col when converting csv to html

## v0.4.1 (2024-10-29)

## v0.4.0 (2024-10-29)

### Feat

- add pptx2md dependencies
- added unoserver in pdm.
- added old document parser for doc and ppt formats.
- added libreoffice image with unoserver installed in docker compose file.
- add pptx parser
- table only extraction and new 'table' content-type
- **parsers**: Added support for converting from PDF-> HTML,TXT , IMAGES->HTML,TXT , DOCX->HTML,TXT , XLSX -> HTML,TXT, CSV->HTML,TXT,MD
- text extraction for docx and xlsx
- text, html, md extraction for csv
- added base64 decode to handle extracted_file_type field
- merge with latest commit
- add getting extracted file presigned url
- changed the data type of extracted_file_paths field of Document
- parsing xlsx to (csv,html,md) and docx to (html,md) and saved to minio s3
- added support for html results. now we can extract html from pdf

### Fix

- surya locked to 0.6.12 , marker locked to 0.3.2 , removed libreoffice container, need to test more or find better alternative
- disable pptx conversion, remove pptx2md
- add pagination filter
- merge conflict
- standardize get_document API response to FileResponse
- refactor text extraction task and include html and markdown extraction for text/ file type
- replace xlsx2html with pandas for extracting html from xlsx
- typo in db query and refactor _pdf_exchange task
- handle error and return meaningful error messages if there is unsuported extraction format
- upgraded pg to 17 and fixed version
- prune images after services up
- logging unsupported type error
- added missing vendor files.
- caddy to vendor
- **migrations**: add back and fix column name
- **migrations**: fix migrations
- **migrations**: disable data migration for non_null
- **startup**: added caddy to dev startup
- **migrations**: final attempt
- **migrations**: another attempt
- **migrations**: attempt to fix again
- **migrations**: attempt to fix nullable
- **migration**: antoher attempt to fix extracted paths
- **migrations**: attempt to fix nullable extracted path
- **migrations**: Fix migration of docs to allow extracted path to null
- typo in docker-compose.cpu.ymal
- uncomment pdm install in bash file
- **wip**: update all extracted results in db
- docker file

## v0.3.0 (2024-10-16)

### Feat

- retrieve uploaded document file API
- load models only if they are unloaded
- markdown retrieve API
- recent document list sorting
- upload document and get document list by user_id
- **wip**: document model changed
- s3_url and several fixes to document
- added s3url to job status , chore: added cpu only launcher , fix: env vars
- **wip**: document upload api
- change xlsx parser to handle both xls and xlsx file types
- **wip**: adding document and extraction controllers
- two new models: Document and Extraction
- UI host preparation
- docx support , xlsx support , html and many other text files . User Login API , Oauth Support , RBAC , User management support and User Teams and Tagging support
- fullstack integration with advanced quality swparse development
- branch merge with hm3-text-extraction
- xlsx to markdown API
- text extraction for content-type text/ prefix files & xlsx to csv convert APIs
- Added additional features to the plan
- page number sync with lib
- page parsing support
- added llama_parse compatbile : See : example.ipynb
- add cleanup
- prod deployment sh files
- imaged and pdf parsing
- docker compose file for prod , runs on port 80
- docker compose file for prod , runs on port 80
- docker compose and docker build ready for deployment
- add a really nice api documentation
- intial working version with api compatibility

### Fix

- clean temp files created in path file of getDocumentContent API
- docker file
- change HTTP method from POST to GET
- job error handling for document and extraction API & status comparison typo
- prod , run on same dev image
- md file store and retreive url
- update document get api to update with extracted url when job is successed
- httpx syntax to get filename and extension
- DTO and return DTO in Document Controller
- set extracted file path to nullable with new migration file
- Type Checking remove to fix UUID errors
- add configs for local env
- proper caddy config
- inserting job to queue with timeout
- remove API endpoints and put them on worker
- various file input handling in xlsx to csv
- raised error instead of returning ok if a job failed
- parser errors on other docs
- increase time out to 999999
- Enum for status
- makle sure env is sourced
- volumne mountpoint
- wrong flag
- added missing files
- added missing files
- added missing files
- worker image bulding
- docker command
- docker command
- added missing files
- packaging
- auto create minio bucket
