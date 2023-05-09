"""
Automate some parts of GovQA portal handling
"""


# Standard Library
import cgi
import logging

# Third Party
import requests
from furl import furl
from govqa.base import GovQA
from smart_open.smart_open_lib import smart_open

# MuckRock
from muckrock.foia.models.communication import FOIACommunication
from muckrock.foia.models.file import get_path
from muckrock.portal.portals.manual import ManualPortal
from muckrock.portal.tasks import portal_task

logger = logging.getLogger(__name__)


class GovQAPortal(ManualPortal):
    """GovQA portal integreation"""

    def send_msg(self, comm, **kwargs):
        """Send a message via email if possible"""
        # send an email for not new submissions, which have a valid email address,
        # only for staff users for right now
        if (
            comm.category in ("f", "u")
            and comm.foia.email
            and comm.foia.email.status == "good"
            and comm.foia.user.is_staff
        ):
            comm.foia.send_email(comm, **kwargs)
        else:
            super().send_msg(comm, **kwargs)

    def get_client(self, comm):
        """Get a GovQA client"""
        return GovQA(
            furl(comm.foia.portal.url).origin,
            comm.foia.get_request_email(),
            comm.foia.portal_password,
        )

    def receive_msg(self, comm, **kwargs):
        """Check for attachments upon receiving a communication"""
        super().receive_msg(comm, **kwargs)
        portal_task.delay(self.portal.pk, "receive_msg_task", [comm.pk], kwargs)

    def receive_msg_task(self, comm_pk, **kwargs):
        """Fetch the request from GovQA"""
        comm = FOIACommunication.objects.get(pk=comm_pk)

        client = self.get_client(comm)
        reqs = client.list_requests()
        if len(reqs) != 1:
            logger.warning(
                "[GOVQA] Communication: %d, list_requests returned %d requests",
                comm_pk,
                len(reqs),
            )
            return
        request = reqs[0]
        status = request["status"]
        logger.info("[GOVQA] Communication: %d Status %s", comm_pk, status)
        request_id = request["id"]
        date = comm.datetime.date()
        request = client.get_request(request_id)
        logger.info("[GOVQA] Communication: %d Request %s", comm_pk, request)
        upload_attachments = [
            a for a in request["attachments"] if a["uploaded_at"] == date
        ]
        logger.info(
            "[GOVQA] Communication: %d Attachments: %s", comm_pk, upload_attachments
        )

        for attachment in upload_attachments:
            value, params = cgi.parse_header(attachment["content-disposition"])
            if value == "attachment" and "filename" in params:
                file_name = params["filename"]
            else:
                logger.warning(
                    "[GOVQA] Communication: %d No file name for attachment: %s",
                    comm_pk,
                    attachment,
                )
                continue

            portal_task.delay(
                self.portal.pk,
                "download_attachment_task",
                [comm.pk, attachment["url"], file_name],
                kwargs,
            )

    def download_attachment_task(self, comm_pk, url, file_name, **kwargs):
        """Download individual attachments"""
        logger.info(
            "[GOVQA] Communication: %d Downloading: %s %s", comm_pk, url, file_name
        )
        comm = FOIACommunication.objects.get(pk=comm_pk)

        # stream the download to not overflow RAM on large files
        with requests.get(url, stream=True) as resp:
            if resp.status_code != 200:
                logger.warning(
                    "[GOVQA] Communication: %d Download failed: %s %s Status: %d "
                    "Error: %s",
                    comm_pk,
                    url,
                    file_name,
                    resp.status_code,
                    resp.text,
                )
                return
            path = get_path(file_name)
            with smart_open(path, "wb") as file:
                for chunk in resp.iter_content(chunk_size=10 * 1024 * 1024):
                    file.write(chunk)

        logger.info(
            "[GOVQA] Communication: %d Download complete: %s %s",
            comm_pk,
            url,
            file_name,
        )
        comm.attach_file(path=path, name=file_name)
