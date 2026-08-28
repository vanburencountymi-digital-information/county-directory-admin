from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("people", "0001_initial"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="person",
            name="uq_people_person_key",
        ),
        migrations.RemoveIndex(
            model_name="person",
            name="people_pers_tenant__985d34_idx",
        ),
        migrations.RemoveField(
            model_name="person",
            name="full_name",
        ),
        migrations.RemoveField(
            model_name="person",
            name="job_title",
        ),
        migrations.RemoveField(
            model_name="person",
            name="person_key",
        ),
        migrations.RemoveField(
            model_name="person",
            name="role",
        ),
        migrations.AddField(
            model_name="person",
            name="display_name",
            field=models.TextField(blank=True, null=True),
        ),
    ]
