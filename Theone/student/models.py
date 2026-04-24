import uuid
from django.db import models
from datetime import date, datetime, timedelta
from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError

# Create your models here.
class Course(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name

class Counsellor(models.Model):
    name = models.CharField(max_length=100)
    mobile = models.CharField(max_length=15, null=True, blank=True)
    center = models.ForeignKey('Center', on_delete=models.SET_NULL, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    age = models.IntegerField(null=True, blank=True, default=0)
    dob = models.DateField(null=True, blank=True)
    joining_date = models.DateField(default=date.today, null=True, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Enquiry(models.Model):
    STATUS_CHOICES = [
        ('new', 'New Enquiry'),
        ('contacted', 'Contacted'),
        ('interested', 'Interested'),
        ('demo_scheduled', 'Demo Scheduled'),
        ('demo_attended', 'Demo Attended'),
        ('follow_up', 'Follow-up Pending'),
        ('ready', 'Ready For Admission'),
        ('admitted', 'Admitted'),
        ('lost', 'Lost / Not Interested'),
    ]

    PROBABILITY_CHOICES = [
        ('hot', 'Hot'),
        ('warm', 'Warm'),
        ('cold', 'Cold'),
    ]

    name = models.CharField(max_length=100)
    mobile_no = models.CharField(max_length=15)
    alt_mobile_no = models.CharField(max_length=15, null=True, blank=True)
    guardian_name = models.CharField(max_length=100, null=True, blank=True)
    guardian_mobile = models.CharField(max_length=15, null=True, blank=True)
    age = models.IntegerField(null=True, blank=True)
    qualification = models.CharField(max_length=100, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    enquiry_date = models.DateField(default=date.today)
    interested_course = models.ForeignKey('Course', on_delete=models.SET_NULL, null=True, blank=True)
    preferred_batch = models.ForeignKey('Batch', on_delete=models.SET_NULL, null=True, blank=True)
    preferred_center = models.ForeignKey('Center', on_delete=models.SET_NULL, null=True, blank=True)
    fee_discussed = models.IntegerField(null=True, blank=True)
    expected_joining_date = models.DateField(null=True, blank=True)
    source = models.CharField(max_length=100, null=True, blank=True)
    assigned_counsellor = models.ForeignKey('Counsellor', on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    next_follow_up_date = models.DateField(null=True, blank=True)
    last_follow_up_date = models.DateField(null=True, blank=True)
    follow_up_remarks = models.TextField(null=True, blank=True)
    demo_date = models.DateField(null=True, blank=True)
    demo_result = models.CharField(max_length=100, null=True, blank=True)
    admission_probability = models.CharField(max_length=10, choices=PROBABILITY_CHOICES, default='warm')
    lost_reason = models.CharField(max_length=150, null=True, blank=True)
    converted_student = models.OneToOneField('Student', on_delete=models.SET_NULL, null=True, blank=True)
    converted_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-enquiry_date', 'name']

    @property
    def is_converted(self):
        return bool(self.converted_student_id)

    def __str__(self):
        return f"{self.name} - {self.mobile_no}"


class Batch(models.Model):
    name = models.CharField(max_length=100, blank=True)
    time = models.TimeField()

    class Meta:
        ordering = ['time', 'name']

    def save(self, *args, **kwargs):
        previous_time = None
        if self.pk:
            previous_time = Batch.objects.filter(pk=self.pk).values_list('time', flat=True).first()

        super().save(*args, **kwargs)

        if previous_time and previous_time != self.time:
            for schedule in self.trainerschedule_set.all():
                schedule.save()

    def __str__(self):
        if self.time and self.name:
            return f"{self.name} ({self.time.strftime('%I %p').lstrip('0')})"
        if self.time:
            return self.time.strftime("%I %p").lstrip("0")
        return "No Time"


class Center(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class StudentCourse(models.Model):
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    course = models.ForeignKey('Course', on_delete=models.CASCADE)

    is_completed = models.BooleanField(default=False)
    completion_date = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ['student', 'course']

    def save(self, *args, **kwargs):
        if self.is_completed and not self.completion_date:
            from datetime import date
            self.completion_date = date.today()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.name} - {self.course.name}"

class Installment(models.Model):
    PAYMENT_MODE_CHOICES = [
        ('cash', 'Cash'),
        ('upi', 'UPI'),
        ('card', 'Card'),
        ('bank_transfer', 'Bank Transfer'),
    ]

    student = models.ForeignKey('Student', on_delete=models.CASCADE)

    installment_no = models.PositiveIntegerField()
    installment_date = models.DateField()
    amount = models.IntegerField()
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES, default='cash')
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ('student', 'installment_no')  # prevents duplicate installment numbers

    def save(self, *args, **kwargs):
        if not self.installment_no:
            last_installment = Installment.objects.filter(student=self.student).order_by('-installment_no').first()
            self.installment_no = 1 if last_installment is None else last_installment.installment_no + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.name} - Installment {self.installment_no}"

# Attendance Class
class Attendance(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('leave', 'Leave'),
    ]

    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    remarks = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ('student', 'date')  # one entry per day per student

    def __str__(self):
        return f"{self.student.name} - {self.date} - {self.status}"

# Student App Class
class Student(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('completed', 'Batch Completed'),
        ('leave', 'Leave'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )

    student_id = models.CharField(
        max_length=15,
        unique=True,
        editable=False
    )
    trainer = models.ForeignKey(
        'Trainer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    batch = models.ForeignKey(
        Batch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    center = models.ForeignKey(
        Center,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    name = models.CharField(max_length=100)
    mobile_no = models.CharField(max_length=15)
    alt_mobile_no = models.CharField(max_length=15, null=True, blank=True)
    guardian_name = models.CharField(max_length=100, null=True, blank=True)
    guardian_mobile = models.CharField(max_length=15, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    qualification = models.CharField(max_length=100, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    reference_source = models.CharField(max_length=100, null=True, blank=True)

    dob = models.DateField(null=True, blank=True)
    joining_date = models.DateField(null=True, blank=True)
    course_completed = models.BooleanField(default=False)
    completion_date = models.DateField(null=True, blank=True)

    counsellor = models.ForeignKey(
        Counsellor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    courses = models.ManyToManyField(
        Course,
        through='StudentCourse',
        related_name='new_students'
    )

    course_fee = models.IntegerField(null=True, blank=True)
    paid_fee = models.IntegerField(null=True, blank=True)

    @property
    def installment_total(self):
        return self.installment_set.aggregate(
            total=models.Sum('amount')
        )['total'] or 0

    @property
    def remaining_fee(self):
        fee = self.course_fee or 0
        return max(fee - self.total_paid, 0)

    @property
    def payment_status(self):
        if self.remaining_fee == 0 and self.course_fee:
            return "Paid"
        elif self.total_paid == 0:
            return "Pending"
        else:
            return "Partial"

    def generate_unique_id(self):
        while True:
            new_id = "MTX-" + uuid.uuid4().hex[:6].upper()

            # Check if already exists
            if not Student.objects.filter(student_id=new_id).exists():
                return new_id

    @property
    def total_paid(self):
        return (self.paid_fee or 0) + self.installment_total

    @property
    def total_present(self):
        return self.attendance_set.filter(status='present').count()

    def save(self, *args, **kwargs):
        if not self.student_id:
            self.student_id = self.generate_unique_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Trainer(models.Model):
    name = models.CharField(max_length=100)
    age = models.IntegerField(null=True, blank=True,default=0)
    dob = models.DateField(null=True, blank=True)
    mobile = models.CharField(max_length=15)
    joining_date = models.DateField(default=date.today,null=True, blank=True)
    courses = models.ManyToManyField('Course', blank=True)

    def __str__(self):
        return self.name

class TrainerSchedule(models.Model):
    trainer = models.ForeignKey('Trainer', on_delete=models.CASCADE)
    center = models.ForeignKey('Center', on_delete=models.CASCADE, null=True, blank=True)
    batch = models.ForeignKey('Batch', on_delete=models.CASCADE)

    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ['batch__time', 'trainer__name', 'center__name']

    def clean(self):
        if not self.batch_id:
            return

        slot_start = self.batch.time
        slot_end = (datetime.combine(date.today(), slot_start) + timedelta(hours=1)).time()

        opening_time = datetime.strptime("07:00", "%H:%M").time()
        closing_time = datetime.strptime("21:00", "%H:%M").time()
        if slot_start < opening_time or slot_end > closing_time:
            raise ValidationError("Trainer schedule must be between 7:00 AM and 9:00 PM.")

        overlapping_schedule = TrainerSchedule.objects.filter(
            trainer=self.trainer,
            batch=self.batch,
        ).exclude(pk=self.pk).first()
        if overlapping_schedule:
            raise ValidationError("This trainer is already assigned for the selected batch time.")

    def save(self, *args, **kwargs):
        if self.batch_id:
            self.start_time = self.batch.time
            self.end_time = (datetime.combine(date.today(), self.batch.time) + timedelta(hours=1)).time()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        center_name = self.center.name if self.center else "Center Pending"
        return f"{self.trainer.name} - {center_name} - {self.batch}"

# models.py

class CenterLogistics(models.Model):
    center = models.OneToOneField('Center', on_delete=models.CASCADE)

    total_pc = models.PositiveIntegerField(default=0)
    repair_pc = models.PositiveIntegerField(default=0)

    @property
    def working_pc(self):
        return max(self.total_pc - self.repair_pc, 0)

    @property
    def total_capacity(self):
        return self.total_pc

    @property
    def remaining_pc(self):
        return self.working_pc

    def save(self, *args, **kwargs):
        # 🔥 VALIDATION: repair cannot exceed total
        if self.repair_pc > self.total_pc:
            self.repair_pc = self.total_pc

        super().save(*args, **kwargs)

    def __str__(self):
        return self.center.name

class ExamRegistration(models.Model):
    PAYMENT_MODE_CHOICES = Installment.PAYMENT_MODE_CHOICES

    student_course = models.OneToOneField(
        'StudentCourse',
        on_delete=models.CASCADE,
        related_name='exam_registration'
    )
    exam_date = models.DateField()
    receipt_no = models.CharField(max_length=50, unique=True)
    receipt_issued_by = models.ForeignKey(
        'Trainer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exam_receipts_issued'
    )
    receipt_issued_date = models.DateField()
    receipt_amount = models.PositiveIntegerField(default=0)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES, default='cash')
    payment_amount = models.PositiveIntegerField(default=0)
    payment_reference = models.CharField(max_length=100, null=True, blank=True)
    exam_marks = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    practical_marks = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(30)]
    )
    certificate_created_date = models.DateField(null=True, blank=True)
    certificate_given_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['exam_date', 'student_course__student__name']

    def __str__(self):
        return f"{self.student_name} - {self.course_name}"

    @property
    def student(self):
        return self.student_course.student

    @property
    def course(self):
        return self.student_course.course

    @property
    def student_name(self):
        return self.student.name

    @property
    def course_name(self):
        return self.course.name

    @property
    def calculated_marks(self):
        if self.exam_marks is None:
            return None
        return round((self.exam_marks / 100) * 70, 2)

    @property
    def total_marks(self):
        if self.exam_marks is None and self.practical_marks is None:
            return None
        return round((self.calculated_marks or 0) + (self.practical_marks or 0), 2)

    @property
    def has_uploaded_marks(self):
        return self.exam_marks is not None or self.practical_marks is not None

    @property
    def is_certificate_created(self):
        return bool(self.certificate_created_date)

    @property
    def is_certificate_given(self):
        return bool(self.certificate_given_date)

    @property
    def certificate_status_label(self):
        if not self.has_uploaded_marks:
            return "Exam is not given yet"
        if not self.is_certificate_created:
            return "Pending"
        if self.is_certificate_given:
            return "Given"
        return "Created"

    @property
    def latest_sms_log(self):
        prefetched_logs = getattr(self, '_prefetched_objects_cache', {}).get('sms_logs')
        if prefetched_logs is not None:
            return prefetched_logs[0] if prefetched_logs else None
        return self.sms_logs.order_by('-created_at').first()


class SmsLog(models.Model):
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_SKIPPED = 'skipped'

    STATUS_CHOICES = [
        (STATUS_SENT, 'Sent'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_SKIPPED, 'Skipped'),
    ]

    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='sms_logs')
    exam_registration = models.ForeignKey(
        'ExamRegistration',
        on_delete=models.CASCADE,
        related_name='sms_logs',
        null=True,
        blank=True
    )
    provider = models.CharField(max_length=30, default='twilio')
    phone_number = models.CharField(max_length=30)
    message_body = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    provider_message_id = models.CharField(max_length=100, null=True, blank=True)
    response_detail = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        exam_label = self.exam_registration.course_name if self.exam_registration_id else "General"
        return f"{self.student.name} - {exam_label} - {self.status}"
