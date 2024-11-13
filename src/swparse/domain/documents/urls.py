DOCUMENT_LIST = "/api/documents/list"  # noqa: INP001
DOCUMENT_DETAIL = "/api/documents/{id:uuid}"
UPLOAD_DOCUMENT = "/api/documents/upload"
UPLOAD_DOCUMENT_PAGE = "/api/documents/upload/page/{page:int}"

DOCUMENT_UPLOAD = "/api/documents/upload"
LIST_DIR = "/api/bucket/dirs"

DOCUMENT_CONTENT = "/api/documents/content/{id:uuid}"
EXTRACTED_CONTENT = "/api/documents/extracted_content/{id:uuid}/result/{result_type:str}"
EXTRACT_ADVANCED_TABLES = "/api/documents/{document_id:uuid}/advanced_table"
