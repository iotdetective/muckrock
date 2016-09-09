"""
Tests for Jurisdiction application
"""

from django.core.urlresolvers import reverse
from django.test import TestCase

from datetime import date, timedelta
from nose.tools import eq_

from muckrock.jurisdiction import factories
from muckrock.factories import FOIARequestFactory, FOIACommunicationFactory, FOIAFileFactory

class TestJurisdictionUnit(TestCase):
    """Unit tests for Jurisdictions"""
    def setUp(self):
        """Set up tests"""
        self.federal = factories.FederalJurisdictionFactory()
        self.state = factories.StateJurisdictionFactory(parent=self.federal)
        self.local = factories.LocalJurisdictionFactory(parent=self.state)

    def test_repr(self):
        """Test Jurisdiction model's __repr__ method"""
        pattern = '<Jurisdiction: %d>'
        eq_(self.federal.__repr__(), pattern % self.federal.pk)
        eq_(self.state.__repr__(), pattern % self.state.pk)
        eq_(self.local.__repr__(), pattern % self.local.pk)

    def test_unicode(self):
        """Test Jurisdiction model's __unicode__ method"""
        eq_(unicode(self.federal), u'United States of America')
        eq_(unicode(self.state), u'Massachusetts')
        eq_(unicode(self.local), u'Boston, MA')
        self.local.full_name = u'Test!'
        self.local.save()
        eq_(unicode(self.local), u'Test!',
            'If the locality has a hardcoded full_name, then always prefer that.')

    def test_jurisdiction_url(self):
        """Test Jurisdiction model's get_absolute_url method"""
        eq_(self.local.get_absolute_url(),
            reverse('jurisdiction-detail', kwargs={
                'local_slug': self.local.slug,
                'state_slug': self.state.slug,
                'fed_slug': self.federal.slug}
            )
        )
        eq_(self.state.get_absolute_url(),
            reverse('jurisdiction-detail', kwargs={
                'state_slug': self.state.slug,
                'fed_slug': self.federal.slug}
            )
        )
        eq_(self.federal.get_absolute_url(),
            reverse('jurisdiction-detail', kwargs={
                'fed_slug': self.federal.slug}
            )
        )

    def test_jurisdiction_legal(self):
        """Local jurisdictions should return state law"""
        eq_(self.federal.legal(), self.federal.abbrev)
        eq_(self.state.legal(), self.state.abbrev)
        eq_(self.local.legal(), self.state.abbrev)
        eq_(self.federal.get_law_name(), self.federal.law_name)
        eq_(self.state.get_law_name(), self.state.law_name)
        eq_(self.local.get_law_name(), self.state.law_name)

    def test_get_day_type(self):
        """Local jurisdictions should return state day type"""
        eq_(self.federal.get_day_type(), 'business')
        eq_(self.state.get_day_type(), 'business')
        eq_(self.local.get_day_type(), 'business')

    def test_jurisdiction_get_days(self):
        """Local jurisdictions should return state days"""
        eq_(self.federal.get_days(), self.federal.days)
        eq_(self.state.get_days(), self.state.days)
        eq_(self.local.get_days(), self.state.days)

    def test_jurisdiction_get_intro(self):
        """Local jurisdictions should return the state intro."""
        eq_(self.federal.get_intro(), self.federal.intro)
        eq_(self.state.get_intro(), self.state.intro)
        eq_(self.local.get_intro(), self.state.intro)

    def test_jurisdiction_get_waiver(self):
        """Local jurisdictions should return the state waiver."""
        eq_(self.federal.get_waiver(), self.federal.waiver)
        eq_(self.state.get_waiver(), self.state.waiver)
        eq_(self.local.get_waiver(), self.state.waiver)

    def test_jurisdiction_can_appeal(self):
        """Local jurisdictions should return the state's appealability."""
        eq_(self.federal.can_appeal(), self.federal.has_appeal)
        eq_(self.state.can_appeal(), self.state.has_appeal)
        eq_(self.local.can_appeal(), self.state.has_appeal)

    def test_get_state(self):
        """Local jurisdictions should return the state's name."""
        eq_(self.federal.get_state(), self.federal.name)
        eq_(self.state.get_state(), self.state.name)
        eq_(self.local.get_state(), self.state.name)

    def test_average_response_time(self):
        """
        Jurisdictions should report their average response time.
        State jurisdictions should include avg. response time of their local jurisdictions.
        """
        today = date.today()
        state_duration = 12
        local_duration = 6
        FOIARequestFactory(
            jurisdiction=self.state,
            date_done=today,
            date_submitted=today-timedelta(state_duration)
        )
        FOIARequestFactory(
            jurisdiction=self.local,
            date_done=today,
            date_submitted=today-timedelta(local_duration)
        )
        eq_(self.state.average_response_time(), (local_duration + state_duration)/2)
        eq_(self.local.average_response_time(), local_duration)

    def test_success_rate(self):
        """
        Jurisdictions should report their success rate: completed/filed.
        State jurisdictions should include success rates of local jurisdictions.
        """
        today = date.today()
        FOIARequestFactory(
            jurisdiction=self.state,
            status='done',
            date_done=today
        )
        FOIARequestFactory(
            jurisdiction=self.local,
            status='ack'
        )
        eq_(self.state.success_rate(), 50.0)
        eq_(self.local.success_rate(), 0.0)

    def test_fee_rate(self):
        """
        Jurisdictions should report the rate at which requests have fees.
        State jurisdictions should include fee rates of local jurisdictions.
        """
        FOIARequestFactory(
            jurisdiction=self.state,
            status='ack',
            price=0
        )
        FOIARequestFactory(
            jurisdiction=self.local,
            status='ack',
            price=1.00
        )
        eq_(self.state.fee_rate(), 50.0)
        eq_(self.local.fee_rate(), 100.0)

    def test_total_pages(self):
        """
        Jurisdictions should report the pages returned across their requests.
        State jurisdictions should include pages from their local jurisdictions.
        """
        page_count = 10
        local_foia = FOIARequestFactory(jurisdiction=self.local)
        state_foia = FOIARequestFactory(jurisdiction=self.state)
        local_foia.files.add(FOIAFileFactory(pages=page_count))
        state_foia.files.add(FOIAFileFactory(pages=page_count))
        eq_(self.local.total_pages(), page_count)
        eq_(self.state.total_pages(), 2*page_count)


