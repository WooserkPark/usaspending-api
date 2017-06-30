# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-06-23 15:35
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('references', '0011_filterhash'),
    ]

    operations = [
        migrations.CreateModel(
            name='OverallTotals',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('create_date', models.DateTimeField(auto_now_add=True, null=True)),
                ('update_date', models.DateTimeField(auto_now=True, null=True)),
                ('fiscal_year', models.IntegerField(blank=True, null=True)),
                ('total_budget_authority', models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True)),
            ],
            options={
                'db_table': 'overall_totals',
                'managed': True,
            },
        ),
    ]
