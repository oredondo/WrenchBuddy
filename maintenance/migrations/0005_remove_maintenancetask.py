from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0004_eventattachment_analysis_fields'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='maintenanceevent',
            name='created_from_task',
        ),
        migrations.DeleteModel(
            name='MaintenanceTask',
        ),
    ]
