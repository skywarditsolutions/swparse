import pandas
import io

def decode_content(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        # Fall back measure for non-UTF-8 encoded text files
        return content.decode("ISO-8859-1")


async def extract_text(content: bytes, content_type: str) -> str:

    decoded_content = decode_content(content)

    if content_type == "text/csv":
        csv_buffer = io.StringIO(decoded_content)
        df = pandas.read_csv(csv_buffer)
        return df.to_string(index=False)

    elif content_type in [
        "text/plain",
        "text/html",
        "text/css",
        "text/javascript",
        "text/markdown",
        "text/vtt",
    ]:
        return decoded_content

    elif content_type == "text/xml":
        return decoded_content

    return decoded_content
