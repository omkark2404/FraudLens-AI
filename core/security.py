import os
import mimetypes

def is_safe_file(file_storage) -> bool:
    """
    Check if a FileStorage object contains a safe file type (JPG, PNG, PDF)
    using magic bytes validation.
    """
    if not file_storage:
        return False
        
    header = file_storage.read(8)
    file_storage.seek(0)
    
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return True
    elif header.startswith(b'\xff\xd8\xff'):
        return True
    elif header.startswith(b'%PDF-'):
        return True
        
    return False
