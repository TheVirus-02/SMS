from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('student', '0011_student_address_student_email_student_guardian_mobile_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='installment',
            name='payment_mode',
            field=models.CharField(choices=[('cash', 'Cash'), ('upi', 'UPI'), ('card', 'Card'), ('bank_transfer', 'Bank Transfer')], default='cash', max_length=20),
        ),
        migrations.AddField(
            model_name='installment',
            name='remarks',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='installment',
            name='transaction_id',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
