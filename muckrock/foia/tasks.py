"""Celery Tasks for the FOIA application"""

from celery.signals import task_failure
from celery.schedules import crontab
from celery.task import periodic_task, task
from django.core import management
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.template.loader import render_to_string
from muckrock.settings import DOCUMNETCLOUD_USERNAME, DOCUMENTCLOUD_PASSWORD, \
                     GA_USERNAME, GA_PASSWORD, GA_ID, \
                     AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_AUTOIMPORT_BUCKET_NAME


import dbsettings
import base64
import gdata.analytics.service
import json
import logging
import os.path
import re
import urllib2
from boto.s3.connection import S3Connection
from datetime import date, datetime, timedelta
from decimal import Decimal
from muckrock.vendor import MultipartPostHandler

from muckrock.foia.models import FOIAFile, FOIARequest, FOIACommunication
from muckrock.foia.codes import CODES

foia_url = r'(?P<jurisdiction>[\w\d_-]+)-(?P<jidx>\d+)/(?P<slug>[\w\d_-]+)-(?P<idx>\d+)'

logger = logging.getLogger(__name__)

class FOIAOptions(dbsettings.Group):
    """DB settings for the FOIA app"""
    enable_followup = dbsettings.BooleanValue('whether to send automated followups or not')
options = FOIAOptions()

@task(ignore_result=True, max_retries=3, name='muckrock.foia.tasks.upload_document_cloud')
def upload_document_cloud(doc_pk, change, **kwargs):
    """Upload a document to Document Cloud"""

    try:
        doc = FOIAFile.objects.get(pk=doc_pk)
    except FOIAFile.DoesNotExist, exc:
        # pylint: disable=E1101
        # give database time to sync
        upload_document_cloud.retry(countdown=300, args=[doc_pk, change], kwargs=kwargs, exc=exc)

    if not doc.is_doccloud():
        # not a file doc cloud supports, do not attempt to upload
        return

    if doc.doc_id and not change:
        # not change means we are uploading a new one - it should not have an id yet
        return

    if not doc.doc_id and change:
        # if we are changing it must have an id - this should never happen but it is!
        logger.warn('Upload Doc Cloud: Changing without a doc id: %s', doc.pk)
        return

    # these need to be encoded -> unicode to regular byte strings
    params = {
        'title': doc.title.encode('utf8'),
        'source': doc.source.encode('utf8'),
        'description': doc.description.encode('utf8'),
        'access': doc.access.encode('utf8'),
        'related_article': ('https://www.muckrock.com' + 
                            doc.get_foia().get_absolute_url()).encode('utf8'),
        }
    if change:
        params['_method'] = str('put')
        url = '/documents/%s.json' % doc.doc_id
    else:
        params['file'] = doc.ffile.url.replace('https', 'http', 1)
        url = '/upload.json'

    opener = urllib2.build_opener(MultipartPostHandler.MultipartPostHandler)
    request = urllib2.Request('https://www.documentcloud.org/api/%s' % url, params)
    # This is just standard username/password encoding
    auth = base64.encodestring('%s:%s' % (DOCUMNETCLOUD_USERNAME, DOCUMENTCLOUD_PASSWORD))[:-1]
    request.add_header('Authorization', 'Basic %s' % auth)

    try:
        ret = opener.open(request).read()
        if not change:
        # pylint: disable=E1101
            info = json.loads(ret)
            doc.doc_id = info['id']
            doc.save()
            set_document_cloud_pages.apply_async(args=[doc.pk], countdown=1800)
    except (urllib2.URLError, urllib2.HTTPError) as exc:
        # pylint: disable=E1101
        logger.warn('Upload Doc Cloud error: %s %s', url, doc.pk)
        upload_document_cloud.retry(args=[doc.pk, change], kwargs=kwargs, exc=exc)


