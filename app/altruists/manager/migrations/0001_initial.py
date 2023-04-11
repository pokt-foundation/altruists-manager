# Generated by Django 4.1.7 on 2023-02-20 03:38

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Chain',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chain_id', models.CharField(max_length=4, unique=True)),
                ('chain_name', models.CharField(max_length=200)),
            ],
        ),
        migrations.CreateModel(
            name='Altruist',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('url', models.CharField(max_length=200, unique=True)),
                ('enabled', models.BooleanField(default=False)),
                ('chain_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='manager.chain')),
            ],
        ),
    ]
