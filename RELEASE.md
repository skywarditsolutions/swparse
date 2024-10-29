
# Release Note

## Version 0.4.0

We're excited to announce the release of our new version! This update brings a host of new features, improvements, and bug fixes. Here's a summary of what's changed:

### Highlights

## New Features

### New Parsing Capabilities

- **PDF, DOCX, XLSX, CSV, IMAGES**: Extended support for extracting these file types to HTML, TXT, MD, and PDF formats.
- **Text, HTML, MD Extraction for CSV**: Enhanced support for extracting text, HTML, and Markdown from CSV files.
- **Table Extraction(Experimental)** : Advanced extraction with `table` mode for CSV , HTML , and XLSX and XLM formats.

### Improved Extraction

- **Table Only Extraction**: Added functionality to extract tables only and introduced a new 'table' content-type.
- **Base64 Decode**: Implemented base64 decode for handling the `extracted_file_type` field.

### API Enhancements for User app backend

- **Presigned URL**: Added functionality to get presigned URLs for extracted files.
- **Standardized Response**: Refactored the `get_document` API response to return a standard `FileResponse`.
- **Paginated Filter**: Introduced pagination filter for better data navigation.

### Frontend

- **File Upload**: Revised UI to focus on consecutive file upload and processing.
- **Preview**: PDF and Image preview for uploaded docs
- **Extracted View** : Extracted Raw and Rendered views
- **Bigger Space** : Improve UI so convient for document side by side previews.

## Bug Fixes & Improvements

### Dependency Updates & Resolutions

- Updated Surya and Marker versions to resolve locking issues.
- Removed LibreOffice container due to testing and alternative exploration needs.
- Upgraded PostgreSQL (pg) version to 17 and fixed version-related issues.

### Parsing & Extraction Fixes

- **PPTX Conversion**: Disabled PPTX conversion temporarily and removed pptx2md dependency due to ongoing issues.
- **Unsupported Format Error Handling**: Improved error handling and added meaningful error messages for unsupported extraction formats.

### Infrastructure & Performance Improvements

- **Image Pruning**: Implemented image pruning after services startup to optimize resource usage.
- **Vendor File Addition**: Added missing vendor files to service via  Caddy reverse proxy.

### Migration & Startup Scripts

- Fixed various migration issues related to column names, nullability, and data migration. Multiple attempts were made to resolve these issues.
- Updated Docker Compose file to fix a typo.
- Uncommented PDM install command in the bash script for proper initialization.

### Ongoing Work

- **pptx extraction**: WIP for converting PowerPoint presentations to Markdown.
- **Unoserver Support**:  Old MS97 formats to support via LibreOffice based exractions
- **API Key Creation**: API Key creation by admin and Permission based on API key for parsers.
- **LibreOffice Image with Unoserver**: Test Docker Compose file to support parsing old file formats.
  
## Version : 0.3.0

## Structured Extractions support

Automatic structure detection and extraction of multiple file format.

- Images -> Markdown
- PDF  -> Markdown
- Docx -> Markdown
- XLSX -> Markdown

## Plain text extraction support

Plain text file parsing and extraction

- Multiple plain text documents.

## APIs for Frotnend

Frontend Facing API for User , Login and Per User parsing.

- User Registration and Login
- ROLE Based Access Control
  - Registured Users
  - Verified Users
  - Admin User
- User specific Extraciton API
- Recent Document Listing

## Frontend

Easy to use frontend and advanced extraction UI

- Upload and Extraction support
- Choosing Extraction formats (currently markdown)
- User automatic registration
- User Login
