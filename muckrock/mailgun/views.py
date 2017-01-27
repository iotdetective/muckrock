"""
Views for mailgun
"""

from django.conf import settings
from django.core.cache import cache
from django.core.mail import EmailMessage
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt

import hashlib
import hmac
import logging
import os
import re
import sys
import time
from datetime import datetime
from email.utils import parseaddr, getaddresses
from functools import wraps
from localflavor.us.us_states import STATE_CHOICES

from muckrock.agency.models import Agency
from muckrock.foia.models import (
        FOIARequest,
        FOIACommunication,
        FOIAFile,
        RawEmail,
        CommunicationError,
        CommunicationOpen,
        )
from muckrock.foia.tasks import upload_document_cloud, classify_status
from muckrock.mailgun.models import WhitelistDomain
from muckrock.task.models import (
        FailedFaxTask,
        OrphanTask,
        RejectedEmailTask,
        ResponseTask,
        StaleAgencyTask,
        )
from muckrock.utils import new_action

logger = logging.getLogger(__name__)


def _upload_file(foia, comm, file_, sender):
    """Upload a file to attach to a FOIA request"""

    access = 'private' if foia and foia.embargo else 'public'
    source = foia.agency.name if foia and foia.agency else sender

    foia_file = FOIAFile(
            foia=foia,
            comm=comm,
            title=os.path.splitext(file_.name)[0][:70],
            date=datetime.now(),
            source=source[:70],
            access=access)
    # max db size of 255, - 22 for folder name
    foia_file.ffile.save(file_.name[:233].encode('ascii', 'ignore'), file_)
    foia_file.save()
    if foia:
        upload_document_cloud.apply_async(args=[foia_file.pk, False], countdown=3)


def _make_orphan_comm(from_, to_, post, files, foia):
    """Make an orphan communication"""
    from_realname, _ = parseaddr(from_)
    to_ = to_[:255] if to_ else ''
    comm = FOIACommunication.objects.create(
            priv_from_who=from_[:255], from_who=from_realname[:255],
            priv_to_who=to_, response=True,
            date=datetime.now(), full_html=False, delivered='email',
            communication=_get_mail_body(post),
            likely_foia=foia)
    RawEmail.objects.create(
        communication=comm,
        raw_email='%s\n%s' % (post.get('message-headers', ''), post.get('body-plain', '')))
    _process_attachments(files, comm)

    return comm


def _get_mail_body(post):
    """Try to get the stripped-text unless it looks like that parsing failed,
    then get the full plain body"""
    stripped_text = post.get('stripped-text', '')
    bad_text = [
            # if stripped-text is blank or not present
            '',
            '\n',
            # the following are form Seattle's automated system
            # they seem to confuse mailgun's parser
            '--- Please respond above this line ---',
            '--- Please respond above this line ---\n',
            ]
    if stripped_text in bad_text:
        return post.get('body-plain')
    else:
        return '%s\n%s' % (
                post.get('stripped-text', ''),
                post.get('stripped-signature', ''))


def mailgun_verify(function):
    """Decorator to verify mailgun webhooks"""
    @wraps(function)
    def wrapper(request):
        """Wrapper"""
        if _verify(request.POST):
            return function(request)
        else:
            return HttpResponseForbidden()
    return wrapper


def get_common_webhook_params(function):
    """Decorator to handle getting the communication for mailgun webhooks"""
    @wraps(function)
    def wrapper(request):
        """Wrapper"""
        comm_id = request.POST.get('comm_id')
        if comm_id:
            try:
                comm = FOIACommunication.objects.get(pk=comm_id)
                timestamp = request.POST['timestamp']
                timestamp = datetime.fromtimestamp(int(timestamp))
                function(request, comm, timestamp)
            except FOIACommunication.DoesNotExist:
                logger.warning(
                        'Communication does not exist for %s: %s',
                        function.__name__,
                        comm_id)
        else:
            logger.warning('No comm ID for %s webhook', function.__name__)

        return HttpResponse('OK')
    return wrapper


