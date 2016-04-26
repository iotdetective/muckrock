"""
Provides a base email class for messages.
"""

from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives

class TemplateEmail(EmailMultiAlternatives):
    """
    The TemplateEmail class provides a base for our transactional emails.
    It supports sending a templated email to a user and providing extra template context.
    It always adds the MuckRock diagnostic email as a BCC'd address.
    Both a HTML and a text template should be provided by subclasses.
    Subjects are expected to be provided at initialization, however a subclass may provide
    a static subject attribute if it is provided to the super __init__ method as as kwarg.
    """
    text_template = None
    html_template = None
    user = None

    def __init__(self, user=None, extra_context=None, **kwargs):
        """Sets the universal attributes for all our email."""
        super(TemplateEmail, self).__init__(**kwargs)
        if user:
            if isinstance(user, User):
                self.user = user
                self.to.append(user.email)
            else:
                raise TypeError('"user" argument expects a User type')
        context = self.get_context_data(extra_context)
        content = {
            'text': render_to_string(self.get_text_template(), context),
            'html': render_to_string(self.get_html_template(), context),
        }
        self.bcc = self.bcc.append('diagnostics@muckrock.com')
        self.body = content['text']
        self.attach_alternative(content['html'], 'text/html')

    def get_context_data(self, extra_context):
        """Sets basic context data and allow extra context to be passed in."""
        context = {
            'base_url': 'https://www.muckrock.com',
            'subject': self.subject,
            'user': self.user
        }
        if extra_context:
            if isinstance(extra_context, dict):
                context.update(extra_context)
            else:
                raise TypeError('"extra_context" must be a dictionary')
        return context

    def get_text_template(self):
        """Returns the template specified by the subclass."""
        if text_template is None:
            raise NotImplementedError('A text template must be provided.')

    def get_html_template(self):
        """Returns the template specified by the subclass."""
        if html_template is None:
            raise NotImplementedError('An HTML template must be provided.')
        return html_template
