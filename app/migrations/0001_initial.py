# Generated by Django 4.0.6 on 2024-03-11 09:54

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Person',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tg_id', models.CharField(max_length=254)),
                ('tg_username', models.CharField(max_length=254)),
                ('tg_fullname', models.CharField(max_length=254)),
                ('arrived_at', models.DateTimeField(blank=True, default=None, null=True)),
                ('left_at', models.DateTimeField(blank=True, default=None, null=True)),
            ],
        ),
    ]
