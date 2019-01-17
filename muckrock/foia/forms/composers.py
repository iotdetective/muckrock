"""
FOIA forms for composing requests
"""

# Django
from django import forms
from django.contrib.auth.models import User

# Third Party
from autocomplete_light import shortcuts as autocomplete_light
from autocomplete_light.contrib.taggit_field import TaggitField
from requests.exceptions import HTTPError

# MuckRock
from muckrock.accounts.forms import BuyRequestForm
from muckrock.accounts.utils import mini_login
from muckrock.agency.models import Agency
from muckrock.core.forms import TaggitWidget
from muckrock.foia.fields import ComposerAgencyField
from muckrock.foia.forms.comms import ContactInfoForm
from muckrock.foia.models import FOIAComposer


class BaseComposerForm(forms.ModelForm):
    """This form creates and updates FOIA composers"""

    title = forms.CharField(
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Add a title',
                'class': 'submit-required',
            }
        ),
        max_length=255,
        required=False,
        help_text='i.e., "John Doe Arrest Report" or "2017 Agency Leadership '
        'Calendars". Agencies may see this on emailed requests.',
    )
    requested_docs = forms.CharField(
        widget=forms.Textarea(
            attrs={
                'placeholder':
                    'Write a short description of the documents you are '
                    'looking for. The more specific you can be, the better.',
                'class': 'submit-required',
            }
        ),
        required=False,
    )
    agencies = ComposerAgencyField(
        queryset=Agency.objects.get_approved(),
        widget=autocomplete_light.
        MultipleChoiceWidget('AgencyComposerAutocomplete'),
        required=False,
        help_text='i.e., Police Department, Austin, TX or Office of the '
        'Governor, Arkansas'
    )
    edited_boilerplate = forms.BooleanField(
        required=False,
        label='Edit Template Language',
    )
    embargo = forms.BooleanField(
        required=False,
        help_text='Embargoing a request keeps it completely private from '
        'other users until the embargo date you set. '
        'You may change this whenever you want.'
    )
    permanent_embargo = forms.BooleanField(required=False)
    tags = TaggitField(
        widget=TaggitWidget(
            'TagAutocomplete',
            attrs={
                'placeholder': 'Search tags',
                'data-autocomplete-minimum-characters': 1
            }
        ),
        help_text='Separate tags with commas.',
        required=False,
    )
    parent = forms.ModelChoiceField(
        queryset=FOIAComposer.objects.none(),
        required=False,
        widget=forms.HiddenInput(),
    )
    action = forms.ChoiceField(
        choices=[
            ('save', 'Save'),
            ('submit', 'Submit'),
            ('delete', 'Delete'),
        ],
        widget=forms.HiddenInput(),
    )

    register_full_name = forms.CharField(
        label='Full Name or Handle (Public)',
        required=False,
    )
    register_email = forms.EmailField(label='Email', required=False)
    register_newsletter = forms.BooleanField(
        initial=True,
        required=False,
        label='Get MuckRock\'s weekly newsletter with '
        'FOIA news, tips, and more',
    )

    login_username = forms.CharField(label='Username', required=False)
    login_password = forms.CharField(
        label='Password', widget=forms.PasswordInput(), required=False
    )

    class Meta:
        model = FOIAComposer
        fields = [
            'title',
            'agencies',
            'requested_docs',
            'edited_boilerplate',
            'embargo',
            'permanent_embargo',
            'tags',
            'parent',
            'register_full_name',
            'register_email',
            'register_newsletter',
        ]

    def __init__(self, *args, **kwargs):
        if not hasattr(self, 'user'):
            self.user = kwargs.pop('user')
        self.request = kwargs.pop('request')
        super(BaseComposerForm, self).__init__(*args, **kwargs)
        if self.user.is_authenticated:
            del self.fields['register_full_name']
            del self.fields['register_email']
            del self.fields['register_newsletter']
            del self.fields['login_username']
            del self.fields['login_password']
        if not self.user.has_perm('foia.embargo_foiarequest'):
            del self.fields['embargo']
        if not self.user.has_perm('foia.embargo_perm_foiarequest'):
            del self.fields['permanent_embargo']
        self.fields['parent'].queryset = (
            FOIAComposer.objects.get_viewable(self.user).distinct()
        )
        self.fields['agencies'].user = self.user
        self.fields['agencies'].queryset = (
            Agency.objects.get_approved_and_pending(self.user)
        )

    def clean_register_email(self):
        """Do a case insensitive uniqueness check"""
        email = self.cleaned_data['register_email']
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                'User with this email already exists. Please login first.'
            )
        return email

    def clean_title(self):
        """Make sure we have a non-blank(ish) title"""
        title = self.cleaned_data['title'].strip()
        if title:
            return title
        else:
            return 'Untitled'

    def clean_agencies(self):
        """Remove exempt agencies"""
        return [a for a in self.cleaned_data['agencies'] if not a.exempt]

    def clean(self):
        """Check cross field dependencies"""
        cleaned_data = super(BaseComposerForm, self).clean()
        if cleaned_data.get('action') == 'submit':
            for field in ['title', 'requested_docs', 'agencies']:
                if not self.cleaned_data.get(field):
                    self.add_error(
                        field,
                        'This field is required when submitting',
                    )
        if cleaned_data.get('permanent_embargo'):
            cleaned_data['embargo'] = True
        if not self.user.is_authenticated:
            register = (
                cleaned_data.get('register_full_name')
                and cleaned_data.get('register_email')
            )
            login = (
                cleaned_data.get('login_username')
                and cleaned_data.get('login_password')
            )
            if not register and not login:
                raise forms.ValidationError(
                    'You must supply either registration information or '
                    'login information'
                )
            if login:
                try:
                    self.user = mini_login(
                        self.request,
                        cleaned_data.get('login_username'),
                        cleaned_data.get('login_password'),
                    )
                except HTTPError:
                    raise forms.ValidationError(
                        'Please enter a correct username and password'
                    )
        return cleaned_data


class ComposerForm(ContactInfoForm, BuyRequestForm, BaseComposerForm):
    """Composer form, including optional subforms"""

    def __init__(self, *args, **kwargs):
        super(ComposerForm, self).__init__(*args, **kwargs)
        # Make sub-form fields non-required
        self.fields['num_requests'].required = False
        self.fields['stripe_token'].required = False

    def clean(self):
        """Buy request fields are only required when buying requests"""
        cleaned_data = super(ComposerForm, self).clean()
        action = cleaned_data.get('action')
        num_requests = cleaned_data.get('num_requests', 0)
        if (
            action == 'submit' and num_requests > 0
            and not self.cleaned_data.get('stripe_token')
        ):
            self.add_error(
                'stripe_token',
                'This field is required when making a purchase',
            )