class TestLawModel(TestCase):
    """
    The Law model contains information about a jurisdiction's law concerning public records.
    It should contain outside references to information on the law.
    """
    def setUp(self):
        self.law = factories.LawFactory()

    def test_unicode(self):
        """The text representation of the law should be the name of the law."""
        eq_(unicode(self.law), self.law.name,
            'The text representation of the law should match the name of the law.')

    def test_absolute_url(self):
        """The absolute url of the law should be the url of its jurisdiction."""
        eq_(self.law.get_absolute_url(), self.law.jurisdiction.get_absolute_url(),
            'The absolute url of the law should match the url of its jurisdicition.')


class TestExemptionModel(TestCase):
    """
    The Exemption model should contain information about a single kind of exemption.
    For example, the Public Employment Applications for Washtington state.
    """
    def setUp(self):
        self.exemption = factories.ExemptionFactory()

    def test_unicode(self):
        """The text representation should be the name of the exemption and its jurisdiction."""
        eq_(unicode(self.exemption),
            u'%s exemption of %s' % (self.exemption.name, self.exemption.jurisdiction),
            'Should include the name of the exemption and the name of the jurisdiction.')

    def test_absolute_url(self):
        """The absolute url of the exemption should be a standalone exemption detail page."""
        kwargs = self.exemption.jurisdiction.get_slugs()
        kwargs['slug'] = self.exemption.slug
        kwargs['pk'] = self.exemption.pk
        expected_url = reverse('exemption-detail', kwargs=kwargs)
        actual_url = self.exemption.get_absolute_url()
        eq_(actual_url, expected_url, ('The exemption should return the exemption-detail url.\n'
             'Actual url: %s\nExpected url: %s') % (actual_url, expected_url))


