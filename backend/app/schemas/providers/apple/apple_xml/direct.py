"""Limits for the direct XML upload endpoint.

The direct endpoint passes the whole file to Celery as a task argument. kombu's JSON
serializer keeps UTF-8 bytes as a string (escaping every quote in the XML attributes)
and base64-encodes anything else; the Redis transport then base64-encodes the whole
message body. That makes the message about 1.42x the file for XML and 1.78x for binary
content, and Redis refuses any value over ``proto-max-bulk-len`` (512 MiB by default),
so the hard ceiling is about 288 MiB.

Memory is the tighter bound: publishing the task holds several copies of the file in
the API process (about 6.6x the file at peak), and every message the worker reserves
stays in its memory (the xml_sync worker disables prefetch, so it holds only the messages
it runs). Larger files go
through the S3 multipart flow, which never puts the file in the broker.

The endpoint applies the smaller of this and the product-wide ``MAX_FILE_SIZE``.
"""

MAX_DIRECT_UPLOAD_SIZE = 200 * 1024 * 1024  # 200 MiB
