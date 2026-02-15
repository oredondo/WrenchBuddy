from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0003_eventattachment'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventattachment',
            name='analysis_status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pendiente'),
                    ('processing', 'Procesando'),
                    ('completed', 'Completado'),
                    ('failed', 'Fallido'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='eventattachment',
            name='analysis_result',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='eventattachment',
            name='analysis_error',
            field=models.TextField(blank=True, null=True),
        ),
    ]