class TestInvokedExemptionModel(TestCase):
    """
    The InvokedExemption model should contain information about a single invocation
    of an exemption. For example, when an agency in Washington state uses the
    Public Employment Applications exemption to withhold records from a request.
    """
    def setUp(self):
        self.invoked_exemption = factories.InvokedExemptionFactory()

    def test_unicode(self):
        """The text representation should be the names of the exemption and the request."""
        actual = unicode(self.invoked_exemption)
        expected = u'%s exemption of %s' % (
            self.invoked_exemption.exemption.name,
            self.invoked_exemption.request,
        )
        eq_(actual,
            expected,
            ('Should include the name of the exemption and the request.\n'
            'Actual: %s\nExpected: %s' % (actual, expected)))

    def test_absolute_url(self):
        """The absolute url of the invoked exemption should be the absolute url of the
        exemption with the invokation pk appended as a target."""
        exemption = self.invoked_exemption.exemption
        kwargs = exemption.jurisdiction.get_slugs()
        kwargs['slug'] = exemption.slug
        kwargs['pk'] = exemption.pk
        expected_url = (reverse('exemption-detail', kwargs=kwargs) +
                        '#invoked-%d' % self.invoked_exemption.pk)
        actual_url = self.invoked_exemption.get_absolute_url()
        eq_(actual_url,
            expected_url,
            ('The exemption should return the exemption-detail url.\n'
             'Actual url: %s\nExpected url: %s') % (actual_url, expected_url))


class TestExampleAppealModel(TestCase):
    """
    The ExampleAppeal model should contain sample language for appealing an exemption.
    Additionally, it should contain the context in which this language is most effective.
    """
    def setUp(self):
        self.example_appeal = factories.ExampleAppealFactory()

    def test_unicode(self):
        """The text representation should be the appeal's context and exemption."""
        actual = unicode(self.example_appeal)
        expected = u'%s for %s' % (self.example_appeal.context, self.example_appeal.exemption)
        eq_(actual,
            expected,
            ('Should include the name of the exemption and the request.\n'
            'Actual: %s\nExpected: %s' % (actual, expected)))

    def test_absolute_url(self):
        """The absolute url of the appeal language should be the absolute url of the exemption
        with the appeal pk appeneded as a target."""
        exemption = self.example_appeal.exemption
        kwargs = exemption.jurisdiction.get_slugs()
        kwargs['slug'] = exemption.slug
        kwargs['pk'] = exemption.pk
        expected_url = (reverse('exemption-detail', kwargs=kwargs) +
                        '#appeal-%d' % self.example_appeal.pk)
        actual_url = self.example_appeal.get_absolute_url()
        eq_(actual_url,
            expected_url,
            ('The exemption should return the exemption-detail url.\n'
             'Actual url: %s\nExpected url: %s') % (actual_url, expected_url))


class TestAppealModel(TestCase):
    """
    The Appeal model is used to track information about appeals when they are filed.
    An appeal should be able to judge whether or not it was successful.
    It should do this by analyzing the request's communication chain
    following the communication it corresponds to.
    """
    def setUp(self):
        self.appeal = factories.AppealFactory()

    def test_unicode(self):
        """The text representation should say which request the appeal is of."""
        actual = unicode(self.appeal)
        expected = u'Appeal of %s' % self.appeal.communication.foia
        eq_(actual, expected)

    def test_absolute_url(self):
        """The absolute url for the appeal should be the absolute url of the communication."""
        expected = self.appeal.communication.get_absolute_url()
        actual = self.appeal.get_absolute_url()
        eq_(expected, actual)

    def test_unsuccessful_by_default(self):
        """By default, an appeal should be not be successful."""
        eq_(self.appeal.is_successful(), False)

    def test_successful(self):
        """The appeal was successful if a subsequent communication has a 'Completed' status."""
        subsequent_communication = FOIACommunicationFactory(
            foia=self.appeal.communication.foia,
            status='done'
        )
        eq_(self.appeal.is_successful(), True)

    def test_another_appeal(self):
        """The appeal was unsuccessful if a subsequent communication has an Appeal as well."""
        subsequent_communication = FOIACommunicationFactory(
            foia=self.appeal.communication.foia,
            status='done'
        )
        subsequent_appeal = factories.AppealFactory(communication=subsequent_communication)
        eq_(self.appeal.is_successful(), False)

