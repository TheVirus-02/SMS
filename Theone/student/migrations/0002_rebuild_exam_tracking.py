# Generated manually to replace legacy exam tables with student-course based exam tracking.

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('student', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL("DROP TABLE IF EXISTS student_examdetail"),
                migrations.RunSQL("DROP TABLE IF EXISTS student_examregistration"),
                migrations.RunSQL("DROP TABLE IF EXISTS student_exam"),
            ],
            state_operations=[
                migrations.DeleteModel(name='ExamMarks'),
                migrations.DeleteModel(name='ExamRegistration'),
                migrations.DeleteModel(name='Exam'),
            ],
        ),
        migrations.CreateModel(
            name='ExamRegistration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('exam_date', models.DateField()),
                ('receipt_no', models.CharField(max_length=50, unique=True)),
                ('receipt_issued_date', models.DateField()),
                ('receipt_amount', models.PositiveIntegerField(default=0)),
                ('payment_method', models.CharField(choices=[('cash', 'Cash'), ('upi', 'UPI'), ('card', 'Card'), ('bank_transfer', 'Bank Transfer')], default='cash', max_length=20)),
                ('payment_amount', models.PositiveIntegerField(default=0)),
                ('payment_reference', models.CharField(blank=True, max_length=100, null=True)),
                ('exam_marks', models.PositiveIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ('practical_marks', models.PositiveIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(30)])),
                ('remarks', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('receipt_issued_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='exam_receipts_issued', to='student.trainer')),
                ('student_course', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='exam_registration', to='student.studentcourse')),
            ],
            options={
                'ordering': ['exam_date', 'student_course__student__name'],
            },
        ),
    ]