@mailgun_verify
@csrf_exempt
def route_mailgun(request):
    """Handle routing of incoming mail with proper header parsing"""

    post = request.POST
    # The way spam hero is currently set up, all emails are sent to the same
    # address, so we must parse to headers to find the recipient.  This can
    # cause duplicate messages if one email is sent to or CC'd to multiple
    # addresses @request.muckrock.com.  To try and avoid this, we will cache
    # the message id, which should be a unique identifier for the message.
    # If it exists int he cache, we will stop processing this email.  The
    # ID will be cached for 5 minutes - duplicates should normally be processed
    # within seconds of each other.
    message_id = (
            post.get('Message-ID') or
            post.get('Message-Id') or
            post.get('message-id'))
    if message_id:
        # cache.add will return False if the key is already present
        if not cache.add(message_id, 1, 300):
            return HttpResponse('OK')

    p_request_email = re.compile(r'(\d+-\d{3,10})@requests.muckrock.com')
    tos = post.get('To', '') or post.get('to', '')
    ccs = post.get('Cc', '') or post.get('cc', '')
    name_emails = getaddresses([tos.lower(), ccs.lower()])
    logger.info('Incoming email: %s', name_emails)
    for _, email in name_emails:
        m_request_email = p_request_email.match(email)
        if m_request_email:
            _handle_request(request, m_request_email.group(1))
        elif email == 'fax@requests.muckrock.com':
            _fax(request)
        elif email.endswith('@requests.muckrock.com'):
            _catch_all(request, email)
    return HttpResponse('OK')


def _handle_request(request, mail_id):
    """Handle incoming mailgun FOI request messages"""
    # pylint: disable=broad-except
    # pylint: disable=too-many-locals
    post = request.POST
    from_ = post.get('From')
    to_ = post.get('To') or post.get('to')
    subject = post.get('Subject') or post.get('subject', '')

    try:
        from_realname, from_email = parseaddr(from_)
        foia = FOIARequest.objects.get(mail_id=mail_id)

        if not _allowed_email(from_email, foia):
            msg, reason = ('Bad Sender', 'bs')
        if foia.block_incoming:
            msg, reason = ('Incoming Blocked', 'ib')
        if not _allowed_email(from_email, foia) or foia.block_incoming:
            logger.warning('%s: %s', msg, from_)
            comm = _make_orphan_comm(from_, to_, post, request.FILES, foia)
            OrphanTask.objects.create(
                reason=reason,
                communication=comm,
                address=mail_id)
            return HttpResponse('WARNING')

        comm = FOIACommunication.objects.create(
                foia=foia,
                from_who=from_realname[:255],
                priv_from_who=from_[:255],
                to_who=foia.user.get_full_name(),
                priv_to_who=to_[:255],
                subject=subject[:255],
                response=True,
                date=datetime.now(),
                full_html=False,
                delivered='email',
                communication=_get_mail_body(post),
                )
        RawEmail.objects.create(
            communication=comm,
            raw_email='%s\n%s' % (post.get('message-headers', ''), post.get('body-plain', '')))

        _process_attachments(request.FILES, comm)

        task = ResponseTask.objects.create(communication=comm)
        classify_status.apply_async(args=(task.pk,), countdown=30 * 60)
        # resolve any stale agency tasks for this agency
        if foia.agency:
            (StaleAgencyTask.objects
                    .filter(resolved=False, agency=foia.agency)
                    .update(resolved=True))
            foia.agency.stale = False
            foia.agency.save()

        foia.email = from_email
        foia.other_emails = ','.join(
                email for name, email
                in getaddresses([post.get('To', ''), post.get('Cc', '')])
                if email and not email.endswith('muckrock.com'))
        while len(foia.other_emails) > 255:
            # drop emails until it fits in db
            foia.other_emails = foia.other_emails[:foia.other_emails.rindex(',')]

        if foia.status == 'ack':
            foia.status = 'processed'
        foia.save(comment='incoming mail')
        action = new_action(
            foia.agency,
            'sent a communication',
            action_object=comm,
            target=foia)
        foia.notify(action)
        foia.update(comm.anchor())

    except FOIARequest.DoesNotExist:
        logger.warning('Invalid Address: %s', mail_id)
        foia = None
        try:
            # try to get the foia by the PK before the dash
            foia = FOIARequest.objects.get(pk=mail_id.split('-')[0])
        except FOIARequest.DoesNotExist:
            pass
        comm = _make_orphan_comm(from_, to_, post, request.FILES, foia)
        OrphanTask.objects.create(
            reason='ia',
            communication=comm,
            address=mail_id)
        return HttpResponse('WARNING')
    except Exception:
        # If anything I haven't accounted for happens, at the very least forward
        # the email to requests so it isn't lost
        logger.error('Uncaught Mailgun Exception: %s', mail_id, exc_info=sys.exc_info())
        _forward(post, request.FILES, 'Uncaught Mailgun Exception', info=True)
        return HttpResponse('ERROR')

    return HttpResponse('OK')