@task(ignore_result=True, max_retries=10, name='muckrock.foia.tasks.set_document_cloud_pages')
def set_document_cloud_pages(doc_pk, **kwargs):
    """Get the number of pages from the document cloud server and save it locally"""

    doc = FOIAFile.objects.get(pk=doc_pk)

    if doc.pages or not doc.is_doccloud():
        # already has pages set or not a doc cloud, just return
        return

    request = urllib2.Request('https://www.documentcloud.org/api/documents/%s.json' % doc.doc_id)
    # This is just standard username/password encoding
    auth = base64.encodestring('%s:%s' % (DOCUMNETCLOUD_USERNAME, DOCUMENTCLOUD_PASSWORD))[:-1]
    request.add_header('Authorization', 'Basic %s' % auth)

    try:
        ret = urllib2.urlopen(request).read()
        info = json.loads(ret)
        doc.pages = info['document']['pages']
        doc.save()
    except urllib2.URLError, exc:
        # pylint: disable=E1101
        set_document_cloud_pages.retry(args=[doc.pk], countdown=600, kwargs=kwargs, exc=exc)


@periodic_task(run_every=crontab(hour=1, minute=10), name='muckrock.foia.tasks.set_top_viewed_reqs')
def set_top_viewed_reqs():
    """Get the top 5 most viewed requests from Google Analytics and save them locally"""

    client = gdata.analytics.service.AnalyticsDataService()
    client.ssl = True
    client.ClientLogin(GA_USERNAME, GA_PASSWORD)
    data = client.GetData(ids=GA_ID, dimensions='ga:pagePath', metrics='ga:pageviews',
                          start_date=(date.today() - timedelta(days=30)).isoformat(),
                          end_date=date.today().isoformat(), sort='-ga:pageviews')
    path_re = re.compile('ga:pagePath=/foi/%s/' % foia_url)
    top_req_paths = [(entry.title.text, int(entry.pageviews.value)) for entry in data.entry
                     if path_re.match(entry.title.text)]

    for req_path, page_views in top_req_paths:
        try:
            req = FOIARequest.objects.get(pk=path_re.match(req_path).group('idx'))
            req.times_viewed = page_views
            req.save()
        except FOIARequest.DoesNotExist:
            pass


@periodic_task(run_every=crontab(hour=1, minute=0), name='muckrock.foia.tasks.update_index')
def update_index():
    """Update the search index every day at 1AM"""
    management.call_command('update_index')


@periodic_task(run_every=crontab(hour=5, minute=0), name='muckrock.foia.tasks.followup_requests')
def followup_requests():
    """Follow up on any requests that need following up on"""
    # change to this after all follows up have been resolved
    #for foia in FOIARequest.objects.get_followup(): 
    logger.info('foia.tasks.followup_requests task being run')
    if options.enable_followup:
        logger.info('%d requests to follow up on',
            FOIARequest.objects.filter(status='processed', date_followup__lte=date.today()).count())
        for foia in FOIARequest.objects.filter(status='processed', date_followup__lte=date.today()):
            foia.followup()


@periodic_task(run_every=crontab(hour=6, minute=0), name='muckrock.foia.tasks.embargo_warn')
def embargo_warn():
    """Warn users their requests are about to come off of embargo"""
    for foia in FOIARequest.objects.filter(embargo=True,
                                           date_embargo=date.today()+timedelta(1)):
        send_mail('[MuckRock] Embargo about to expire for FOI Request "%s"' % foia.title,
                  render_to_string('foia/embargo.txt', {'request': foia}),
                  'info@muckrock.com', [foia.user.email])


@periodic_task(run_every=crontab(hour=0, minute=0),
               name='muckrock.foia.tasks.set_all_document_cloud_pages')
def set_all_document_cloud_pages():
    """Try and set all document cloud documents that have no page count set"""
    # pylint: disable=E1101
    docs = [doc for doc in FOIAFile.objects.filter(pages=0) if doc.is_doccloud()]
    logger.info('Setting document cloud pages, %d documents with 0 pages', len(docs))
    for doc in docs:
        set_document_cloud_pages.apply_async(args=[doc.pk])


@periodic_task(run_every=crontab(hour=0, minute=20),
               name='muckrock.foia.tasks.retry_stuck_documents')
