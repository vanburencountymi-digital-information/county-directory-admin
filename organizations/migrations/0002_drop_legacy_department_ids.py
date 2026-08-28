from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="organization",
            name="department_id",
        ),
        migrations.RemoveField(
            model_name="organization",
            name="parent_department_id",
        ),
    ]
