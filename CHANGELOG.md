## v0.0.1 (2024-10-29)

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
