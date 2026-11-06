"""Owner-authorized callers use immutable UUID artifacts, locally or in private Blob."""
import os
from pathlib import Path
import uuid
from .database import DATA_DIR

FILES={'records.json','evaluation.json','weights.npz','policy.json'}

def cloud_storage():return os.getenv('ARTIFACT_STORAGE')=='vercel-blob'

def folder(identifier):
    path=DATA_DIR/str(uuid.UUID(identifier))
    path.mkdir(parents=True,exist_ok=True)
    return path

def blob_path(identifier,filename):
    if filename not in FILES:raise ValueError('Unsupported artifact filename')
    return f'pricemesh/{uuid.UUID(identifier)}/{filename}'

def publish(identifier):
    if not cloud_storage():return
    from vercel.blob.sync import put_blob
    for path in folder(identifier).iterdir():
        if path.name in FILES:
            put_blob(blob_path(identifier,path.name),path.read_bytes(),access='private',allow_overwrite=True,
                     content_type='application/json' if path.suffix=='.json' else 'application/octet-stream')

def read(identifier,filename):
    if filename not in FILES:raise ValueError('Unsupported artifact filename')
    if cloud_storage():
        from vercel.blob.sync import get_blob
        from vercel.blob import BlobNotFoundError
        try:return get_blob(blob_path(identifier,filename),access='private').body
        except BlobNotFoundError as exc:raise FileNotFoundError('Artifact unavailable') from exc
    return (folder(identifier)/filename).read_bytes()

def policy_folder(identifier):
    path=folder(identifier)
    if cloud_storage():
        # Always restore from the durable store; a partial local file is not authoritative.
        for filename in ('weights.npz','policy.json'):
            data=read(identifier,filename)
            temporary=path/(filename+'.'+uuid.uuid4().hex+'.tmp')
            temporary.write_bytes(data)
            temporary.replace(path/filename)
    return path
