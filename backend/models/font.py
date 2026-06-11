from pydantic import BaseModel


class ServerFontItem(BaseModel):
    id: str
    name: str
    file_name: str
    extension: str
    size_bytes: int
    sha256: str
    download_url: str
