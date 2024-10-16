## 0.2.0

### Feat

- retrieve uploaded document file API
- load models only if they are unloaded
- markdown retrieve API
- recent document list sorting
- upload document and get document list by user_id
- updated document controller to support s3_url output
- added s3url to job status , chore: added cpu only launcher , fix: env vars
- change xlsx parser to handle both xls and xlsx file types
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
- added llamaparse compatbile api : See : example.ipynb
- add cleanup
- prod deployment sh files
- imaged and pdf parsing
- api documentation via RapiDOC and Scalar
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
