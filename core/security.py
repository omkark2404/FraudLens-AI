

def is_safe_file(file_storage) -> bool:
    """
    Check if a FileStorage object contains a safe file type (JPG, PNG, PDF)
    using magic bytes validation.
    """
    if not file_storage:
        return False

    header = file_storage.read(8)
    file_storage.seek(0)

    return bool(header.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"%PDF-")))