def retry_stuck_documents():
    """Reupload all document cloud documents which are stuck"""
    # pylint: disable=E1101
    docs = [doc for doc in FOIAFile.objects.filter(doc_id='') if doc.is_doccloud()]
    logger.info('Reupload documents, %d documents are stuck', len(docs))
    for doc in docs:
        upload_document_cloud.apply_async(args=[doc.pk, False])

class SizeError(Exception):
    """Uploaded file is not the correct size"""

@periodic_task(run_every=crontab(hour=2, minute=0), name='muckrock.foia.tasks.autoimport')
def autoimport():
    """Auto import documents from S3"""
    # pylint: disable=R0914
    # pylint: disable=R0912
    p_name = re.compile(r'(?P<month>\d\d?)-(?P<day>\d\d?)-(?P<year>\d\d) '
                        r'(?P<docs>(?:mr\d+ )+)(?P<code>[a-z-]+)(?:\$(?P<arg>\S+))?'
                        r'(?: ID#(?P<id>\S+))?', re.I)
    log = ['Start Time: %s' % datetime.now()]

    def s3_copy(bucket, key_or_pre, dest_name):
        """Copy an s3 key or prefix"""

        if key_or_pre.name.endswith('/'):
            for key in bucket.list(prefix=key_or_pre.name, delimiter='/'):
                if key.name == key_or_pre.name:
                    key.copy(bucket, dest_name)
                    continue
                s3_copy(bucket, key, '%s/%s' %
                    (dest_name, os.path.basename(os.path.normpath(key.name))))
        else:
            key_or_pre.copy(bucket, dest_name)

    def s3_delete(bucket, key_or_pre):
        """Delete an s3 key or prefix"""

        if key_or_pre.name.endswith('/'):
            for key in bucket.list(prefix=key_or_pre.name, delimiter='/'):
                if key.name == key_or_pre.name:
                    key.delete()
                    continue
                s3_delete(bucket, key)
        else:
            key_or_pre.delete()

    def parse_name(name):
        """Parse a file name"""
        # strip off trailing / and file extension
        name = os.path.normpath(name)
        name = os.path.splitext(name)[0]

        m_name = p_name.match(name)
        if not m_name:
            raise ValueError('ERROR: %s does not match the file name format' % name)
        code = m_name.group('code').upper()
        if code not in CODES:
            raise ValueError('ERROR: %s uses an unknown code' % name)
        foia_pks = [pk[2:] for pk in m_name.group('docs').split()]
        file_date = datetime(int(m_name.group('year')) + 2000,
                             int(m_name.group('month')),
                             int(m_name.group('day')))
        title, status, body = CODES[code]
        arg = m_name.group('arg')
        id_ = m_name.group('id')

        return foia_pks, file_date, code, title, status, body, arg, id_

    def import_key(key, comm, log, title=None):
        """Import a key"""
        # pylint: disable=E1101

        foia = comm.foia
        file_name = os.path.split(key.name)[1]

        title = title or file_name
        access = 'private' if foia.is_embargo() else 'public'

        foia_file = FOIAFile(foia=foia, comm=comm, title=title, date=comm.date,
                             source=comm.from_who[:70], access=access)

        con_file = ContentFile(key.get_contents_as_string())
        foia_file.ffile.save(file_name, con_file)
        con_file.close()
        foia_file.save()
        if key.size != foia_file.ffile.size:
            raise SizeError(key.size, foia_file.ffile.size, foia_file)

        log.append('SUCCESS: %s uploaded to FOIA Request %s with a status of %s' %
                   (file_name, foia.pk, foia.status))

        upload_document_cloud.apply_async(args=[foia_file.pk, False], countdown=3)

    def import_prefix(prefix, bucket, comm, log):
        """Import a prefix (folder) full of documents"""

        for key in bucket.list(prefix=prefix.name, delimiter='/'):
            if key.name == prefix.name:
                continue
            try:
                import_key(key, comm, log)
            except SizeError as exc:
                s3_copy(bucket, key, 'review/%s' % key.name[6:])
                exc.args[2].delete() # delete the foia file
                comm.delete()
                log.append('ERROR: %s was %s bytes and after uploaded was %s bytes - retry' %
                           (key.name[6:], exc.args[0], exc.args[1]))

    conn = S3Connection(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    bucket = conn.get_bucket(AWS_AUTOIMPORT_BUCKET_NAME)
    for key in bucket.list(prefix='scans/', delimiter='/'):
        if key.name == 'scans/':
            continue
        # strip off 'scans/'
        file_name = key.name[6:]

        try:
            foia_pks, file_date, code, title, status, body, arg, id_ = parse_name(file_name)
        except ValueError as exc:
            s3_copy(bucket, key, 'review/%s' % file_name)
            s3_delete(bucket, key)
            log.append(unicode(exc))
            continue

        for foia_pk in foia_pks:
            try:
                # pylint: disable=E1101
                foia = FOIARequest.objects.get(pk=foia_pk)
                source = foia.agency.name if foia.agency else ''

                comm = FOIACommunication.objects.create(
                        foia=foia, from_who=source,
                        to_who=foia.user.get_full_name(), response=True,
                        date=file_date, full_html=False,
                        communication=body, status=status)

                foia.status = status or foia.status
                if code == 'FEE' and arg:
                    foia.price = Decimal(arg)
                if id_:
                    foia.tracking_id = id_

                if key.name.endswith('/'):
                    import_prefix(key, bucket, comm, log)
                else:
                    import_key(key, comm, log, title=title)

                foia.save()
                foia.update(comm.anchor())

            except FOIARequest.DoesNotExist:
                s3_copy(bucket, key, 'review/%s' % file_name)
                log.append('ERROR: %s references FOIA Request %s, but it does not exist' %
                           (file_name, foia_pk))
            except Exception as exc:
                s3_copy(bucket, key, 'review/%s' % file_name)
                log.append('ERROR: %s has caused an unknown error. %s' % (file_name, exc))
        # delete key after processing all requests for it
        s3_delete(bucket, key)
    log.append('End Time: %s' % datetime.now())
    log_msg = '\n'.join(log)
    send_mail('[AUTOIMPORT] %s Logs' % datetime.now(), log_msg, 'info@muckrock.com',
              ['requests@muckrock.com'], fail_silently=False)


@periodic_task(run_every=crontab(hour=3, minute=0), name='muckrock.foia.tasks.notify_unanswered')
def notify_unanswered():
    """Notify admins of highly overdue requests"""
    foias = FOIARequest.objects.get_overdue().order_by('date_submitted')
    data = []

    for foia in foias:
        comms = foia.communications.filter(response=True).order_by('-date')
        if comms:
            days_since_response = (datetime.now() - comms[0].date).days
        else:
            # no response ever, set large days late
            days_since_response = 9999
        if days_since_response > 60:
            data.append((days_since_response, foia))

    total = len(data)

    send_mail('[UNANSWERED REQUESTS] %s' % datetime.now(),
              render_to_string('foia/unanswered.txt', {'total': total, 'foias': data[:20]}),
              'info@muckrock.com', ['requests@muckrock.com'], fail_silently=False)
    

def process_failure_signal(exception, traceback, sender, task_id,
                           signal, args, kwargs, einfo, **kw):
    """Log celery exceptions to sentry"""
    # http://www.colinhowe.co.uk/2011/02/08/celery-and-sentry-recording-errors/
    # pylint: disable=R0913
    # pylint: disable=W0613
    exc_info = (type(exception), exception, traceback)
    logger.error(
        'Celery job exception: %s(%s)' % (exception.__class__.__name__, exception),
        exc_info=exc_info,
        extra={
            'data': {
                'task_id': task_id,
                'sender': sender,
                'args': args,
                'kwargs': kwargs,
            }
        }
    )
task_failure.connect(process_failure_signal, dispatch_uid='muckrock.foia.tasks.logging')
