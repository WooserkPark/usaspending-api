# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2019-10-30 17:31
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_tasautocompletematview_tassearchmatview'),
    ]

    operations = [
        migrations.AddField(
            model_name='treasuryappropriationaccount',
            name='internal_end_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='treasuryappropriationaccount',
            name='internal_start_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]