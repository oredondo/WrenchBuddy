from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0005_remove_maintenancetask'),
        ('vehicles', '0001_initial'),
    ]

    operations = [
        migrations.DeleteModel(
            name='TaskCatalog',
        ),
        migrations.CreateModel(
            name='TaskCatalog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('vehicle', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='task_catalog',
                    to='vehicles.vehicle',
                )),
                ('task_code', models.CharField(max_length=50)),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
                ('interval_km', models.PositiveIntegerField(blank=True, null=True)),
                ('interval_months', models.PositiveIntegerField(blank=True, null=True)),
                ('is_safety_critical', models.BooleanField(default=False)),
                ('source', models.CharField(
                    choices=[('ai_generated', 'IA'), ('user_created', 'Usuario')],
                    default='ai_generated',
                    max_length=20,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Tarea de catálogo',
                'verbose_name_plural': 'Catálogo de tareas',
                'db_table': 'task_catalog',
            },
        ),
        migrations.AlterUniqueTogether(
            name='taskcatalog',
            unique_together={('vehicle', 'task_code')},
        ),
    ]
