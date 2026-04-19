import uuid
from django.db import models
from datetime import date

# Create your models here.
class Course(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Counsellor(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Batch(models.Model):
    time = models.TimeField()

    def __str__(self):
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
    student = models.ForeignKey('Student', on_delete=models.CASCADE)

    installment_no = models.PositiveIntegerField()
    installment_date = models.DateField()
    amount = models.IntegerField()

    class Meta:
        unique_together = ('student', 'installment_no')  # prevents duplicate installment numbers

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
    center = models.ForeignKey('Center', on_delete=models.CASCADE)
    batch = models.ForeignKey('Batch', on_delete=models.CASCADE)

    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"{self.trainer.name} - {self.batch.time}"

# models.py

class CenterLogistics(models.Model):
    center = models.OneToOneField('Center', on_delete=models.CASCADE)

    total_pc = models.PositiveIntegerField(default=0)
    repair_pc = models.PositiveIntegerField(default=0)

    @property
    def working_pc(self):
        return max(self.total_pc - self.repair_pc, 0)

    def save(self, *args, **kwargs):
        # 🔥 VALIDATION: repair cannot exceed total
        if self.repair_pc > self.total_pc:
            self.repair_pc = self.total_pc

        super().save(*args, **kwargs)

    def __str__(self):
        return self.center.name
