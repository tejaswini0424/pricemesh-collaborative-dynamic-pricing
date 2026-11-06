import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest
import uuid

from backend.app import artifacts

class CloudArtifactTests(unittest.TestCase):
    def test_paths_reject_arbitrary_files(self):
        with self.assertRaises(ValueError):artifacts.blob_path('not-a-uuid','records.json')
        with self.assertRaises(ValueError):artifacts.blob_path(str(uuid.uuid4()),'../../secret')

    def test_reads_come_from_private_storage_instead_of_ephemeral_disk(self):
        identifier=str(uuid.uuid4())
        with patch.dict(os.environ,{'ARTIFACT_STORAGE':'vercel-blob'}):
            with patch('vercel.blob.sync.get_blob',return_value=SimpleNamespace(body=b'[{"units":3}]')) as download:
                self.assertEqual(artifacts.read(identifier,'records.json'),b'[{"units":3}]')
                download.assert_called_once_with(f'pricemesh/{identifier}/records.json',access='private')

    def test_publish_never_uploads_unrecognized_local_files(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            (folder/'policy.json').write_text('{"version":1}')
            (folder/'unrelated-secret.txt').write_text('must-not-upload')
            identifier=str(uuid.uuid4())
            with patch.dict(os.environ,{'ARTIFACT_STORAGE':'vercel-blob'}),patch.object(artifacts,'folder',return_value=folder):
                with patch('vercel.blob.sync.put_blob') as upload:
                    artifacts.publish(identifier)
                    self.assertEqual(upload.call_count,1)
                    self.assertEqual(upload.call_args.kwargs['access'],'private')
                    self.assertTrue(upload.call_args.args[0].endswith('/policy.json'))
