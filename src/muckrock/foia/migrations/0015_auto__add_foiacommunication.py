# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):

        # Adding model 'FOIACommunication'
        db.create_table('foia_foiacommunication', (
            ('from_who', self.gf('django.db.models.fields.CharField')(max_length=70)),
            ('communication', self.gf('django.db.models.fields.TextField')()),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('date', self.gf('django.db.models.fields.DateField')()),
            ('response', self.gf('django.db.models.fields.BooleanField')(default=False, blank=True)),
            ('foia', self.gf('django.db.models.fields.related.ForeignKey')(related_name='communications', to=orm['foia.FOIARequest'])),
        ))
        db.send_create_signal('foia', ['FOIACommunication'])

        # migrate the data
        def default_date(date):
            if date:
                return date
            else:
                return datetime.datetime.today()

        for foia in orm.FOIARequest.objects.all():
            orm.FOIACommunication.objects.create(foia=foia, from_who='%s %s' % (foia.user.first_name, foia.user.last_name),
                                                 date=default_date(foia.date_submitted), response=False,
                                                 communication=foia.request)
            if foia.response:
                orm.FOIACommunication.objects.create(
                    foia=foia,
                    from_who='%s Department of %s' % (foia.agency_type.name, foia.jurisdiction.name),
                    date=default_date(foia.date_done), response=True,
                    communication=foia.response)


    def backwards(self, orm):

        # Deleting model 'FOIACommunication'
        db.delete_table('foia_foiacommunication')


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'blank': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'foia.agency': {
            'Meta': {'object_name': 'Agency'},
            'address': ('django.db.models.fields.TextField', [], {}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'jurisdiction': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'agencies'", 'to': "orm['foia.Jurisdiction']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '60'}),
            'types': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['foia.AgencyType']", 'symmetrical': 'False'})
        },
        'foia.agencytype': {
            'Meta': {'object_name': 'AgencyType'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '60'})
        },
        'foia.foiacommunication': {
            'Meta': {'object_name': 'FOIACommunication'},
            'communication': ('django.db.models.fields.TextField', [], {}),
            'date': ('django.db.models.fields.DateField', [], {}),
            'foia': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'communications'", 'to': "orm['foia.FOIARequest']"}),
            'from_who': ('django.db.models.fields.CharField', [], {'max_length': '70'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'response': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'})
        },
        'foia.foiadocument': {
            'Meta': {'object_name': 'FOIADocument'},
            'access': ('django.db.models.fields.CharField', [], {'max_length': '12'}),
            'description': ('django.db.models.fields.TextField', [], {}),
            'doc_id': ('django.db.models.fields.SlugField', [], {'max_length': '80', 'db_index': 'True'}),
            'document': ('django.db.models.fields.files.FileField', [], {'max_length': '100'}),
            'foia': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'documents'", 'to': "orm['foia.FOIARequest']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'source': ('django.db.models.fields.CharField', [], {'max_length': '70'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '70'})
        },
        'foia.foiafile': {
            'Meta': {'object_name': 'FOIAFile'},
            'ffile': ('django.db.models.fields.files.FileField', [], {'max_length': '100'}),
            'foia': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'files'", 'to': "orm['foia.FOIARequest']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'foia.foiarequest': {
            'Meta': {'object_name': 'FOIARequest'},
            'agency_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['foia.AgencyType']"}),
            'date_done': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'date_due': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'date_submitted': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'embargo': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'jurisdiction': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['foia.Jurisdiction']"}),
            'request': ('django.db.models.fields.TextField', [], {}),
            'response': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '70', 'db_index': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '70'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'foia.jurisdiction': {
            'Meta': {'object_name': 'Jurisdiction'},
            'abbrev': ('django.db.models.fields.CharField', [], {'max_length': '5', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'level': ('django.db.models.fields.CharField', [], {'max_length': '1'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'children'", 'null': 'True', 'to': "orm['foia.Jurisdiction']"}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '55', 'db_index': 'True'})
        }
    }
    
    complete_apps = ['foia']
