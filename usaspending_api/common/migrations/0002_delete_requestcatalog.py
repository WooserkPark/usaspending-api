# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-12-05 21:39
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0001_initial'),
    ]

    operations = [
        migrations.DeleteModel(
            name='RequestCatalog',
        ),
    ]
