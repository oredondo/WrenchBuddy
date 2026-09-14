import django.db.models.deletion
from django.db import migrations, models
from pgvector.django import VectorExtension, VectorField


class Migration(migrations.Migration):

    dependencies = [
        ('vehicles', '0002_vehicledocument'),
    ]

    operations = [
        VectorExtension(),
        migrations.CreateModel(
            name='DocumentChunk',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chunk_index', models.PositiveIntegerField()),
                ('text', models.TextField()),
                ('embedding', VectorField(dimensions=768)),
                ('document', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='chunks',
                    to='vehicles.vehicledocument',
                )),
            ],
            options={
                'db_table': 'document_chunks',
                'ordering': ['document', 'chunk_index'],
            },
        ),
    ]
