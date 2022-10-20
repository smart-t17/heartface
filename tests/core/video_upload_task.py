import os
from unittest.mock import patch

from django.db import IntegrityError
from django.conf import settings
from django.test import TestCase

from tests.factories import VideoFactory, GlacierFileFactory
from heartface.apps.core.tasks import upload_video_glacier

import sure


class TestUpload(TestCase):
    @patch('heartface.apps.core.tasks.subprocess')
    def test_glacier_upload(self, subprocess):
        video = VideoFactory()

        subprocess.check_output.return_value = 'Archive ID: archiveId'

        upload_video_glacier(video.pk)

        video.glacierfile.archive_id.should.equal('archiveId')
        os.path.exists(video.videofile.path).should.be.falsy

    @patch('heartface.apps.core.tasks.subprocess')
    def test_missing_file(self, subprocess):
        video = VideoFactory()

        os.unlink(video.videofile.path)

        upload_video_glacier(video.pk).should.be.none

    @patch('heartface.apps.core.tasks.subprocess')
    @patch('heartface.apps.core.tasks.GlacierFile')
    @patch('heartface.apps.core.tasks.boto3')
    def test_already_uploaded_to_glacier(self, boto3, GlacierFile, subprocess):
        video = VideoFactory()
        GlacierFileFactory(video=video, size=100, archive_id='12345')

        client = boto3.client.return_value
        subprocess.check_output.return_value = 'Archive ID: archiveId'

        GlacierFile.objects.create.side_effect = IntegrityError()

        upload_video_glacier(video.pk).should.be.none

        client.delete_archive.assert_called_once_with(archiveId='archiveId',
                                                      vaultName=settings.AWS_GLACIER_VAULT_NAME)
