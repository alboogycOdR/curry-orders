from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="password_hash",
            field=models.TextField(blank=True, null=True),
        ),
    ]