def _parse_faxaway_email(body, prefixes, addtl_info=False):
    """Parse a faxaway confirmation email"""
    values = {}
    info_list = []
    in_info = False
    for line in body.split('\n'):
        for prefix in prefixes:
            if line.startswith(prefix):
                values[prefix] = line[len(prefix):].strip()
                prefixes.remove(prefix)
        if not prefixes and not addtl_info:
            break
        if addtl_info and line.startswith('Additional Information:'):
            in_info = True
        elif addtl_info and line.startswith('==='):
            # a line of equal signs marks the end of the additonal
            # information, and the end of any data we want to parse
            break
        elif addtl_info and in_info:
            info_list.append(line.strip())
    values['info'] = '\n'.join(info_list)
    return values


def _fax(request):
    """Handle fax confirmations and failures"""

    p_id = re.compile(r'MR#(\d+)-(\d+)')

    post = request.POST
    subject = post.get('subject', '')
    m_id = p_id.search(subject)

    if m_id:
        # pylint: disable=duplicate-except
        try:
            FOIARequest.objects.get(pk=m_id.group(1))
            comm = FOIACommunication.objects.get(pk=m_id.group(2))
        except FOIARequest.DoesNotExist:
            logger.warning('Fax FOIARequest does not exist: %s', m_id.group(1))
        except FOIACommunication.DoesNotExist:
            logger.warning('Fax FOIACommunication does not exist: %s', m_id.group(2))
        else:
            if subject.startswith('CONFIRM:'):
                comm.confirmed = datetime.now()
                comm.save()
            if subject.startswith('FAILURE:'):
                parsed = _parse_faxaway_email(
                        post.get('body-plain', ''),
                        ['REASON:', 'FAX NUMBER:'],
                        addtl_info=True,
                        )
                reason = parsed.get('REASON:', '')
                recipient = parsed.get('FAX NUMBER:', '')
                date = datetime.now()
                error = parsed.get('info', '')
                FailedFaxTask.objects.create(
                        communication=comm,
                        reason=reason,
                        )
                CommunicationError.objects.create(
                        communication=comm,
                        date=date,
                        recipient=recipient,
                        error=error,
                        event='failed fax',
                        reason=reason,
                        )

    _forward(request.POST, request.FILES)
    return HttpResponse('OK')


def _catch_all(request, address):
    """Handle emails sent to other addresses"""

    post = request.POST

    from_ = post.get('From')
    to_ = post.get('To') or post.get('to')
    _, from_email = parseaddr(from_)

    if _allowed_email(from_email):
        comm = _make_orphan_comm(from_, to_, post, request.FILES, None)
        OrphanTask.objects.create(
            reason='ia',
            communication=comm,
            address=address)

    return HttpResponse('OK')


@mailgun_verify
@csrf_exempt
@get_common_webhook_params
def bounces(request, communication, timestamp):
    """Notify when an email is bounced or dropped"""

    foia = communication.foia
    recipient = request.POST.get('recipient', '')
    event = request.POST.get('event', '')
    if event == 'bounced':
        error = request.POST.get('error', '')
    elif event == 'dropped':
        error = request.POST.get('description', '')
    else:
        error = ''

    RejectedEmailTask.objects.create(
            category=event[0],
            foia=foia,
            email=recipient,
            error=error,
            )

    CommunicationError.objects.create(
            communication=communication,
            date=timestamp,
            recipient=recipient,
            code=request.POST.get('code', ''),
            error=error,
            event=event,
            reason=request.POST.get('reason', ''),
            )


