# SWParse : Skyward's Smart parser for image and multi-document parsing for LLMs

Latest Version : 0.6.0

## Summary

The SWParse  system is a smart document parser that integrates well with LLamaIndex RAG  that extracts Structured text from various file types, including images and documents.
Features:

- Support for multiple file formats and languages ( PDF , DOCX , XLSX , HTML , Markdown , Images and Several Plain Text files)
- High Performance and Accurate text extraction using Document Structure detection, Table Detection and for OCR
- Caching to avoid re-processing the same document multiple times (WIP)
- Page separation and targeted page extraction
- Asynchronous processing with queues for efficient processing of multiple files
- Progress tracking
- Intuitve UI for Document Management

See `CHANGELOG.md` for details.

## Quick Start

### Docker

With GPU

```bash
cp .env.docker.example .env
docker compose up
```

Without GPU

```bash
cp .env.docker.example .env
docker compose -f docker-compose.cpu.yml up
```

### SWParse table extraction syntax

```
{table_1} = {column_1:type}, {column_2:type}, ..., {column_n:type} - {extraction_mode}; {table_2} = ...; as {output_type}
```

**Table Name** can be any string containing a-z, A-Z, 0-9 and " "

**Column Name** can be any string containing a-z, A-Z, 0-9 and " "

**Column Type** (Optional)

- string (default) = str, text, string
- integer = int, number
- float = float
- boolean = bool, boolean
- date = date
- list type = {type}[] (e.g. text[], int[])

**Extraction Mode** (Optional, Case in-sensitive)

- sentence splitting (default) = sent, sentence, by sentence, by_sentence, bySentence
- line splitting = ln, line, by line, by_line, byLine

**Output Type** (Optional, Case in-sensitive)

as {output_type}

- json (default) = output as json string
- csv = output as csv string
- md = output as markdown string
- html = output as html string

### Example Queries

```
table 1 = column 1, column 2: number; table 2 = col 1: str[], col 2: bool - byLine; as json

students = first name: text, last name: text, age: int, Favorite Subjects: text[]; as MD
```

Query syntax can be tested at `/api/parsing/query_syntax` endpoint

<hr>

To quickly get a development environment running, run the following:

```shell
make install
. .venv/bin/activate
```

### Local Development

```bash
cp .env.local.example .env
pdm run start-infra # this starts a database and redis instance only
pdm run swparse run
# to stop the database and redis, run
pdm run stop-infra
```

## Api Documentation

## **DEMO Endpoints**

