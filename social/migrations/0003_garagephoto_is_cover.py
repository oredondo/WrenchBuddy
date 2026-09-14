from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('social', '0002_social_fase2'),
    ]

    operations = [
        migrations.AddField(
            model_name='garagephoto',
            name='is_cover',
            field=models.BooleanField(default=False),
        ),
    ]
