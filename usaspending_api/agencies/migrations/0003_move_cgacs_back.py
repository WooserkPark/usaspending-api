# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2019-08-29 12:32
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('agencies', '0002_auto_20190917_1750'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=None,
            state_operations=[
                migrations.DeleteModel(
                    name='CGAC',
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=None,
            state_operations=[
                migrations.DeleteModel(
                    name='FREC',
                ),
            ],
        ),
    ]