- New Documentation System : [http://localhost:8000//schema](http://localhost:8000//schema)
- Old Documentation System : [http://localhost:8000//schema/docs](http://localhost:8000//schema/docs)
- base_url : [http://localhost:8000/](http://localhost:8000/)
- llama_parse Compatibility :

```python
parser = LlamaParse(
    api_key="llx-...",  # can also be set in your env as LLAMA_CLOUD_API_KEY
    result_type="markdown",  # "markdown" and "text" are available
    num_workers=2,  # if multiple files passed, split in `num_workers` API calls
    verbose=True,
    language="en",  # Optionally you can define a language, default=e
    base_url="http://localhost:8000"
)
```

- See `example.ipynb`

### Uploading

#### `POST /api/parsing/upload`

- **Description:** Upload a file and create a new job.
- **Request Body:**
  - `file`: The file to upload.
- **Response:**
  - `201`: The job is created and the job status is returned in the response body.
  - `400`: Bad request syntax or unsupported method.

### Parsing

#### `GET /api/parsing/job/{job_id}`

- **Description:** Check the status of a job.
- **Parameters:**
  - `job_id`: The ID of the job to check.
- **Response:**
  - `200`: The job status is returned in the response body.
  - `400`: Bad request syntax or unsupported method.

#### `GET /api/parsing/job/{job_id}/result/{result_type}`

- **Description:** Get the result of a job.
- **Parameters:**
  - `job_id`: The ID of the job to get the result for.
  - `result_type`: The type of result to retrieve (e.g. markdown).
- **Response:**
  - `200`: The job result is returned in the response body.
  - `400`: Bad request syntax or unsupported method.

### SAQ (Worker Queue)

#### `GET /saq/api/queues`

- **Description:** List all configured worker queues.
- **Response:**
  - `200`: A list of queue information is returned in the response body.

#### `GET /saq/api/queues/{queue_id}`

- **Description:** Get the details of a specific queue.
- **Parameters:**
  - `queue_id`: The ID of the queue to get the details for.
- **Response:**
  - `200`: The queue details are returned in the response body.
  - `400`: Bad request syntax or unsupported method.

#### `GET /saq/api/queues/{queue_id}/jobs/{job_id}`

- **Description:** Get the details of a specific job in a queue.
- **Parameters:**
  - `queue_id`: The ID of the queue that the job belongs to.
  - `job_id`: The ID of the job to get the details for.
- **Response:**
  - `200`: The job details are returned in the response body.
  - `400`: Bad request syntax or unsupported method.

#### `POST /saq/api/queues/{queue_id}/jobs/{job_id}/abort`

- **Description:** Abort a running job.
- **Parameters:**
  - `queue_id`: The ID of the queue that the job belongs to.
  - `job_id`: The ID of the job to abort.
- **Response:**
  - `202`: The job is aborted and the response body is empty.
  - `400`: Bad request syntax or unsupported method.

#### `POST /saq/api/queues/{queue_id}/jobs/{job_id}/retry`

- **Description:** Retry a failed job.
- **Parameters:**
  - `queue_id`: The ID of the queue that the job belongs to.
  - `job_id`: The ID of the job to retry.
- **Response:**
  - `202`: The job is retried and the response body is empty.
  - `400`: Bad request syntax or unsupported method.

## **Schemas**

### JobMetadata

- **Properties:**
  - `credits_max`: The maximum number of credits available.
  - `credits_used`: The number of credits used.
  - `job_credits_usage`: The number of credits used by the job.
  - `job_is_cache_hit`: Whether the job is a cache hit.
  - `job_pages`: The number of pages in the job.

### JobResult

- **Properties:**
  - `job_metadata`: The job metadata.
  - `markdown`: The markdown result of the job.

### JobStatus

- **Properties:**
  - `id`: The ID of the job.
  - `status`: The status of the job.

### QueueInfo

- **Properties:**
  - `active`: The number of active jobs in the queue.
  - `jobs`: A list of job information in the queue.
  - `name`: The name of the queue.
  - `queued`: The number of queued jobs in the queue.
  - `scheduled`: The number of scheduled jobs in the queue.
  - `workers`: A list of worker information in the queue.

## **Error Handling**

The API returns error responses in the following format:

- `400`: Bad request syntax or unsupported method.
- `404`: Not found.

## App Commands

```bash
❯ swparse

 Usage: swparse [OPTIONS] COMMAND [ARGS]...

 Litestar CLI.

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --swparse          TEXT       Module path to a Litestar application (TEXT)   │
│ --swparse-dir      DIRECTORY  Look for APP in the specified directory, by    │
│                           adding this to the PYTHONPATH. Defaults to the     │
│                           current working directory.                         │
│                           (DIRECTORY)                                        │
│ --help     -h             Show this message and exit.                        │
╰──────────────────────────────────────────────────────────────────────────────╯
Using Litestar swparse from env: 'swparse.asgi:swparse'
Loading environment configuration from .env
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ assets       Manage Vite Tasks.                                              │
│ database     Manage SQLAlchemy database components.                          │
│ info         Show information about the detected Litestar swparse.           │
│ routes       Display information about the application's routes.             │
│ run          Run a Litestar swparse.                                         │
│ schema       Manage server-side OpenAPI schemas.                             │
│ sessions     Manage server-side sessions.                                    │
│ users        Manage application users and roles.                             │
│ version      Show the currently installed Litestar version.                  │
│ workers      Manage background task workers.                                 │
╰──────────────────────────────────────────────────────────────────────────────╯

```

## Database Commands

Alembic integration is built directly into the CLI under the `database` command.

```bash
❯ swparse database
Using Litestar swparse from env: 'swparse.asgi:create_app'

 Usage: swparse database [OPTIONS] COMMAND [ARGS]...

 Manage SQLAlchemy database components.

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help  -h    Show this message and exit.                                    │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ downgrade              Downgrade database to a specific revision.            │
│ init                   Initialize migrations for the project.                │
│ make-migrations        Create a new migration revision.                      │
│ merge-migrations       Merge multiple revisions into a single new revision.  │
│ show-current-revision  Shows the current revision for the database.          │
│ stamp-migration        Mark (Stamp) a specific revision as current without   │
│                        applying the migrations.                              │
│ upgrade                Upgrade database to a specific revision.              │
╰──────────────────────────────────────────────────────────────────────────────╯

```

### Upgrading the Database

```bash
❯ swparse database upgrade
Using Litestar swparse from env: 'swparse.asgi:create_app'
Starting database upgrade process ───────────────────────────────────────────────
Are you sure you you want migrate the database to the "head" revision? [y/n]: y
2023-10-01T19:44:13.536101Z [debug    ] Using selector: EpollSelector
2023-10-01T19:44:13.623437Z [info     ] Context impl PostgresqlImpl.
2023-10-01T19:44:13.623617Z [info     ] Will assume transactional DDL.
2023-10-01T19:44:13.667920Z [info     ] Running upgrade  -> c3a9a11cc35d, init
2023-10-01T19:44:13.774932Z [debug    ] new branch insert c3a9a11cc35d
2023-10-01T19:44:13.783804Z [info     ] Pool disposed. Pool size: 5  Connections
 in pool: 0 Current Overflow: -5 Current Checked out connections: 0
2023-10-01T19:44:13.784013Z [info     ] Pool recreating
```

## Worker Commands

```bash
❯ swparse worker
Using Litestar swparse from env: 'swparse.asgi:create_app'

 Usage: swparse worker [OPTIONS] COMMAND [ARGS]...

 Manage application background workers.

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help  -h    Show this message and exit.                                    │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ run       Starts the background workers.                                     │
╰──────────────────────────────────────────────────────────────────────────────╯

```

## Run Commands

To run the application through Granian (HTTP1 or HTTP2) using the standard Litestar CLI, you can use the following:

```bash
❯ swparse run --help
Using Litestar swparse from env: 'swparse.asgi:swparse'
Loading environment configuration from .env

 Usage: swparse run [OPTIONS]

 Run a Litestar swparse.
 The swparse can be either passed as a module path in the form of <module
 name>.<submodule>:<swparse instance or factory>, set as an environment variable
 LITESTAR_APP with the same format or automatically discovered from one of
 these canonical paths: swparse.py, asgi.py, application.py or swparse/__init__.py.
 When auto-discovering application factories, functions with the name
 ``create_app`` are considered, or functions that are annotated as returning a
 ``Litestar`` instance.

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --port                   -p  INTEGER                 Serve under this port   │
│                                                      (INTEGER)               │
│                                                      [default: 8000]         │
│ --wc,--web-concurrency…  -W  INTEGER RANGE           The number of processes │
│                              [1<=x<=7]               to start.               │
│                                                      (INTEGER RANGE)         │
│                                                      [default: 1; 1<=x<=7]   │
│ --threads                    INTEGER RANGE [x>=1]    The number of threads.  │
│                                                      (INTEGER RANGE)         │
│                                                      [default: 1; x>=1]      │
│ --blocking-threads           INTEGER RANGE [x>=1]    The number of blocking  │
│                                                      threads.                │
│                                                      (INTEGER RANGE)         │
│                                                      [default: 1; x>=1]      │
│ --threading-mode             THREADMODES             Threading mode to use.  │
│                                                      (THREADMODES)           │
│ --http                       HTTPMODES               HTTP Version to use     │
│                                                      (HTTP or HTTP2)         │
│                                                      (HTTPMODES)             │
│ --opt                                                Enable additional event │
│                                                      loop optimizations      │
│ --backlog                    INTEGER RANGE [x>=128]  Maximum number of       │
│                                                      connections to hold in  │
│                                                      backlog.                │
│                                                      (INTEGER RANGE)         │
│                                                      [default: 1024; x>=128] │
│ --host                   -H  TEXT                    Server under this host  │
│                                                      (TEXT)                  │
│                                                      [default: 127.0.0.1]    │
│ --ssl-keyfile                FILE                    SSL key file (FILE)     │
│ --ssl-certificate            FILE                    SSL certificate file    │
│                                                      (FILE)                  │
│ --create-self-signed-c…                              If certificate and key  │
│                                                      are not found at        │
│                                                      specified locations,    │
│                                                      create a self-signed    │
│                                                      certificate and a key   │
│ --http1-buffer-size          INTEGER RANGE           Set the maximum buffer  │
│                              [x>=8192]               size for HTTP/1         │
│                                                      connections             │
│                                                      (INTEGER RANGE)         │
│                                                      [default: 417792;       │
│                                                      x>=8192]                │
│ --http1-keep-alive/--n…                              Enables or disables     │
│                                                      HTTP/1 keep-alive       │
│                                                      [default:               │
│                                                      http1-keep-alive]       │
│ --http1-pipeline-flush…                              Aggregates HTTP/1       │
│                                                      flushes to better       │
│                                                      support pipelined       │
│                                                      responses               │
│                                                      (experimental)          │
│ --http2-adaptive-windo…                              Sets whether to use an  │
│                                                      adaptive flow control   │
│                                                      for HTTP2               │
│ --http2-initial-connec…      INTEGER                 Sets the max            │
│                                                      connection-level flow   │
│                                                      control for HTTP2       │
│                                                      (INTEGER)               │
│ --http2-initial-stream…      INTEGER                 Sets the                │
│                                                      `SETTINGS_INITIAL_WIND… │
│                                                      option for HTTP2        │
│                                                      stream-level flow       │
│                                                      control                 │
│                                                      (INTEGER)               │
│ --http2-keep-alive-int…      OPTIONAL                Sets an interval for    │
│                                                      HTTP2 Ping frames       │
│                                                      should be sent to keep  │
│                                                      a connection alive      │
│                                                      (OPTIONAL)              │
│ --http2-keep-alive-tim…      INTEGER                 Sets a timeout for      │
│                                                      receiving an            │
│                                                      acknowledgement of the  │
│                                                      HTTP2 keep-alive ping   │
│                                                      (INTEGER)               │
│ --http2-max-concurrent…      INTEGER                 Sets the                │
│                                                      SETTINGS_MAX_CONCURREN… │
│                                                      option for HTTP2        │
│                                                      connections             │
│                                                      (INTEGER)               │
│ --http2-max-frame-size       INTEGER                 Sets the maximum frame  │
│                                                      size to use for HTTP2   │
│                                                      (INTEGER)               │
│ --http2-max-headers-si…      INTEGER                 Sets the max size of    │
│                                                      received header frames  │
│                                                      (INTEGER)               │
│ --http2-max-send-buffe…      INTEGER                 Set the maximum write   │
│                                                      buffer size for each    │
│                                                      HTTP/2 stream           │
│                                                      (INTEGER)               │
│ --url-path-prefix            TEXT                    URL path prefix the swparse │
│                                                      is mounted on           │
│                                                      (TEXT)                  │
│ --debug                  -d                          Run swparse in debug mode   │
│ --pdb,--use-pdb          -P                          Drop into PDB on an     │
│                                                      exception               │
│ --respawn-failed-worke…                              Enable workers respawn  │
│                                                      on unexpected exit      │
│ --reload                 -r                          Reload server on        │
│                                                      changes                 │
│ --help                   -h                          Show this message and   │
│                                                      exit.                   │
╰──────────────────────────────────────────────────────────────────────────────╯

```