@mailgun_verify
@csrf_exempt
@get_common_webhook_params
def opened(request, communication, timestamp):
    """Notify when an email has been opened"""
    CommunicationOpen.objects.create(
            communication=communication,
            date=timestamp,
            recipient=request.POST.get('recipient', ''),
            city=request.POST.get('city', ''),
            region=request.POST.get('region', ''),
            country=request.POST.get('country', ''),
            client_type=request.POST.get('client-type', ''),
            client_name=request.POST.get('client-name', ''),
            client_os=request.POST.get('client-os', ''),
            device_type=request.POST.get('device-type', ''),
            user_agent=request.POST.get('user-agent', '')[:255],
            ip_address=request.POST.get('ip', ''),
            )


@mailgun_verify
@csrf_exempt
@get_common_webhook_params
def delivered(_request, communication, timestamp):
    """Notify when an email has been delivered"""
    communication.confirmed = timestamp
    communication.save()


def _verify(post):
    """Verify that the message is from mailgun"""
    token = post.get('token', '')
    timestamp = post.get('timestamp', '')
    signature = post.get('signature', '')
    signature_ = hmac.new(
            key=settings.MAILGUN_ACCESS_KEY,
            msg='%s%s' % (timestamp, token),
            digestmod=hashlib.sha256,
            ).hexdigest()
    return signature == signature_ and int(timestamp) + 300 > time.time()


def _forward(post, files, title='', extra_content='', info=False):
    """Forward an email from mailgun to admin"""
    if title:
        subject = '%s: %s' % (title, post.get('subject', ''))
    else:
        subject = post.get('subject', '')
    subject = subject.replace('\r', '').replace('\n', '')

    if extra_content:
        body = '%s\n\n%s' % (extra_content, post.get('body-plain'))
    else:
        body = post.get('body-plain')
    if not body:
        body = 'This email intentionally left blank'

    to_addresses = ['requests@muckrock.com']
    if info:
        to_addresses.append('info@muckrock.com')
    email = EmailMessage(subject, body, post.get('From'), to_addresses)
    for file_ in files.itervalues():
        email.attach(file_.name, file_.read(), file_.content_type)

    email.send(fail_silently=False)


def _allowed_email(email, foia=None):
    """Is this an allowed email?"""
    # pylint: disable=too-many-return-statements

    email = email.lower()
    allowed_tlds = ['.%s.us' % a.lower() for (a, _) in STATE_CHOICES
            if a not in ('AS', 'DC', 'GU', 'MP', 'PR', 'VI')]
    allowed_tlds.extend(['.gov', '.mil'])

    # from the same domain as the FOIA email
    if (foia and foia.email and '@' in foia.email and
            email.endswith(foia.email.split('@')[1].lower())):
        return True

    # the email is a known email for this FOIA's agency
    if (foia and foia.agency and email in
            [i.lower() for i in foia.agency.get_other_emails()]):
        return True

    # the email is a known email for this FOIA
    if foia and email in [i.lower() for i in foia.get_other_emails()]:
        return True

    # it is from any known government TLD
    if any(email.endswith(tld) for tld in allowed_tlds):
        return True

    # if not associated with any FOIA,
    # checked if the email is known for any agency
    if not foia and (Agency.objects.filter(email__iexact=email).exists() or
            Agency.objects.filter(other_emails__icontains=email).exists()):
        return True

    # check the email domain against the whitelist
    if '@' in email and WhitelistDomain.objects.filter(
            domain__iexact=email.split('@')[1]).exists():
        return True

    return False


def _process_attachments(files, comm):
    """Process all attachments for the email"""

    ignore_types = [('application/x-pkcs7-signature', 'p7s')]

    for file_ in files.itervalues():
        if not any(file_.content_type == t or file_.name.endswith(s)
                for t, s in ignore_types):
            _upload_file(comm.foia, comm, file_, comm.priv_from_who)
