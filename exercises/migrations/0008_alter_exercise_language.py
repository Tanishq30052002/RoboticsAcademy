# Generated by Django 3.2.4 on 2021-06-11 13:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exercises', '0007_alter_exercise_language'),
    ]

    operations = [
        migrations.AlterField(
            model_name='exercise',
            name='language',
            field=models.CharField(choices=[('javascript', 'JavaScript'), ('python', 'Python'), ('scratch', 'Scratch')], max_length=40),
        ),
    ]
